<#
    Registers the TradeLogger MT5 push agent as a Windows scheduled task that
    runs every 15 minutes while you are logged in.

    Run this ONCE, from an ordinary (non-admin) PowerShell, in this folder:

        powershell -ExecutionPolicy Bypass -File .\register_task.ps1

    To remove it later:

        Unregister-ScheduledTask -TaskName "TradeLogger MT5 Push Agent" -Confirm:$false
#>

$ErrorActionPreference = "Stop"

$here   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script = Join-Path $here "mt5_push_agent.py"
$config = Join-Path $here "mt5_agent_config.json"

if (-not (Test-Path $config)) {
    Write-Error "mt5_agent_config.json not found. Copy the .example.json file first and fill it in."
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Error "Python not found on PATH. Install Python 3 first." }

$taskName = "TradeLogger MT5 Push Agent"

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "`"$script`" --once --config `"$config`"" `
    -WorkingDirectory $here

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Reads MT5 and pushes deals to TradeLogger. Read-only, no order path." `
    -Force | Out-Null

Write-Host "Registered scheduled task: '$taskName' (every 15 min)."
Write-Host "Run it now with:  Start-ScheduledTask -TaskName `"$taskName`""
Write-Host "Check it worked:  python `"$script`" --check"
