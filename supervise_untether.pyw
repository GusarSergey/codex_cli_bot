from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
STATE_DIR = Path.home() / ".untether"
LOCK_PATH = STATE_DIR / "bridge-supervisor.lock.json"
LOG_PATH = PROJECT_DIR / "untether-supervisor.log"
WORKER_SCRIPT = PROJECT_DIR / "run_untether_detached.pyw"


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        ts = datetime.now(timezone.utc).isoformat()
        fh.write(f"{ts} [supervisor] {message}\n")


def _pid_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 6:
            return False
        return False
    return True


def _acquire_lock() -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"pid": os.getpid(), "started_at": time.time()}
    serialized = json.dumps(payload, indent=2) + "\n"
    while True:
        try:
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                data = None
            if isinstance(data, dict):
                existing_pid = data.get("pid")
                if isinstance(existing_pid, int) and _pid_running(existing_pid):
                    _log(f"already running with pid={existing_pid}")
                    return False
            try:
                LOCK_PATH.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                return False
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(serialized)
        except Exception:
            try:
                LOCK_PATH.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return True


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> None:
    if not WORKER_SCRIPT.exists():
        _log(f"worker script missing: {WORKER_SCRIPT}")
        return
    if not _acquire_lock():
        return
    _log("started")
    restart_delay = 2.0
    try:
        while True:
            proc = subprocess.Popen(
                [sys.executable, str(WORKER_SCRIPT)],
                cwd=str(PROJECT_DIR),
            )
            _log(f"worker started pid={proc.pid}")
            rc = proc.wait()
            _log(f"worker exited pid={proc.pid} rc={rc}")
            time.sleep(restart_delay)
            if restart_delay < 30.0:
                restart_delay = min(30.0, restart_delay * 2.0)
    finally:
        _release_lock()
        _log("stopped")


if __name__ == "__main__":
    main()
