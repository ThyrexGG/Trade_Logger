# v3 - Run in an Administrator PowerShell.
# Turns on command-line process auditing (event 4688), then on every terminal64
# spawn it dumps the matching 4688 record: real creator process + command line,
# even when that creator exits in microseconds.
$ErrorActionPreference = 'Continue'
$log = 'C:\Users\Asus\Desktop\Trade_Logger\mt5_launch_watch.txt'
function Write-Log($m) { Add-Content -Path $log -Value ("[" + (Get-Date -Format o) + "] " + $m) }

Write-Log "=== watcher v3 starting ==="

try {
    & auditpol /set /subcategory:"Process Creation" /success:enable /failure:enable | Out-Null
    New-Item -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit' -Force -EA SilentlyContinue | Out-Null
    Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit' `
        -Name 'ProcessCreationIncludeCmdLine_Enabled' -Type DWord -Value 1 -Force
    Write-Log "4688 command-line auditing enabled"
    Write-Host "Command-line auditing ON."
} catch {
    Write-Log ("could not enable 4688 auditing: " + $_.Exception.Message)
    Write-Host "WARNING: could not enable 4688 auditing. $($_.Exception.Message)"
}

$q = "SELECT * FROM Win32_ProcessStartTrace WHERE ProcessName='terminal64.exe' OR ProcessName='metatester64.exe'"
try {
    Register-WmiEvent -Query $q -SourceIdentifier MT5Start -Action {
        $log = 'C:\Users\Asus\Desktop\Trade_Logger\mt5_launch_watch.txt'
        $e = $Event.SourceEventArgs.NewEvent
        Add-Content $log ""
        Add-Content $log ("[" + (Get-Date -Format o) + "]  " + [string]$e.ProcessName + " pid " + [int]$e.ProcessID + "  <- ppid " + [int]$e.ParentProcessID + "  session " + $e.SessionID)
        Start-Sleep -Milliseconds 800
        try {
            $evs = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4688; StartTime=(Get-Date).AddSeconds(-8)} -MaxEvents 80 -ErrorAction Stop
        } catch { Add-Content $log ("    (no 4688 yet: " + $_.Exception.Message + ")"); $evs = @() }
        foreach ($ev in $evs) {
            $x = [xml]$ev.ToXml()
            $d = @{}
            foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = [string]$n.'#text' }
            if ($d['NewProcessName'] -match 'terminal64|metatester') {
                Add-Content $log ("    4688 NEW  : " + $d['NewProcessName'])
                Add-Content $log ("         cmd  : " + $d['CommandLine'])
                Add-Content $log ("         by   : " + $d['ParentProcessName'] + "  (creator pid " + $d['ProcessId'] + ")")
                Add-Content $log ("         who  : " + $d['SubjectUserName'] + "   elev: " + $d['TokenElevationType'])
            }
        }
    } -ErrorAction Stop | Out-Null
    Write-Host "Armed. Leave this window open. Ctrl-C to stop."
    Write-Log "armed"
} catch {
    Write-Log ("register failed: " + $_.Exception.Message)
    Write-Host "Register failed - Administrator window? $($_.Exception.Message)"
    return
}

while ($true) { Start-Sleep -Seconds 30 }
