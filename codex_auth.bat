@echo off
echo Starting Codex for authentication...
echo.
set "CODEX_CMD=%APPDATA%\npm\codex.cmd"
if not exist "%CODEX_CMD%" set "CODEX_CMD=%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\npm\codex.cmd"
if not exist "%CODEX_CMD%" (
  echo codex.cmd not found. Check your Codex CLI installation.
  pause
  exit /b 1
)
"%CODEX_CMD%"
pause
