from __future__ import annotations

from pathlib import Path

import pytest

from untether.commands import CommandContext
from untether.config import read_config
from untether.telegram.chat_prefs import ChatPrefsStore, resolve_prefs_path
from untether.telegram.commands.project import (
    ProjectCommand,
    _allocate_alias,
    _normalize_alias,
    _register_project,
)
from untether.transport import MessageRef


class _FakeExecutor:
    async def send(self, *args, **kwargs):  # pragma: no cover - not used here
        return None

    async def edit(self, *args, **kwargs):  # pragma: no cover - not used here
        return None

    async def run_one(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("run_one should not be called")

    async def run_many(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("run_many should not be called")


class _FakeRuntime:
    def __init__(self, *, config_path: Path) -> None:
        self.config_path = config_path
        self.default_engine = "codex"
        self.default_project = None
        self.watch_config = False
        self.applied = False
        self._aliases: tuple[str, ...] = ()

    def project_aliases(self) -> tuple[str, ...]:
        return self._aliases

    def update(
        self,
        *,
        router,
        projects,
        allowlist=None,
        config_path=None,
        plugin_configs=None,
        watch_config=False,
    ) -> None:
        self.applied = True
        self._aliases = tuple(project.alias for project in projects.projects.values())
        self.default_project = projects.default_project
        self.watch_config = watch_config


def _write_config(path: Path) -> None:
    path.write_text(
        'default_engine = "codex"\n'
        'transport = "telegram"\n'
        "\n"
        "[transports.telegram]\n"
        'bot_token = "123:abc"\n'
        "chat_id = 1\n"
        'session_mode = "chat"\n'
        "show_resume_line = false\n",
        encoding="utf-8",
    )


def test_normalize_alias_and_allocate() -> None:
    assert _normalize_alias("My Cool Repo") == "my_cool_repo"
    assert _normalize_alias("123 repo") == "p_123_repo"
    assert _allocate_alias(
        "demo repo",
        existing={"demo_repo"},
        reserved={"codex"},
    ) == "demo_repo_2"


def test_register_project_writes_config(tmp_path: Path) -> None:
    cfg = tmp_path / "untether.toml"
    _write_config(cfg)
    repo = tmp_path / "My Repo"
    repo.mkdir()

    alias, created = _register_project(
        config_path=cfg,
        project_path=repo,
        default_engine="codex",
    )

    assert created is True
    assert alias == "my_repo"
    config = read_config(cfg)
    assert config["watch_config"] is True
    assert config["projects"]["my_repo"]["path"] == str(repo)


@pytest.mark.anyio
async def test_project_use_registers_and_binds_chat(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "untether.toml"
    _write_config(cfg)
    repo = tmp_path / "Another Repo"
    repo.mkdir()

    runtime = _FakeRuntime(config_path=cfg)

    class _FakeSpec:
        def apply(self, runtime_obj, *, config_path):
            runtime_obj._aliases = ("another_repo",)
            runtime_obj.applied = True

    monkeypatch.setattr(
        "untether.telegram.commands.project.build_runtime_spec",
        lambda **kwargs: _FakeSpec(),
    )

    ctx = CommandContext(
        command="project",
        text=f'/project use "{repo}"',
        args_text=f'use "{repo}"',
        args=("use", str(repo)),
        message=MessageRef(channel_id=123, message_id=1),
        reply_to=None,
        reply_text=None,
        config_path=cfg,
        plugin_config={},
        runtime=runtime,
        executor=_FakeExecutor(),
        trigger_manager=None,
        default_chat_id=None,
    )

    result = await ProjectCommand().handle(ctx)

    assert result is not None
    assert "switched this chat to project `another_repo`" in result.text
    assert runtime.applied is True

    prefs = ChatPrefsStore(resolve_prefs_path(cfg))
    bound = await prefs.get_context(123)
    assert bound is not None
    assert bound.project == "another_repo"

    config = read_config(cfg)
    assert config["projects"]["another_repo"]["path"] == str(repo)
