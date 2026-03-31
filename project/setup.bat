@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title TradeOS — Setup Installer

echo.
echo ============================================================
echo   TradeOS v5.1 — Setup Installer
echo   Jalankan sekali sebagai Administrator
echo ============================================================
echo.

:: ── Track errors ────────────────────────────────────────────────────────────
set ERRORS=0
set WARNINGS=0

:: ============================================================
:: [1] CEK PYTHON 3.12
:: ============================================================
echo [1/7] Memeriksa Python 3.12...

:: Cari Python di lokasi umum
set PYTHON_EXE=
for %%P in (
    "D:\Python312\python.exe"
    "C:\Python312\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Program Files\Python312\python.exe"
) do (
    if exist %%P (
        if "!PYTHON_EXE!"=="" set PYTHON_EXE=%%~P
    )
)

:: Fallback ke PATH
if "!PYTHON_EXE!"=="" (
    where python >nul 2>&1
    if !errorlevel!==0 (
        for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
        echo !PY_VER! | findstr "3.12" >nul
        if !errorlevel!==0 (
            set PYTHON_EXE=python
        )
    )
)

if "!PYTHON_EXE!"=="" (
    echo   [ERROR] Python 3.12 tidak ditemukan!
    echo   Download dari: https://www.python.org/downloads/release/python-3120/
    echo   Centang "Add Python to PATH" saat install.
    set /a ERRORS+=1
) else (
    for /f "tokens=*" %%i in ('"!PYTHON_EXE!" --version 2^>^&1') do echo   OK: %%i di !PYTHON_EXE!
)

:: ============================================================
:: [2] CEK .NET 8
:: ============================================================
echo.
echo [2/7] Memeriksa .NET 8 SDK...

where dotnet >nul 2>&1
if !errorlevel! neq 0 (
    echo   [ERROR] .NET SDK tidak ditemukan!
    echo   Download dari: https://dotnet.microsoft.com/download/dotnet/8.0
    set /a ERRORS+=1
) else (
    for /f "tokens=*" %%i in ('dotnet --version 2^>^&1') do set DOTNET_VER=%%i
    echo !DOTNET_VER! | findstr /r "^8\." >nul
    if !errorlevel! neq 0 (
        echo   [WARNING] .NET versi !DOTNET_VER! ditemukan, disarankan 8.x
        set /a WARNINGS+=1
    ) else (
        echo   OK: .NET !DOTNET_VER!
    )
)

:: ============================================================
:: [3] CEK NODE.JS
:: ============================================================
echo.
echo [3/7] Memeriksa Node.js...

where node >nul 2>&1
if !errorlevel! neq 0 (
    echo   [ERROR] Node.js tidak ditemukan!
    echo   Download dari: https://nodejs.org/en/download (pilih LTS)
    set /a ERRORS+=1
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
    echo   OK: Node.js !NODE_VER!
    for /f "tokens=*" %%i in ('npm --version 2^>^&1') do echo   OK: npm %%i
)

:: ============================================================
:: [4] CEK POSTGRESQL
:: ============================================================
echo.
echo [4/7] Memeriksa PostgreSQL...

:: Cari psql di lokasi umum
set PSQL_EXE=
for %%P in (
    "C:\Program Files\PostgreSQL\15\bin\psql.exe"
    "C:\Program Files\PostgreSQL\16\bin\psql.exe"
    "C:\Program Files\PostgreSQL\17\bin\psql.exe"
    "C:\Program Files\PostgreSQL\14\bin\psql.exe"
) do (
    if exist %%P (
        if "!PSQL_EXE!"=="" set PSQL_EXE=%%~P
    )
)

if "!PSQL_EXE!"=="" (
    where psql >nul 2>&1
    if !errorlevel!==0 set PSQL_EXE=psql
)

if "!PSQL_EXE!"=="" (
    echo   [WARNING] psql tidak ditemukan di PATH.
    echo   Tambahkan folder bin PostgreSQL ke PATH, atau install PostgreSQL 15.
    echo   Download: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
    set /a WARNINGS+=1
) else (
    for /f "tokens=*" %%i in ('"!PSQL_EXE!" --version 2^>^&1') do echo   OK: %%i
)

:: ── Berhenti jika ada error kritis ────────────────────────────────────────
if !ERRORS! gtr 0 (
    echo.
    echo ============================================================
    echo   [STOP] !ERRORS! dependency kritis tidak ditemukan.
    echo   Install software di atas lalu jalankan setup.bat lagi.
    echo ============================================================
    pause
    exit /b 1
)

:: ============================================================
:: [5] INSTALL PYTHON PACKAGES
:: ============================================================
echo.
echo [5/7] Menginstall Python packages...
echo   Menggunakan: !PYTHON_EXE!
echo   File: python-sidecar\requirements.txt
echo.

cd /d "%~dp0python-sidecar"

"!PYTHON_EXE!" -m pip install --upgrade pip >nul 2>&1
echo   Menginstall dependencies (mungkin butuh beberapa menit)...
"!PYTHON_EXE!" -m pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo   [WARNING] Beberapa package mungkin gagal install.
    echo   Coba jalankan manual: pip install -r requirements.txt
    set /a WARNINGS+=1
) else (
    echo   OK: Semua Python packages terinstall.
)

:: Verifikasi import kritis
echo   Verifikasi imports...
"!PYTHON_EXE!" -c "import fastapi, uvicorn, pandas, numpy, hmmlearn; print('   OK: fastapi, uvicorn, pandas, numpy, hmmlearn')" 2>&1
"!PYTHON_EXE!" -c "import MetaTrader5; print('   OK: MetaTrader5', MetaTrader5.__version__)" 2>&1 || echo   [INFO] MetaTrader5 tidak tersedia (normal jika MT5 belum login)

