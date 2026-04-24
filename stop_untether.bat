@echo off
setlocal
title Untether - Stop Telegram Bridge
echo Stopping Untether supervisor and worker...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = [Regex]::Escape('%~dp0');" ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -match 'pythonw.exe|python.exe') -and $_.CommandLine -match $root -and $_.CommandLine -match 'supervise_untether.pyw|run_untether_detached.pyw' };" ^
  "if ($procs) { $procs | Sort-Object ParentProcessId -Descending | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }"
echo Stop signal sent.
