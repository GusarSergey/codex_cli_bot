from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
LOG_PATH = PROJECT_DIR / "untether.log"
LOCAL_BIN = Path.home() / ".local" / "bin"
NODEJS_DIR = Path(r"C:\Program Files\nodejs")
FALLBACK_NPM_BIN = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Packages"
    / "Claude_pzs8sxrjxfjjc"
    / "LocalCache"
    / "Roaming"
    / "npm"
)


def _resolve_npm_bin() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        primary = Path(appdata) / "npm"
        if (primary / "codex.cmd").exists():
            return primary
    return FALLBACK_NPM_BIN


def _configure_stdio() -> None:
    stream = LOG_PATH.open("a", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    ts = datetime.now(timezone.utc).isoformat()
    print(f"{ts} [launcher] detached start", flush=True)


def _configure_environment() -> None:
    npm_bin = _resolve_npm_bin()
    path_parts = [
        str(npm_bin),
        str(LOCAL_BIN),
        str(NODEJS_DIR),
        os.environ.get("PATH", ""),
    ]
    os.environ["PATH"] = ";".join(part for part in path_parts if part)
    os.chdir(PROJECT_DIR)
    src_dir = PROJECT_DIR / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))


def main() -> None:
    _configure_stdio()
    _configure_environment()
    try:
        from untether.cli import main as untether_main

        untether_main()
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
