@echo off
echo ============================================
echo  TradeOS Python Sidecar — Setup
echo ============================================

:: Buat virtual environment kalau belum ada
if not exist ".venv" (
    echo [1/3] Membuat virtual environment...
    python -m venv .venv
) else (
    echo [1/3] Virtual environment sudah ada, skip.
)

:: Aktifkan venv
echo [2/3] Mengaktifkan virtual environment...
call .venv\Scripts\activate.bat

:: Install dependencies (dev = ringan, tanpa vectorbt/MetaTrader5)
echo [3/3] Installing packages dari requirements-dev.txt...
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

echo.
echo ============================================
echo  Setup selesai!
echo  Jalankan: start.bat
echo ============================================
pause
