@echo off
cd /d "%~dp0"
echo ============================================================
echo  TradeOS Python Sidecar
echo ============================================================

echo [1/3] Killing any existing process on port 8001...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8001 "') do (
    if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] Clearing __pycache__...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)

echo [3/3] Starting on http://localhost:8001
echo Docs: http://localhost:8001/docs
echo Press Ctrl+C to stop.
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8001
