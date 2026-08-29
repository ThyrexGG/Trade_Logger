Set WshShell = CreateObject("WScript.Shell")
' Run FastAPI backend completely hidden in background (0 = hide window)
WshShell.Run "python -m uvicorn server:app --host 127.0.0.1 --port 8000", 0, False
WScript.Sleep 2000
' Open Trade Logger Pro in default browser
WshShell.Run "http://127.0.0.1:8000"
