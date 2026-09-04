' Launches the auto_sync.py cloud-sync daemon fully hidden (0 = no window).
' Referenced by the "TradeLogger_AutoSync" Startup-folder shortcut.
' (Restored — the file was removed in cleanup commit e133e7c while the Startup
'  shortcut still pointed at it, so the sync daemon had silently stopped.)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonwPath = "C:\Users\Asus\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = "pythonw.exe"   ' fall back to PATH
End If

WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & pythonwPath & """ """ & scriptDir & "\auto_sync.py""", 0, False
