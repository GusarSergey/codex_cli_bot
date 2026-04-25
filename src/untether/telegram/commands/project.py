from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from ...commands import CommandBackend, CommandContext, CommandResult
from ...config import ConfigError, ensure_table, read_config, write_config
from ...context import RunContext
from ...ids import RESERVED_CHAT_COMMANDS, RESERVED_ENGINE_IDS, is_valid_id
from ...logging import get_logger
from ...runtime_loader import build_runtime_spec
from ...settings import load_settings
from ..chat_prefs import ChatPrefsStore, resolve_prefs_path
from ..files import split_command_args
from ..types import TelegramIncomingMessage
from .overrides import require_admin_or_private
from .reply import make_reply

if TYPE_CHECKING:
    from ..bridge import TelegramBridgeConfig

logger = get_logger(__name__)

PROJECT_USAGE = (
    "usage: `/project`, `/project use <path>`, `/project add <path>`, "
    "or `/project clear`"
)

_INVALID_ALIAS_RE = re.compile(r"[^a-z0-9_]+")


def _normalize_alias(value: str) -> str:
    alias = _INVALID_ALIAS_RE.sub("_", value.strip().lower()).strip("_")
    alias = re.sub(r"_+", "_", alias)
    if not alias:
        alias = "project"
    if alias[0].isdigit():
        alias = f"p_{alias}"
    return alias[:32].rstrip("_") or "project"


def _allocate_alias(
    preferred: str,
    *,
    existing: set[str],
    reserved: set[str],
) -> str:
    base = _normalize_alias(preferred)
    candidate = base
    index = 2
    while candidate in existing or candidate in reserved or not is_valid_id(candidate):
        suffix = f"_{index}"
        candidate = f"{base[: max(1, 32 - len(suffix))]}{suffix}"
        index += 1
    return candidate


def _find_project_by_path(
    projects: dict[str, Any], target_path: Path
) -> tuple[str, dict[str, Any]] | None:
    resolved_target = target_path.resolve(strict=False)
    for key, value in projects.items():
        if not isinstance(value, dict):
            continue
        raw_path = value.get("path")
        if not isinstance(raw_path, str):
            continue
        if Path(raw_path).expanduser().resolve(strict=False) == resolved_target:
            return key, value
    return None


def _register_project(
    *,
    config_path: Path,
    project_path: Path,
    default_engine: str,
) -> tuple[str, bool]:
    config = read_config(config_path)
    projects = ensure_table(
        config,
        "projects",
        config_path=config_path,
        label="projects",
    )
    if not isinstance(projects, dict):
        raise ConfigError(f"Invalid `projects` in {config_path}; expected a table.")

    existing = _find_project_by_path(projects, project_path)
    if existing is not None:
        alias, entry = existing
        if "default_engine" not in entry:
            entry["default_engine"] = default_engine
            write_config(config, config_path)
        return alias, False

    reserved = {value.lower() for value in RESERVED_CHAT_COMMANDS | RESERVED_ENGINE_IDS}
    alias = _allocate_alias(
        project_path.name or project_path.stem or "project",
        existing={str(key).lower() for key in projects},
        reserved=reserved,
    )
    projects[alias] = {
        "path": str(project_path),
        "default_engine": default_engine,
    }
    config["watch_config"] = True
    write_config(config, config_path)
    return alias, True


def _state_summary(ctx: CommandContext, bound_project: str | None) -> str:
    aliases = ", ".join(ctx.runtime.project_aliases()) or "none"
    current = bound_project or "none"
    return (
        f"current project: `{current}`\n"
        f"default project: `{ctx.runtime.default_project or 'none'}`\n"
        f"available aliases: `{aliases}`"
    )


def _state_summary_runtime(
    runtime,
    bound_project: str | None,
) -> str:
    aliases = ", ".join(runtime.project_aliases()) or "none"
    current = bound_project or "none"
    return (
        f"current project: `{current}`\n"
        f"default project: `{runtime.default_project or 'none'}`\n"
        f"available aliases: `{aliases}`"
    )


