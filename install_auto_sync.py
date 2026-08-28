import os
import subprocess

vbs_path = os.path.abspath("run_auto_sync_hidden.vbs")
cwd = os.path.abspath(".")
startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
shortcut_path = os.path.join(startup_folder, "TradeLogger_AutoSync.lnk")

ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut_path}')
$s.TargetPath = 'wscript.exe'
$s.Arguments = '"{vbs_path}"'
$s.WorkingDirectory = '{cwd}'
$s.Save()
"""

with open("temp_shortcut.ps1", "w", encoding="utf-8") as f:
    f.write(ps_script)

subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "temp_shortcut.ps1"], check=True)
if os.path.exists("temp_shortcut.ps1"):
    os.remove("temp_shortcut.ps1")

print(f"[SUCCESS] Auto-Sync shortcut installed to Windows Startup: {shortcut_path}")
