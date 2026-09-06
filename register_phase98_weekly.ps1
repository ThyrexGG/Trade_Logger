# Registers a Windows Scheduled Task that runs the Phase 98 forward-evidence
# daemon once a day. The daemon itself only runs the harness when a weekly
# run is actually due (>= 7 days since the last snapshot), so a daily trigger
# is safe and robust to missed days / a sleeping laptop.
#
# Usage (from the repo folder):
#   powershell -ExecutionPolicy Bypass -File register_phase98_weekly.ps1
#
# To remove it:
#   Unregister-ScheduledTask -TaskName "TradeLogger Phase98 Forward Evidence" -Confirm:$false

$ErrorActionPreference = "Stop"

$repo = $PSScriptRoot
$python = (Get-Command python).Source
$script = Join-Path $repo "phase98_forward_daemon.py"
$taskName = "TradeLogger Phase98 Forward Evidence"

if (-not (Test-Path $script)) { throw "phase98_forward_daemon.py not found in $repo" }

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --once" -WorkingDirectory $repo

# Daily at 10:00 local; also catch up if the machine was off at trigger time.
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Runs the Phase 98 funding-carry forward-evidence harness weekly (daily check, weekly run). No execution." `
    -Force | Out-Null

Write-Host "Registered scheduled task: '$taskName'"
Write-Host "  runs: $python `"$script`" --once"
Write-Host "  trigger: daily 10:00 (the daemon runs the harness only when a weekly run is due)"
Write-Host ""
Write-Host "Check it:   Get-ScheduledTask -TaskName '$taskName'"
Write-Host "Run it now: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Remove it:  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host "Log:        $(Join-Path $repo 'phase98_daemon_log.txt')"