async def _handle_project_command(
    cfg: TelegramBridgeConfig,
    msg: TelegramIncomingMessage,
    args_text: str,
    chat_prefs: ChatPrefsStore | None,
) -> None:
    reply = make_reply(cfg, msg)
    config_path = cfg.runtime.config_path
    if config_path is None or chat_prefs is None:
        await reply(text="project switching unavailable; config path is not set.")
        return

    allowed = await require_admin_or_private(
        cfg,
        msg,
        missing_sender="cannot verify sender for project switching.",
        failed_member="failed to verify project switching permissions.",
        denied="project switching is restricted to group admins.",
    )
    if not allowed:
        return

    tokens = split_command_args(args_text)
    action = tokens[0].lower() if tokens else "show"
    bound = await chat_prefs.get_context(msg.chat_id)

    if action in {"show", ""}:
        await reply(text=_state_summary_runtime(cfg.runtime, bound.project if bound else None))
        return

    if action == "clear":
        await chat_prefs.clear_context(msg.chat_id)
        await reply(text="chat project binding cleared.")
        return

    if action not in {"use", "add"} or len(tokens) < 2:
        await reply(text=PROJECT_USAGE)
        return

    raw_path = " ".join(tokens[1:]).strip()
    project_path = Path(raw_path).expanduser()
    if not project_path.is_absolute():
        project_path = project_path.resolve(strict=False)
    if not project_path.exists():
        await reply(text=f"path does not exist: `{project_path}`")
        return
    if not project_path.is_dir():
        await reply(text=f"path is not a directory: `{project_path}`")
        return

    alias, created = _register_project(
        config_path=config_path,
        project_path=project_path.resolve(strict=False),
        default_engine=cfg.runtime.default_engine,
    )
    settings, resolved_config_path = load_settings(config_path)
    spec = build_runtime_spec(
        settings=settings,
        config_path=resolved_config_path,
        reserved=RESERVED_CHAT_COMMANDS,
    )
    spec.apply(cfg.runtime, config_path=resolved_config_path)

    verb = "registered" if created else "reused"
    if action == "add":
        await reply(
            text=(
                f"{verb} project `{alias}` -> `{project_path}`.\n"
                "The project is available immediately."
            )
        )
        return

    await chat_prefs.set_context(
        msg.chat_id,
        RunContext(project=alias, branch=None),
    )
    await reply(
        text=(
            f"switched this chat to project `{alias}` -> `{project_path}`.\n"
            "Codex will use this repo for the next runs."
        )
    )


class ProjectCommand:
    id = "project"
    description = "register path and switch chat project"

    async def handle(self, ctx: CommandContext) -> CommandResult | None:
        config_path = ctx.config_path
        if config_path is None:
            return CommandResult("project switching unavailable (no config path).")

        prefs = ChatPrefsStore(resolve_prefs_path(config_path))
        bound = await prefs.get_context(ctx.message.channel_id)
        tokens = ctx.args
        action = tokens[0].lower() if tokens else "show"

        if action in {"show", ""}:
            return CommandResult(_state_summary(ctx, bound.project if bound else None))

        if action == "clear":
            await prefs.clear_context(ctx.message.channel_id)
            return CommandResult("chat project binding cleared.")

        if action not in {"use", "add"}:
            return CommandResult(PROJECT_USAGE, parse_mode="Markdown")

        if len(tokens) < 2:
            return CommandResult(PROJECT_USAGE, parse_mode="Markdown")

        raw_path = " ".join(tokens[1:]).strip()
        project_path = Path(raw_path).expanduser()
        if not project_path.is_absolute():
            project_path = project_path.resolve(strict=False)
        if not project_path.exists():
            return CommandResult(f"path does not exist: `{project_path}`")
        if not project_path.is_dir():
            return CommandResult(f"path is not a directory: `{project_path}`")

        alias, created = _register_project(
            config_path=config_path,
            project_path=project_path.resolve(strict=False),
            default_engine=ctx.runtime.default_engine,
        )
        settings, resolved_config_path = load_settings(config_path)
        spec = build_runtime_spec(
            settings=settings,
            config_path=resolved_config_path,
            reserved=RESERVED_CHAT_COMMANDS,
        )
        spec.apply(ctx.runtime, config_path=resolved_config_path)

        verb = "registered" if created else "reused"
        if action == "add":
            return CommandResult(
                f"{verb} project `{alias}` -> `{project_path}`.\n"
                "The project is available immediately."
            )

        # Bind explicitly to the new alias; this is separate from the global default.
        await prefs.set_context(
            ctx.message.channel_id,
            RunContext(project=alias, branch=None),
        )
        return CommandResult(
            f"switched this chat to project `{alias}` -> `{project_path}`.\n"
            "Codex will use this repo for the next runs."
        )


BACKEND: CommandBackend = ProjectCommand()
