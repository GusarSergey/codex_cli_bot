$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupDir = [Environment]::GetFolderPath("Startup")
$startupScript = Join-Path $startupDir "Codex Telegram Bridge.vbs"
$startScript = Join-Path $projectDir "start_untether.bat"

if (-not (Test-Path $startScript)) {
    throw "Start script not found: $startScript"
}

$vbs = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "$startScript" & Chr(34), 0
"@

Set-Content -Path $startupScript -Value $vbs -Encoding ASCII
Write-Host "Startup script installed:" $startupScript
