from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "supervise_untether.pyw"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("supervise_untether", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_acquire_lock_rejects_running_pid(tmp_path, monkeypatch):
    module = _load_module()
    lock_path = tmp_path / "bridge-supervisor.lock.json"
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    monkeypatch.setattr(module, "LOCK_PATH", lock_path)
    monkeypatch.setattr(module.os, "getpid", lambda: 1234)
    monkeypatch.setattr(module.time, "time", lambda: 111.0)
    monkeypatch.setattr(module, "_pid_running", lambda pid: pid == 9999)

    lock_path.write_text(json.dumps({"pid": 9999, "started_at": 1.0}), encoding="utf-8")

    assert module._acquire_lock() is False
    assert json.loads(lock_path.read_text(encoding="utf-8"))["pid"] == 9999


def test_acquire_lock_replaces_stale_pid(tmp_path, monkeypatch):
    module = _load_module()
    lock_path = tmp_path / "bridge-supervisor.lock.json"
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    monkeypatch.setattr(module, "LOCK_PATH", lock_path)
    monkeypatch.setattr(module.os, "getpid", lambda: 1234)
    monkeypatch.setattr(module.time, "time", lambda: 222.0)
    monkeypatch.setattr(module, "_pid_running", lambda pid: False)

    lock_path.write_text(json.dumps({"pid": 9999, "started_at": 1.0}), encoding="utf-8")

    assert module._acquire_lock() is True
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert payload["pid"] == 1234
    assert payload["started_at"] == 222.0
