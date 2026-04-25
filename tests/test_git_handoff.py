from __future__ import annotations

import subprocess
from pathlib import Path

from untether.git_handoff import GitHandoff, execute_git_handoff, extract_git_handoff


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.name", "Test User"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    (repo / "BRAIN.md").write_text("line 1\n", encoding="utf-8")
    _git(["add", "BRAIN.md"], cwd=repo)
    _git(["commit", "-m", "init"], cwd=repo)
    return repo


def test_extract_git_handoff_strips_block() -> None:
    answer = (
        "Done.\n\n```untether-git\n"
        '{"files":["BRAIN.md"],"message":"docs: note","push":true}\n'
        "```"
    )

    cleaned, handoff = extract_git_handoff(answer)

    assert cleaned == "Done."
    assert handoff == GitHandoff(
        files=("BRAIN.md",),
        message="docs: note",
        push=True,
    )


def test_execute_git_handoff_commits_changed_files(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "BRAIN.md").write_text("line 1\nline 2\n", encoding="utf-8")

    result = execute_git_handoff(
        GitHandoff(
            files=("BRAIN.md",),
            message="docs: update brain",
            push=False,
        ),
        cwd=repo,
    )

    assert result.status == "committed"
    assert result.commit_hash is not None
    assert "committed" in result.summary


def test_execute_git_handoff_skips_when_no_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    result = execute_git_handoff(
        GitHandoff(
            files=("BRAIN.md",),
            message="docs: update brain",
            push=False,
        ),
        cwd=repo,
    )

    assert result.status == "skipped"
    assert "no matching file changes" in result.summary
