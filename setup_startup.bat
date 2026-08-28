@echo off
set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%SCRIPT_DIR%run_auto_sync_hidden.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\TradeLogger_AutoSync.lnk"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_PATH%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

echo [SUCCESS] TradeLogger Auto-Sync has been added to your Windows Startup folder!
echo It will now run silently in the background every time you turn on your PC.
echo.
pause
