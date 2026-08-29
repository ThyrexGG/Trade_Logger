@echo off
title Trade Logger Pro - Flutter & FastAPI Engine
color 0B

echo ===================================================
echo     STARTING TRADE LOGGER PRO FLUTTER ENGINE
echo ===================================================

echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000...
start "TradeLogger_FastAPI" python -m uvicorn server:app --host 127.0.0.1 --port 8000

timeout /t 3 /nobreak >nul

echo [2/2] Launching Flutter Application on Windows Desktop...
cd trade_logger_app
flutter run -d windows

pause