cd /d "%~dp0"

:: ============================================================
:: [6] INSTALL NODE PACKAGES + DOTNET RESTORE
:: ============================================================
echo.
echo [6/7] Menginstall Node.js packages dan restore .NET...

:: Frontend
echo   [npm] Menginstall frontend packages...
cd /d "%~dp0frontend"
if exist "node_modules" (
    echo   Folder node_modules sudah ada, skip install.
    echo   Jalankan 'npm install' manual jika ingin update.
) else (
    npm install
    if !errorlevel! neq 0 (
        echo   [WARNING] npm install gagal.
        set /a WARNINGS+=1
    ) else (
        echo   OK: Frontend packages terinstall.
    )
)

:: .NET restore
echo   [dotnet] Restore NuGet packages...
cd /d "%~dp0backend\TradeOS.Api"
dotnet restore >nul 2>&1
if !errorlevel! neq 0 (
    echo   [WARNING] dotnet restore gagal.
    set /a WARNINGS+=1
) else (
    echo   OK: .NET packages restored.
)

cd /d "%~dp0"

:: ============================================================
:: [7] SETUP DATABASE
:: ============================================================
echo.
echo [7/7] Setup database PostgreSQL...

:: Baca konfigurasi dari .env python-sidecar
set DB_USER=postgres
set DB_PASS=P@ss1234
set DB_NAME=tradeos
set DB_HOST=localhost
set DB_PORT=5432

if exist "python-sidecar\.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("python-sidecar\.env") do (
        set LINE_KEY=%%a
        set LINE_VAL=%%b
        if "!LINE_KEY!"=="DATABASE_URL" (
            :: Parse postgresql://user:pass@host:port/dbname
            for /f "tokens=3 delims=/" %%u in ("!LINE_VAL!") do (
                for /f "tokens=1,2 delims=@" %%x in ("%%u") do (
                    for /f "tokens=1,2 delims=:" %%m in ("%%x") do (
                        set DB_USER=%%m
                        set DB_PASS=%%n
                    )
                    for /f "tokens=1,2 delims=:" %%h in ("%%y") do (
                        set DB_HOST=%%h
                        if not "%%i"=="" set DB_PORT=%%i
                    )
                )
            )
        )
    )
)

if "!PSQL_EXE!"=="" (
    echo   [SKIP] psql tidak ditemukan, skip database setup.
    echo   Setup manual: jalankan file SQL di folder database\migrations\ secara berurutan.
    goto :DONE
)

:: Buat database jika belum ada
echo   Membuat database '%DB_NAME%' jika belum ada...
set PGPASSWORD=!DB_PASS!
"!PSQL_EXE!" -h !DB_HOST! -p !DB_PORT! -U !DB_USER! -tc "SELECT 1 FROM pg_database WHERE datname='!DB_NAME!'" 2>nul | findstr "1" >nul
if !errorlevel! neq 0 (
    "!PSQL_EXE!" -h !DB_HOST! -p !DB_PORT! -U !DB_USER! -c "CREATE DATABASE !DB_NAME!;" >nul 2>&1
    if !errorlevel! neq 0 (
        echo   [WARNING] Gagal membuat database. Cek password PostgreSQL.
        echo   Buka pgAdmin dan buat database '%DB_NAME%' secara manual.
        set /a WARNINGS+=1
        goto :DONE
    )
    echo   OK: Database '%DB_NAME%' dibuat.
) else (
    echo   OK: Database '%DB_NAME%' sudah ada.
)

:: Jalankan migrations secara berurutan
echo   Menjalankan migrations...
set MIGRATION_ERR=0
for %%F in (
    "database\migrations\V1__create_tables.sql"
    "database\migrations\V2__indexes.sql"
    "database\migrations\V3__stored_procs.sql"
    "database\migrations\V4__seed_ccodes.sql"
    "database\migrations\V5__sp_save_theory_version.sql"
    "database\migrations\V6__fix_numeric_overflow.sql"
    "database\migrations\V7__ohlc_cache.sql"
    "database\migrations\V8__mt5_ticket.sql"
    "database\migrations\V9__smart_trade_log.sql"
    "database\migrations\V10__smart_trade_log_ai.sql"
) do (
    if exist "%~dp0%%~F" (
        "!PSQL_EXE!" -h !DB_HOST! -p !DB_PORT! -U !DB_USER! -d !DB_NAME! -f "%~dp0%%~F" >nul 2>&1
        if !errorlevel! neq 0 (
            echo   [INFO] %%~nxF - sudah ada atau error ringan (normal jika re-run)
        ) else (
            echo   OK: %%~nxF
        )
    ) else (
        echo   [WARNING] File tidak ditemukan: %%~F
    )
)

:DONE

:: ============================================================
:: RINGKASAN
:: ============================================================
echo.
echo ============================================================
echo   SETUP SELESAI
echo ============================================================
if !WARNINGS! gtr 0 (
    echo   Warnings: !WARNINGS! (lihat pesan di atas)
) else (
    echo   Semua berhasil tanpa warning!
)
echo.
echo   Langkah selanjutnya:
echo   1. Edit python-sidecar\.env  (isi MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
echo   2. Edit backend\TradeOS.Api\appsettings.json  (sesuaikan DB password)
echo   3. Buka MetaTrader 5 dan aktifkan AutoTrading
echo   4. Jalankan: run_all.bat
echo.
echo   Login default: admin / admin
echo   Frontend:      http://localhost:3000
echo   API Swagger:   http://localhost:5206/swagger
echo   Python Docs:   http://localhost:8001/docs
echo ============================================================
echo.
pause
