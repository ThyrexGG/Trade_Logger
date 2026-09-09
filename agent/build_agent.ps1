<#
    Build  tradelogger-mt5-sync.exe  — a single file your friends double-click.
    Run this on Windows (the .exe can only be built on Windows).

        powershell -ExecutionPolicy Bypass -File .\build_agent.ps1

    Output:  agent\dist\tradelogger-mt5-sync.exe
    Then host that file somewhere your friends can download it (GitHub
    Releases, a shared drive, Discord — it contains no secrets, only the
    public API + Supabase URLs).
#>
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $here
try {
    python -m pip install --upgrade pyinstaller MetaTrader5 requests

    python -m PyInstaller --onefile --console --clean --noconfirm `
        --name tradelogger-mt5-sync `
        --collect-submodules MetaTrader5 `
        --hidden-import requests `
        mt5_push_agent.py

    $exe = Join-Path $here "dist\tradelogger-mt5-sync.exe"
    if (Test-Path $exe) {
        Write-Host ""
        Write-Host "Built: $exe"
        Write-Host ("Size : {0:N1} MB" -f ((Get-Item $exe).Length / 1MB))
    } else {
        throw "Build finished but $exe is missing."
    }
}
finally {
    Pop-Location
}
