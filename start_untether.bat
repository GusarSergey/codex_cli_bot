@echo off
setlocal
title Untether - Telegram Bridge
echo Starting Untether supervisor...
echo.
set "UNTETHER_PYW=%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\uv\tools\untether\Scripts\pythonw.exe"
set "SUPERVISOR=%~dp0supervise_untether.pyw"
if not exist "%UNTETHER_PYW%" (
  echo Untether Python runtime not found.
  pause
  exit /b 1
)
if not exist "%SUPERVISOR%" (
  echo Supervisor script not found: %SUPERVISOR%
  pause
  exit /b 1
)
start "" "%UNTETHER_PYW%" "%SUPERVISOR%"
echo Untether supervisor was launched.
