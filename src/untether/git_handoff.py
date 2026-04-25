from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .utils.git import git_is_worktree, git_run, git_stdout


_HANDOFF_RE = re.compile(r"```untether-git\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True, slots=True)
class GitHandoff:
    files: tuple[str, ...]
    message: str
    push: bool = False


@dataclass(frozen=True, slots=True)
class GitHandoffResult:
    status: str
    summary: str
    commit_hash: str | None = None


def extract_git_handoff(answer: str) -> tuple[str, GitHandoff | None]:
    matches = list(_HANDOFF_RE.finditer(answer))
    if not matches:
        return answer, None
    match = matches[-1]
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return answer, None
    if not isinstance(payload, dict):
        return answer, None

    files_raw = payload.get("files")
    message_raw = payload.get("message")
    push_raw = payload.get("push", False)
    if not isinstance(files_raw, list) or not files_raw:
        return answer, None
    files: list[str] = []
    for item in files_raw:
        if not isinstance(item, str):
            return answer, None
        cleaned = item.strip().replace("\\", "/")
        if not cleaned:
            return answer, None
        files.append(cleaned)
    if not isinstance(message_raw, str) or not message_raw.strip():
        return answer, None
    handoff = GitHandoff(
        files=tuple(files),
        message=message_raw.strip(),
        push=bool(push_raw),
    )
    cleaned_answer = (answer[: match.start()] + answer[match.end() :]).strip()
    cleaned_answer = re.sub(r"\n{3,}", "\n\n", cleaned_answer)
    return cleaned_answer, handoff


def _resolve_paths(cwd: Path, files: tuple[str, ...]) -> tuple[list[str], str | None]:
    resolved: list[str] = []
    root = cwd.resolve(strict=False)
    for rel in files:
        rel_path = Path(rel)
        if rel_path.is_absolute():
            return [], f"absolute path is not allowed: {rel}"
        candidate = (root / rel_path).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError:
            return [], f"path escapes repo root: {rel}"
        if ".git" in candidate.parts:
            return [], f".git paths are not allowed: {rel}"
        normalized = candidate.relative_to(root).as_posix()
        resolved.append(normalized)
    return resolved, None


def execute_git_handoff(handoff: GitHandoff, *, cwd: Path) -> GitHandoffResult:
    if not git_is_worktree(cwd):
        return GitHandoffResult(
            status="failed",
            summary="Bridge git: skipped because the current directory is not a git worktree.",
        )
    files, error = _resolve_paths(cwd, handoff.files)
    if error is not None:
        return GitHandoffResult(
            status="failed",
            summary=f"Bridge git: handoff rejected ({error}).",
        )
    status_result = git_run(["status", "--porcelain", "--", *files], cwd=cwd)
    if status_result is None:
        return GitHandoffResult(
            status="failed",
            summary="Bridge git: `git` is not available on PATH.",
        )
    if status_result.returncode != 0:
        error_text = (status_result.stderr or status_result.stdout).strip() or "git status failed"
        return GitHandoffResult(
            status="failed",
            summary=f"Bridge git: status check failed ({error_text}).",
        )
    if not status_result.stdout.strip():
        return GitHandoffResult(
            status="skipped",
            summary="Bridge git: no matching file changes to commit.",
        )

    add_result = git_run(["add", "--", *files], cwd=cwd)
    if add_result is None:
        return GitHandoffResult(
            status="failed",
            summary="Bridge git: `git add` could not start.",
        )
    if add_result.returncode != 0:
        error_text = (add_result.stderr or add_result.stdout).strip() or "git add failed"
        return GitHandoffResult(
            status="failed",
            summary=f"Bridge git: add failed ({error_text}).",
        )

    commit_result = git_run(["commit", "-m", handoff.message], cwd=cwd)
    if commit_result is None:
        return GitHandoffResult(
            status="failed",
            summary="Bridge git: `git commit` could not start.",
        )
    if commit_result.returncode != 0:
        error_text = (commit_result.stderr or commit_result.stdout).strip() or "git commit failed"
        return GitHandoffResult(
            status="failed",
            summary=f"Bridge git: commit failed ({error_text}).",
        )

    commit_hash = git_stdout(["rev-parse", "--short", "HEAD"], cwd=cwd)
    if handoff.push:
        push_result = git_run(["push"], cwd=cwd)
        if push_result is None:
            return GitHandoffResult(
                status="failed",
                commit_hash=commit_hash,
                summary="Bridge git: commit succeeded, but `git push` could not start.",
            )
        if push_result.returncode != 0:
            error_text = (push_result.stderr or push_result.stdout).strip() or "git push failed"
            return GitHandoffResult(
                status="failed",
                commit_hash=commit_hash,
                summary=f"Bridge git: committed `{commit_hash or 'unknown'}`, but push failed ({error_text}).",
            )
        return GitHandoffResult(
            status="pushed",
            commit_hash=commit_hash,
            summary=f"Bridge git: committed `{commit_hash or 'unknown'}` and pushed successfully.",
        )

    return GitHandoffResult(
        status="committed",
        commit_hash=commit_hash,
        summary=f"Bridge git: committed `{commit_hash or 'unknown'}`.",
    )
