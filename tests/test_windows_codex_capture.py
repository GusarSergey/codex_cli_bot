import os

import pytest

from untether.model import CompletedEvent, StartedEvent
from untether.runners.codex import CodexRunner


class _FakePopen:
    def __init__(
        self,
        cmd,
        *,
        stdin,
        stdout,
        stderr,
        env,
        cwd,
        stdout_data: bytes,
        stderr_data: bytes,
        returncode: int,
        captured: dict,
    ) -> None:
        self.pid = 43210
        self.returncode = returncode
        captured["cmd"] = cmd
        captured["stdin"] = stdin
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["env"] = env
        captured["cwd"] = cwd
        self._stdout_data = stdout_data
        self._stderr_data = stderr_data
        self._captured = captured

    def communicate(self, payload: bytes | None) -> tuple[bytes, bytes]:
        self._captured["payload"] = payload
        return self._stdout_data, self._stderr_data


@pytest.mark.anyio
async def test_codex_runner_windows_blocking_capture_success(monkeypatch) -> None:
    import untether.runner as runner_module

    captured: dict = {}
    stdout_data = (
        b'{"type":"thread.started","thread_id":"019dc088-8c2e-7372-9f50-a8fbee215936"}\n'
        b'{"type":"turn.started"}\n'
        b'{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"OK"}}\n'
        b'{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}\n'
    )

    def fake_popen(cmd, **kwargs):
        return _FakePopen(
            cmd,
            stdout_data=stdout_data,
            stderr_data=b"",
            returncode=0,
            captured=captured,
            **kwargs,
        )

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(runner_module.subprocess, "Popen", fake_popen)

    runner = CodexRunner(codex_cmd="codex.cmd", extra_args=["-c", "notify=[]"])
    events = [evt async for evt in runner.run("Reply with exactly: OK", None)]

    started = next(evt for evt in events if isinstance(evt, StartedEvent))
    completed = next(evt for evt in events if isinstance(evt, CompletedEvent))
    assert started.resume.value == "019dc088-8c2e-7372-9f50-a8fbee215936"
    assert completed.ok is True
    assert completed.answer == "OK"
    assert captured["payload"] == b"Reply with exactly: OK"
    assert captured["cmd"][0] == "codex.cmd"


@pytest.mark.anyio
async def test_codex_runner_windows_blocking_capture_error(monkeypatch) -> None:
    import untether.runner as runner_module

    stderr_text = "The application was unable to start correctly."

    def fake_popen(cmd, **kwargs):
        return _FakePopen(
            cmd,
            stdout_data=b"",
            stderr_data=stderr_text.encode("utf-8"),
            returncode=3221225794,
            captured={},
            **kwargs,
        )

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(runner_module.subprocess, "Popen", fake_popen)

    runner = CodexRunner(codex_cmd="codex.cmd", extra_args=["-c", "notify=[]"])
    events = [evt async for evt in runner.run("Reply with exactly: OK", None)]

    completed = next(evt for evt in events if isinstance(evt, CompletedEvent))
    assert completed.ok is False
    assert completed.error is not None
    assert "rc=3221225794" in completed.error
    assert stderr_text in completed.error
