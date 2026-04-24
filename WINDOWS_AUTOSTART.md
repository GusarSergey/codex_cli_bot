# Windows Autostart

This repo includes a Windows-specific launcher stack for the Telegram bridge:

- `start_untether.bat` starts the hidden supervisor
- `supervise_untether.pyw` restarts the worker automatically if it exits
- `run_untether_detached.pyw` launches Untether from this repo's `src/`
- `install_windows_startup.ps1` installs a hidden startup item in the current user's Startup folder
- `stop_untether.bat` stops the supervisor and worker processes for this repo

## Install Autostart

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_startup.ps1
```

After installation, Windows starts the bridge automatically when the current user signs in.

## Manual Control

```bat
start_untether.bat
stop_untether.bat
codex_auth.bat
```

## Recovery

If Telegram stops responding:

1. Check `untether.log`.
2. Check `untether-supervisor.log`.
3. Restart the bridge:

```bat
stop_untether.bat
start_untether.bat
```

The supervisor is designed to restart the worker automatically after unexpected exits.
