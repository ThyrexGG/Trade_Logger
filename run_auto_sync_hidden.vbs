Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonwPath = "C:\Users\Asus\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
WshShell.Run """" & pythonwPath & """ """ & scriptDir & "\auto_sync.py""", 0, False
