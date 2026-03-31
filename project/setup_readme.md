# TradeOS v5.1 — Setup Guide

Panduan lengkap instalasi TradeOS dari nol di perangkat manapun (Windows).

---

## Arsitektur Singkat

```
[React :3000] ──► [C# API :5206] ──► [PostgreSQL :5432]
                        │
                        └──► [Python Sidecar :8001] ──► [MetaTrader 5]
```

---

## 1. Prasyarat Software

Install semua software berikut **sebelum** menjalankan `setup.bat`.

### 1.1 Python 3.12
- Download: https://www.python.org/downloads/release/python-3120/
- Pilih: **Windows installer (64-bit)**
- Saat install, **centang** "Add Python to PATH"
- Verifikasi: `python --version` → harus `3.12.x`

> MetaTrader5 Python library hanya tersedia di **Windows + Python 3.12**.

### 1.2 .NET 8 SDK
- Download: https://dotnet.microsoft.com/download/dotnet/8.0
- Pilih: **.NET 8.0 SDK (64-bit)**
- Verifikasi: `dotnet --version` → harus `8.x.x`

### 1.3 Node.js LTS
- Download: https://nodejs.org/en/download
- Pilih: **LTS version (20.x atau 22.x), Windows 64-bit**
- Verifikasi: `node --version` → harus `v20.x` atau lebih baru
- Verifikasi: `npm --version`

### 1.4 PostgreSQL 15
- Download: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
- Pilih: **PostgreSQL 15.x, Windows x86-64**
- Saat instalasi:
  - Port: `5432` (default)
  - Password superuser: bebas, tapi catat — akan dimasukkan ke `.env`
  - Centang **pgAdmin 4** jika ingin GUI
- Verifikasi: service `postgresql-x64-15` harus Running di Windows Services

### 1.5 MetaTrader 5 Terminal
- Download dari broker kamu (contoh: Exness, IC Markets, dll.)
- Login ke akun trading (demo atau real)
- Wajib: **buka MT5 dan aktifkan AutoTrading** (tombol di toolbar)
- MT5 harus **tetap terbuka** saat TradeOS berjalan

---

## 2. Clone / Salin Project

Pastikan folder project ada di lokasi yang diinginkan, misal:
```
C:\Projects\tradeos-framework-v2\project\
```

Struktur yang diharapkan:
```
project/
├── backend/
├── frontend/
├── python-sidecar/
├── database/
├── setup.bat          ← installer otomatis
├── run_all.bat        ← launcher utama
└── .env.example
```

---

## 3. Konfigurasi Environment (.env)

### 3.1 Python Sidecar
Buka file `python-sidecar/.env` (buat jika belum ada, salin dari `.env.example`):

```env
# Database PostgreSQL
DATABASE_URL=postgresql://postgres:PASSWORD_KAMU@localhost:5432/tradeos

# MetaTrader 5
MT5_LOGIN=NOMOR_AKUN_MT5_KAMU
MT5_PASSWORD=PASSWORD_MT5_KAMU
MT5_SERVER=NAMA_SERVER_BROKER
# Contoh server Exness: Exness-MT5Trial6

# AI (opsional, untuk fitur AI)
ANTHROPIC_API_KEY=sk-ant-...

# Sidecar config
SIDECAR_PORT=8001
LOG_LEVEL=INFO
```

### 3.2 C# Backend
Buka `backend/TradeOS.Api/appsettings.json` dan sesuaikan:

```json
"ConnectionStrings": {
    "Default": "Host=localhost;Port=5432;Database=tradeos;Username=postgres;Password=PASSWORD_KAMU"
},
"Auth": {
    "Username": "admin",
    "PasswordHash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
}
```

> Password hash di atas adalah SHA256 dari `admin`. Untuk ganti password:
> ```python
> python -c "import hashlib; print(hashlib.sha256('password_baru'.encode()).hexdigest())"
> ```

---

## 4. Instalasi Otomatis

Jalankan **sekali** sebagai Administrator:

```
Klik kanan setup.bat → Run as Administrator
```

Script ini akan:
1. Mendeteksi Python, .NET, Node.js
2. Menginstall semua Python packages (`requirements.txt`)
3. Menginstall Node.js packages (`npm install`)
4. Memeriksa koneksi PostgreSQL
5. Membuat database `tradeos` dan menjalankan semua migrations (V1–V10)
6. Menjalankan `dotnet restore` untuk C# backend

---

## 5. Menjalankan Aplikasi

Setelah setup selesai, gunakan:

```
Klik kanan run_all.bat → Run as Administrator
```

Atau jalankan manual di 3 terminal terpisah:

**Terminal 1 — Python Sidecar:**
```batch
cd project\python-sidecar
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

**Terminal 2 — C# Backend:**
```batch
cd project\backend\TradeOS.Api
dotnet run
```

**Terminal 3 — React Frontend:**
```batch
cd project\frontend
npm run dev
```

---

## 6. Akses Aplikasi

| Service | URL | Keterangan |
|---------|-----|------------|
| Frontend | http://localhost:3000 | Dashboard utama |
| C# API Swagger | http://localhost:5206/swagger | API docs + testing |
| Python FastAPI Docs | http://localhost:8001/docs | Python endpoint docs |
| Hangfire Dashboard | http://localhost:5206/hangfire | Background jobs |

**Login default:**
- Username: `admin`
- Password: `admin`

---

## 7. Deployment dengan Docker (Opsional)

Jika ingin deploy semua services dalam container:

```bash
# Pastikan Docker Desktop terinstall dan berjalan
cd project
docker compose up -d
```

> Untuk Docker, MT5 tidak tersedia karena MT5 adalah software Windows-only.
> Gunakan mode local (tanpa Docker) untuk fitur trading live.

---

## 8. Troubleshooting

### Python: "MetaTrader5 package not available"
- Pastikan Python yang digunakan adalah versi 3.12 (bukan 3.11 atau 3.14)
- Jalankan: `python --version` di terminal
- Jika salah versi, edit `run_all.bat` dan ganti `PYTHON_HOME` ke path Python 3.12 yang benar

### PostgreSQL: "connection refused"
- Pastikan service PostgreSQL berjalan: `Services.msc` → cari `postgresql-x64-15`
- Pastikan password di `.env` dan `appsettings.json` sama

### MT5: "terminal_info not found" atau 503
- Buka MetaTrader 5 secara manual
- Aktifkan AutoTrading (tombol di toolbar)
- Pastikan sudah login ke akun broker

### npm install gagal
- Hapus folder `frontend/node_modules` lalu coba lagi
- Pastikan Node.js versi 20+: `node --version`

### dotnet build gagal
- Pastikan .NET 8 SDK terinstall: `dotnet --version`
- Jalankan `dotnet restore` di folder `backend/TradeOS.Api`

---

## 9. Struktur Port

```
:3000  → React frontend (Vite dev server)
:5206  → C# ASP.NET Core API
:8001  → Python FastAPI sidecar
:5432  → PostgreSQL
:6379  → Redis (Docker only)
```

---

## 10. Update Dependencies

Jika ada update package di masa depan:

```batch
# Python
cd project\python-sidecar
python -m pip install -r requirements.txt --upgrade

# Node.js
cd project\frontend
npm install

# .NET
cd project\backend\TradeOS.Api
dotnet restore
```
