# TradeOS v2.1 — Setup Guide

Panduan instalasi TradeOS dari nol di Windows.

---

## Arsitektur

```
[React :3000] ──► [C# ASP.NET Core :5206] ──► [PostgreSQL :5432]
                            │
                            └──► [Python Sidecar :8001] ──► [MetaTrader 5]
```

- **React** — UI dashboard (Live Trading, HMM Models, Backtest, dll.)
- **C# API** — Business logic, auth, database queries, bridge ke Python sidecar
- **Python Sidecar** — HMM engine, feature extraction, execution engines (Aggressive, Cascade, Smart)
- **PostgreSQL** — Database utama (OHLC cache, theories, patterns, trade logs)
- **MetaTrader 5** — Terminal trading broker (harus terbuka saat engine berjalan)

---

## 1. Prasyarat Software

Install semua berikut **sebelum** menjalankan `setup.bat`.

### Python 3.12

- Download: https://www.python.org/downloads/release/python-3120/
- Pilih: **Windows installer (64-bit)**
- Saat install, **centang** "Add Python to PATH"
- Verifikasi: `python --version` → harus `3.12.x`

> MetaTrader5 Python library hanya tersedia di **Windows + Python 3.12**. Versi lain tidak didukung.

### .NET 8 SDK

- Download: https://dotnet.microsoft.com/download/dotnet/8.0
- Pilih: **.NET 8.0 SDK (64-bit)**
- Verifikasi: `dotnet --version` → harus `8.x.x`

### Node.js LTS

- Download: https://nodejs.org/en/download
- Pilih: **LTS version (20.x atau 22.x), Windows 64-bit**
- Verifikasi: `node --version` → harus `v20.x` atau lebih baru

### PostgreSQL 15

- Download: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
- Pilih: **PostgreSQL 15.x, Windows x86-64**
- Saat instalasi:
  - Port: `5432` (default, jangan ganti)
  - Password superuser: bebas, tapi **catat** — akan dimasukkan ke `.env`
  - Optional: centang **pgAdmin 4** untuk GUI management
- Verifikasi: service `postgresql-x64-15` status **Running** di Windows Services

### MetaTrader 5 Terminal

- Download dari broker kamu (Exness, IC Markets, Tickmill, dll.)
- Login ke akun trading (demo atau real)
- **Wajib:** buka MT5 dan aktifkan **AutoTrading** (tombol hijau di toolbar)
- MT5 harus **tetap terbuka** selama TradeOS berjalan

---

## 2. Struktur Folder Project

```
project/
├── backend/
│   └── TradeOS.Api/         ← C# ASP.NET Core solution
├── frontend/                ← React + TypeScript + Vite
├── python-sidecar/          ← FastAPI + HMM + execution engines
│   ├── main.py              ← entry point, 13 routers
│   ├── routers/             ← endpoint handlers
│   ├── services/            ← core engine logic
│   ├── docs/                ← panduan penggunaan engine
│   ├── requirements.txt
│   └── .env                 ← konfigurasi (buat dari .env.example)
├── database/
│   └── migrations/          ← V1–V10 PostgreSQL migration files
├── setup.bat                ← installer otomatis (jalankan sekali)
├── run_all.bat              ← launcher semua service
└── setup_readme.md          ← file ini
```

---

## 3. Konfigurasi Environment

### 3.1 Python Sidecar — `python-sidecar/.env`

Buat file ini (salin dari `.env.example` jika ada):

```env
# PostgreSQL
DATABASE_URL=postgresql://postgres:PASSWORD_KAMU@localhost:5432/tradeos

# MetaTrader 5
MT5_LOGIN=NOMOR_AKUN
MT5_PASSWORD=PASSWORD_AKUN
MT5_SERVER=NAMA_SERVER_BROKER
# Contoh: Exness-MT5Trial6, ICMarketsSC-Demo, Tickmill-Demo

# AI — untuk fitur Smart Engine (opsional)
ANTHROPIC_API_KEY=sk-ant-...

# Sidecar
SIDECAR_PORT=8001
LOG_LEVEL=INFO
```

### 3.2 C# Backend — `backend/TradeOS.Api/appsettings.json`

```json
"ConnectionStrings": {
    "Default": "Host=localhost;Port=5432;Database=tradeos;Username=postgres;Password=PASSWORD_KAMU"
},
"Auth": {
    "Username": "admin",
    "PasswordHash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
}
```

> Hash di atas adalah SHA256 dari `admin`. Untuk ganti password:
> ```python
> python -c "import hashlib; print(hashlib.sha256('password_baru'.encode()).hexdigest())"
> ```

---

## 4. Instalasi Otomatis

Jalankan **sekali** sebagai Administrator:

