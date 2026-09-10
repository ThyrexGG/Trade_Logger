<#
    Build  tradelogger-mt5-sync.exe  — a single file your friends double-click.
    Run this on Windows, from this folder, in the SAME PowerShell where
    `python` is your normal Python 3.14 (the one that runs the test suite):

        cd C:\Users\Asus\Desktop\Trade_Logger
        powershell -ExecutionPolicy Bypass -File agent\build_agent.ps1

    Output:  agent\dist\tradelogger-mt5-sync.exe
    Host that file wherever friends can download it (Drive, Discord, …) —
    it contains no secrets, only the public API URL.
#>
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $here
try {
    # MetaTrader5 is a compiled extension and the agent imports it inside a
    # try/except, so PyInstaller does not bundle it automatically — it (and its
    # numpy dependency) must be collected explicitly, or the .exe builds fine
    # but can't read MT5.
    python -c "import MetaTrader5, numpy" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "This Python is missing MetaTrader5 / numpy. Run:  pip install MetaTrader5 numpy   then retry (use the Python that runs your tests)."
    }

    python -m pip install --upgrade --quiet pyinstaller requests

    python -m PyInstaller --onefile --console --clean --noconfirm `
        --name tradelogger-mt5-sync `
        --collect-all MetaTrader5 `
        --collect-all numpy `
        --hidden-import MetaTrader5 `
        --hidden-import requests `
        mt5_push_agent.py

    $exe = Join-Path $here "dist\tradelogger-mt5-sync.exe"
    if (-not (Test-Path $exe)) { throw "Build finished but $exe is missing." }

    # sanity: the frozen exe must be able to import MetaTrader5
    $probe = & $exe --check 2>&1 | Out-String
    if ($probe -match "no MetaTrader5 module") {
        throw "Build is missing MetaTrader5. Check the PyInstaller warnings above."
    }

    Write-Host ""
    Write-Host "Built: $exe"
    Write-Host ("Size : {0:N1} MB" -f ((Get-Item $exe).Length / 1MB))
    Write-Host "MetaTrader5 bundled: OK"
}
finally {
    Pop-Location
}
