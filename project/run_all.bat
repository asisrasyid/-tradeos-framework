@echo off
cd /d "%~dp0"
title TradeOS — Master Launcher

:: ── Set Python 3.12 path explicitly ───────────────────────────
set PYTHON_HOME=D:\Python312
set PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%PATH%

echo ============================================================
echo  TradeOS v5.1 — Master Launcher
echo ============================================================
echo.

:: ── 1. KILL existing processes on all service ports ──────────
echo [1/5] Killing existing processes on ports 8001, 5206, 3000...
for %%P in (8001 5206 3000) do (
    for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":%%P "') do (
        if not "%%a"=="0" (
            taskkill /F /PID %%a >nul 2>&1
        )
    )
)
timeout /t 1 /nobreak >nul

:: ── 2. CLEAR Python __pycache__ ──────────────────────────────
echo [2/5] Clearing Python __pycache__...
for /d /r "%~dp0python-sidecar" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)

:: ── 3. START Python sidecar (NO --reload to avoid spawn bugs) ─
echo [3/5] Starting Python sidecar on :8001...
start "TradeOS Python :8001" cmd /k "cd /d "%~dp0python-sidecar" && python -m uvicorn main:app --host 0.0.0.0 --port 8001"
timeout /t 4 /nobreak >nul

:: ── 4. START C# API ──────────────────────────────────────────
echo [4/5] Starting C# API on :5206...
start "TradeOS API :5206" cmd /k "cd /d "%~dp0backend\TradeOS.Api" && dotnet run"
timeout /t 2 /nobreak >nul

:: ── 5. START React Frontend ──────────────────────────────────
echo [5/5] Starting React frontend on :3000...
start "TradeOS Frontend :3000" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================================
echo  3 windows launched. Wait ~15s for all services to start.
echo  Frontend:    http://localhost:3000
echo  Python docs: http://localhost:8001/docs
echo  C# Swagger:  http://localhost:5206/swagger
echo ============================================================
echo.
pause
