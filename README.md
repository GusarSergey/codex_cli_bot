# Codex CLI Bot

Windows-first Telegram bridge for Codex, based on Untether.

This repository is set up to run Codex through Telegram on Windows with:

- background launch
- auto-restart after crashes
- Windows startup integration
- local patches for stable Codex execution on Windows

## What This Repo Contains

- `src/` with the Untether source used by the local launcher
- `start_untether.bat` to start the bridge in the background
- `stop_untether.bat` to stop the bridge processes
- `supervise_untether.pyw` to keep the worker alive
- `run_untether_detached.pyw` to launch Untether outside the active Codex desktop session
- `codex_auth.bat` to run Codex authentication in the same environment
- `install_windows_startup.ps1` to install autostart for Windows
- `..\start_untether.bat` and `..\run_untether_detached.pyw` as compatibility wrappers that redirect into this folder

## Quick Start

1. Install Codex CLI.
2. Install Untether dependencies for this repo.
3. Configure your Telegram bot token in your Untether config.
4. Start the bridge from this folder:

```bat
untether\start_untether.bat
```

5. Send a test message to your Telegram bot.

## Windows Autostart

Install autostart once:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_startup.ps1
```

After that, Windows will start the bridge when the current user signs in.

The bridge is supervised. If the worker exits unexpectedly, `supervise_untether.pyw` starts it again automatically.

## Daily Commands

```bat
untether\start_untether.bat
untether\stop_untether.bat
untether\codex_auth.bat
```

## Logs

Use these files first when Telegram stops responding:

- `untether.log`
- `untether-supervisor.log`

## Important Notes

- This fork is tuned for Windows and Codex.
- Codex is launched through a hardened Windows path so `codex.cmd` is used correctly.
- The Telegram bridge is detached from the active Codex desktop window, so it can keep working in the background.
- Optional engine import failures on Windows should not block Telegram startup.

## Recovery

If the bot stops answering:

1. Check `untether.log`.
2. Check `untether-supervisor.log`.
3. Restart the bridge:

```bat
untether\stop_untether.bat
untether\start_untether.bat
```

## Canonical Launch Path

Use only the launchers inside the `untether\` folder for normal work:

- `untether\start_untether.bat`
- `untether\stop_untether.bat`
- `untether\run_untether_detached.pyw`

Root-level files with the same names are kept only as compatibility redirects so older shortcuts do not start a second bridge instance.

## Upstream

This repo started from Untether and keeps `upstream` pointed at the original project:

- upstream project: [littlebearapps/untether](https://github.com/littlebearapps/untether)
- published fork: [GusarSergey/codex_cli_bot](https://github.com/GusarSergey/codex_cli_bot)