```
Klik kanan setup.bat → Run as Administrator
```

Script akan:
1. Verifikasi Python 3.12, .NET 8, Node.js terpasang
2. Install semua Python packages dari `requirements.txt`
3. Install Node.js packages (`npm install`)
4. Cek koneksi PostgreSQL
5. Buat database `tradeos` dan jalankan semua migrations (V1–V10)
6. Jalankan `dotnet restore` untuk C# backend

---

## 5. Menjalankan Aplikasi

### Cara Otomatis

```
Klik kanan run_all.bat → Run as Administrator
```

### Cara Manual (3 terminal terpisah)

**Terminal 1 — Python Sidecar:**
```batch
cd project\python-sidecar
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
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
| Frontend (UI) | http://localhost:3000 | Dashboard utama TradeOS |
| C# API Swagger | http://localhost:5206/swagger | REST API docs + testing |
| Python Sidecar Docs | http://localhost:8001/docs | FastAPI endpoint docs |
| Hangfire Dashboard | http://localhost:5206/hangfire | Background jobs |

**Login default:**
- Username: `admin`
- Password: `admin`

---

## 7. Struktur Port

```
:3000  → React frontend (Vite dev server)
:5206  → C# ASP.NET Core API
:8001  → Python FastAPI sidecar (internal only)
:5432  → PostgreSQL
:6379  → Redis (Docker only, tidak digunakan di setup lokal)
```

---

## 8. Docker (Opsional)

Untuk deploy semua services dalam container:

```bash
cd project
docker compose up -d
```

> **Catatan:** MetaTrader 5 adalah aplikasi Windows-only — tidak tersedia di Docker.
> Fitur trading live (engine Aggressive/Cascade) tidak bisa digunakan di mode Docker.
> Docker hanya cocok untuk testing backend/frontend tanpa MT5.

---

## 9. Urutan Start yang Benar

Jika start manual, urutan ini penting:

```
1. Buka MetaTrader 5 → login → aktifkan AutoTrading
2. Pastikan PostgreSQL service running
3. Jalankan Python Sidecar terlebih dahulu
4. Jalankan C# Backend
5. Jalankan React Frontend
```

Engine trading (Aggressive, Cascade) hanya bisa dijalankan setelah **Python Sidecar + MT5 keduanya aktif**.

---

## 10. Troubleshooting

### "MetaTrader5 package not available"
- Python yang digunakan bukan versi 3.12
- Jalankan `python --version` untuk cek
- Edit `run_all.bat`, sesuaikan path ke Python 3.12 yang benar

### PostgreSQL: "connection refused"
- Cek service: `Win + R` → `services.msc` → cari `postgresql-x64-15` → pastikan **Running**
- Pastikan password di `.env` dan `appsettings.json` **sama persis**

### MT5: "terminal not found" / 503 dari endpoint `/python/mt5/*`
- Buka MetaTrader 5 manual, login ke akun
- Aktifkan AutoTrading (tombol hijau di toolbar)
- Jika sudah terbuka tapi masih error: restart Python Sidecar

### npm install gagal
- Hapus folder `frontend/node_modules` lalu jalankan ulang
- Verifikasi Node.js: `node --version` → harus 20+

### dotnet build / restore gagal
- Verifikasi: `dotnet --version` → harus `8.x.x`
- Coba: `dotnet restore` di folder `backend/TradeOS.Api`

### Engine tidak bisa start (500 dari API)
- Cek Python Sidecar berjalan: buka http://localhost:8001/docs
- Cek log terminal Python untuk error detail
- Pastikan MT5 sudah terbuka dan login

### OHLC data tidak muncul
- Pastikan MT5 terhubung ke server broker (icon hijau di kanan bawah MT5)
- Background sync dimulai otomatis saat Python Sidecar start — tunggu 30 detik
- Cek status sync di halaman UI: bagian OHLC Data Sync

---

## 11. Update Dependencies

```batch
# Python packages
cd project\python-sidecar
python -m pip install -r requirements.txt --upgrade

# Node.js packages
cd project\frontend
npm install

# .NET packages
cd project\backend\TradeOS.Api
dotnet restore
```

---

## 12. Referensi Dokumentasi Engine

Panduan penggunaan engine trading ada di `python-sidecar/docs/`:

| File | Isi |
|------|-----|
| `guide_hmm_complete.md` | Cara kerja HMM: training, pattern, theory, backtest, signal engine |
| `guide_trade_aggressive.md` | Panduan Aggressive Engine v2.1: semua parameter, HMM Gate, direction logic |
| `guide_trade_cascade.md` | Panduan Cascade Engine v2.1: batch system, pyramiding, MCGuard |
