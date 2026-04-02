# TradeOS — Panduan Cascade Engine

> Versi: v2.1 | Dibuat: 2026-04-02

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Perbedaan Cascade vs Aggressive](#cascade-vs-aggressive)
3. [Alur Kerja Engine (Lifecycle)](#alur-kerja-engine)
4. [Parameter Lengkap](#parameter-lengkap)
5. [Sistem Batch — Inti Strategi Cascade](#sistem-batch)
6. [Trend Analysis — M1 + M5 + M15 Vote](#trend-analysis)
7. [Topup Logic — Pyramiding vs Flip](#topup-logic)
8. [Hard SL Per Posisi](#hard-sl)
9. [MCGuard — Proteksi Equity Account](#mcguard)
10. [Profit Guard — Proteksi Per-Session](#profit-guard)
11. [Expected Value & Kalkulasi](#expected-value)
12. [Rekomendasi Setting](#rekomendasi-setting)
13. [Tampilan UI — Session Card](#tampilan-ui)
14. [Troubleshooting](#troubleshooting)

---

## 1. Gambaran Umum {#gambaran-umum}

Cascade Engine adalah **execution engine berbasis batch + pyramiding**. Ide dasarnya:

```
Buka batch awal saat trend terdeteksi
    ↓
Setiap N detik (eval_interval): cek apakah trend masih berlanjut
    ├─ Trend sama → topup (tambah posisi ke arah yang sama = pyramiding)
    ├─ Trend berbalik → flip (buka batch baru ke arah berlawanan)
    └─ Trend netral → tunggu, pakai last_tp_direction sebagai fallback
```

**Filosofi:** Ikuti momentum yang sudah terbukti. Tambahkan posisi saat tren terkonfirmasi, bukan saat baru mulai.

Engine berjalan di thread tersendiri, poll setiap `eval_interval` detik (default 300 = 5 menit), berkomunikasi dengan MT5 via HTTP ke `/python/mt5/*`.

---

## 2. Perbedaan Cascade vs Aggressive {#cascade-vs-aggressive}

| Aspek | Aggressive | Cascade |
|-------|-----------|---------|
| **Interval poll** | 2 detik | `eval_interval` (default 5 menit) |
| **Strategi** | Fill N layers terus-menerus, tutup satu-satu saat TP | Batch bertahap, pyramiding saat trend terkonfirmasi |
| **Buka ulang** | Otomatis segera setelah TP | Hanya saat eval — tidak ada fill per-posisi |
| **Komunikasi MT5** | Direct MT5 Python API | HTTP ke /python/mt5/* |
| **HMM Gate** | Ada (opsional) | Tidak ada |
| **Auto Direction** | Ada (P1-P4 priority + HMM vote) | Pure EMA vote M1+M5+M15 |
| **Cocok untuk** | High-frequency, scalping | Trend-following, swing session |
| **Risiko utama** | Banyak posisi kecil cepat, SL beruntun | Posisi menumpuk satu arah — satu flip besar bisa mahal |

---

## 3. Alur Kerja Engine (Lifecycle) {#alur-kerja-engine}

### Start Session

```
User klik START CASCADE
    ↓
Analisis trend awal: M1+M5+M15 majority vote
    ├─ NEUTRAL → retry setiap 5 detik, maksimal 2 menit
    │   └─ Masih NEUTRAL setelah 2 menit → session berhenti dengan error
    └─ BUY atau SELL → lanjut
    ↓
MCGuard pre-check
    ├─ DANGER atau EMERGENCY → session berhenti, tidak buka posisi
    └─ OK / CAUTION / WARNING → lanjut
    ↓
Buka initial_batch posisi ke arah yang terdeteksi
    ↓
Masuk eval loop (setiap eval_interval detik)
```

### Eval Loop (setiap eval_interval detik)

```
MCGuard check
    ├─ EMERGENCY → tutup semua posisi → stop session
    ├─ DANGER    → tutup 3 posisi terburuk → skip topup siklus ini
    ├─ WARNING   → block topup → lanjut loop
    └─ OK / CAUTION → lanjut
    ↓
Profit Guard check → jika trip → tutup semua → stop
    ↓
Sync positions (deteksi TP hit dari broker)
    ↓
Cek trend ulang: M1+M5+M15 vote
    ↓
Hard SL check (jika sl_loss_multiplier > 0)
    ↓
[TOPUP LOGIC — lihat seksi 7]
    ↓
Update status, tunggu eval_interval berikutnya
```

### Stop Session

```
User klik STOP  →  sess.active = False
    ↓
Thread berhenti di siklus berikutnya
    ↓
Hitung next_recommendation (EMA M1+M5+M15 saat itu)
    ↓
Session tetap di list (stopped) selama 30 menit, lalu dihapus otomatis
```

> **Catatan:** Saat session stop, **posisi yang sudah terbuka TIDAK otomatis ditutup**. Posisi tetap berjalan di MT5 dengan TP/SL broker sampai ditutup manual atau MCGuard/Profit Guard aktif.

---

## 4. Parameter Lengkap {#parameter-lengkap}

### Core Config

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `symbol` | XAUUSDm | Instrumen trading |
| `initial_batch` | 10 | Jumlah posisi yang dibuka di awal session |
| `topup_batch` | 5 | Posisi tambahan yang dibuka setiap kali topup |
| `volume` | 0.01 | Lot per posisi |
| `profit_target` | 2.0 | USD — digunakan sebagai threshold SL (bukan TP di broker). TP ditangani broker secara terpisah |
| `max_positions` | 30 | Batas total posisi terbuka (semua batch gabungan) |
| `eval_interval` | 300 | Detik antara setiap evaluasi (300 = 5 menit) |

### Hard SL

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `sl_loss_multiplier` | 1.0 | Tutup posisi jika floating loss ≥ N × profit_target. `0` = disabled |
| `hard_sl_pips` | 0.0 | SL tetap dalam pips ditempatkan di broker saat order. `0` = tidak ada broker SL |

### MCGuard

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `mc_level_pct` | 0.10 | Trigger saat free_margin ≤ 10% dari balance |
| `safety_multiplier` | 3.0 | Safety floor = mc_level × 3.0 |
| `emergency_multiplier` | 1.5 | Emergency floor = mc_level × 1.5 |

### Profit Guard

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `max_session_loss_usd` | 0.0 | Stop jika total loss (realized + floating) ≥ nilai ini. `0` = off |
| `max_drawdown_from_peak` | 0.0 | Stop jika profit turun N dollar dari peak. `0` = off |

---

## 5. Sistem Batch — Inti Strategi Cascade {#sistem-batch}

Setiap kali Cascade membuka posisi, ia membuat sebuah **DirectionBatch** — grup posisi yang dibuka sekaligus dalam satu arah pada satu momen.

```
Session dimulai:
    Batch-1: [#1001, #1002, #1003, #1004, #1005] direction=BUY  ← initial_batch=5

Eval ke-1: trend=BUY (sama)
    Batch-2: [#1006, #1007, #1008] direction=BUY  ← topup_batch=3 (pyramiding)

Eval ke-2: trend=SELL (berbalik)
    Batch-3: [#1009, #1010, #1011] direction=SELL  ← flip, topup_batch baru
    (Batch-1 dan Batch-2 masih jalan!)

Eval ke-3: trend=SELL (sama)
    Batch-4: [#1012, #1013, #1014] direction=SELL  ← topup pyramiding SELL
```

**Poin penting:**
- Flip **tidak menutup** batch lama — batch lama tetap jalan bersamaan
- Posisi dari batch BUY dan batch SELL bisa terbuka **bersamaan di MT5**
- Total posisi terbuka = jumlah tiket di semua batch aktif
- `max_positions` adalah hard cap — topup berhenti jika cap tercapai

### Batches di UI

Di session card, batch tampil sebagai chip kecil inline:
```
B×5  B×3  S×3  S×3
```
Artinya: 2 batch BUY (5 posisi + 3 posisi) dan 2 batch SELL (3 + 3 posisi).

---

## 6. Trend Analysis — M1 + M5 + M15 Vote {#trend-analysis}

Cascade menggunakan **EMA5/EMA10 crossover** pada 3 timeframe secara independen, lalu majority vote.

### Cara Kerja

```python
# Untuk setiap TF (M1, M5, M15):
EMA5  = exponential moving average periode 5 dari close
EMA10 = exponential moving average periode 10 dari close

if EMA5 > EMA10 → vote BUY
if EMA5 < EMA10 → vote SELL
else             → vote NEUTRAL

# Majority vote (minimal 2 dari 3 TF setuju):
if BUY_votes  ≥ 2 → BUY
if SELL_votes ≥ 2 → SELL
else               → NEUTRAL
```

### Implementasi EMA

Engine menggunakan EMA sejati (bukan SMA):
```
α = 2 / (period + 1)
EMA = EMA_prev × (1 - α) + price × α
Seed: rata-rata aritmatik dari `period` bar pertama
```

### NEUTRAL Handling

Jika vote menghasilkan NEUTRAL:
- **Saat awal session:** retry setiap 5 detik, maksimal 2 menit
- **Saat eval loop:** gunakan `last_tp_direction` sebagai fallback
  - `last_tp_direction` = arah dari batch yang terakhir kali ada posisi TP hit
  - Jika `last_tp_direction` kosong (tidak ada TP sama sekali) → skip topup siklus ini

```
Contoh NEUTRAL fallback:
  Eval ke-4: trend=NEUTRAL
  last_tp_direction = BUY (dari batch-2 yang sudah ada TP)
  → topup ke BUY tetap jalan (mengikuti momentum yang sudah terbukti)
```

---

## 7. Topup Logic — Pyramiding vs Flip {#topup-logic}

Setiap eval, engine memutuskan:

```
Total posisi terbuka ≥ max_positions?
    → "Max positions reached" — tidak ada topup

Trend == current_direction?
    → PYRAMIDING: buka topup_batch posisi ke arah yang sama

Trend != current_direction?
    → FLIP: ganti current_direction, buka topup_batch posisi ke arah baru
    (posisi lama dari arah sebelumnya TIDAK ditutup)

MCGuard == CAUTION?
    → Topup dibatasi jadi 2 posisi (bukan topup_batch penuh)

MCGuard == WARNING?
    → Topup di-block sepenuhnya siklus ini
```

### Contoh Numeric

```
Setting: initial_batch=5, topup_batch=3, max_positions=15, eval_interval=300

T=0:   trend=BUY → buka 5 posisi BUY (total: 5)
T=5m:  trend=BUY → topup 3 BUY (total: 8)
T=10m: trend=BUY → topup 3 BUY (total: 11)
T=15m: trend=SELL → flip: buka 3 SELL, current_direction=SELL (total: 14)
T=20m: trend=SELL → topup 1 SELL (max_positions=15, available=1) (total: 15)
T=25m: max_positions reached → tidak ada topup
```

---

## 8. Hard SL Per Posisi {#hard-sl}

Cascade memiliki dua mekanisme SL:

### 1. Broker Hard SL (hard_sl_pips)

```
hard_sl_pips = 50
→ Setiap order ditempatkan dengan SL 50 pips dari harga masuk
→ Broker akan otomatis menutup jika harga mencapai SL tersebut
```

Ini adalah SL "keras" di sisi broker — tidak bergantung pada polling engine.

### 2. Monitored SL (sl_loss_multiplier)

```
sl_loss_multiplier = 1.0, profit_target = 2.0
→ threshold = 1.0 × $2.00 = $2.00

Engine cek setiap eval: jika floating_loss posisi ≥ $2.00 → tutup paksa
```

Ini di-check di sisi Python setiap eval_interval — ada jeda waktu, tapi tidak bergantung pada broker SL placement.

> **Rekomendasi:** Gunakan keduanya bersama. `hard_sl_pips` sebagai safety net broker-side, `sl_loss_multiplier` sebagai kontrol dollar-based.

---

## 9. MCGuard — Proteksi Equity Account {#mcguard}

MCGuard selalu aktif di Cascade (tidak ada toggle — berbeda dengan Aggressive yang opsional).

### Kalkulasi Level

```
mc_level     = balance × mc_level_pct
             = $1000 × 0.10 = $100

safety_floor = mc_level × safety_multiplier
             = $100 × 3.0 = $300

emergency_floor = mc_level × emergency_multiplier
                = $100 × 1.5 = $150
```

### Level dan Tindakan

| Level | Kondisi | Tindakan Engine |
|-------|---------|----------------|
| `OK` | free_margin > $300 | Normal, topup jalan |
| `CAUTION` | $300 < free_margin ≤ $450 | Topup dibatasi 2 posisi |
| `WARNING` | $100 < free_margin ≤ $300 | Topup di-block |
| `DANGER` | free_margin ≤ $100 | Tutup 3 posisi paling rugi, skip topup |
| `EMERGENCY` | equity ≤ $150 | Tutup SEMUA posisi → stop session |

### Koordinasi Multi-Session

Jika multiple session (Aggressive + Cascade) aktif bersamaan dan semua mencapai EMERGENCY, hanya **satu session** yang mengeksekusi close-all (claim token eksklusif via `equity_cache`). Session lain langsung stop tanpa close. Ini mencegah double-close yang bisa mengacaukan akun.

---

## 10. Profit Guard — Proteksi Per-Session {#profit-guard}

### Floor Loss (max_session_loss_usd)

```
max_session_loss_usd = 15.0

Dihitung: realized_profit + floating_pnl (semua posisi terbuka session ini)
Jika total ≤ -$15 → tutup semua posisi → stop session
```

### Peak Drawdown (max_drawdown_from_peak)

```
max_drawdown_from_peak = 8.0

Engine pantau peak_profit sepanjang session
Jika current_net < peak_profit - $8 → tutup semua → stop session

Contoh:
  Profit naik ke $12 (peak = $12)
  Profit turun ke $3.50 ($12 - $3.50 = $8.50 > $8) → STOP
```

---

## 11. Expected Value & Kalkulasi {#expected-value}

Cascade berbeda dari Aggressive dalam cara kalkulasi EV — karena posisi menumpuk dan tidak semua TP di waktu yang sama.

### Contoh Skenario (XAUUSDm)

```
Setting: initial_batch=5, topup_batch=3, vol=0.01, profit_target=2.0, sl=1.0×

Skenario trending BUY:
  T=0:   buka 5 BUY @ $1800
  T=5m:  trend BUY, topup 3 BUY → total 8 posisi
  T=10m: trend BUY, topup 3 BUY → total 11 posisi
  T=15m: 11 posisi semua TP @ $2.00 = +$22.00

Skenario trend reversal:
  T=0:   buka 5 BUY @ $1800
  T=5m:  trend flip ke SELL, buka 3 SELL (5 BUY masih jalan)
  T=10m: 5 BUY mencapai SL = 5 × -$2.00 = -$10.00
          3 SELL TP = 3 × +$2.00 = +$6.00
  Net = -$4.00 siklus ini
```

**Kesimpulan:** Cascade sangat profitable saat trending panjang, tapi mahal saat sering flip. Gunakan `max_session_loss_usd` dan `max_drawdown_from_peak` untuk batasi kerugian skenario kedua.

### Break-even Winrate

```
sl_loss_multiplier = 1.0 → break-even di 50% (sama dengan Aggressive)
sl_loss_multiplier = 2.0 → break-even di 66.7%
```

---

## 12. Rekomendasi Setting {#rekomendasi-setting}

### XAUUSDm — Trending Mode (Recommended Start)

```
symbol                 = XAUUSDm
initial_batch          = 5
topup_batch            = 3
volume                 = 0.01
profit_target          = 2.0
sl_loss_multiplier     = 1.0
hard_sl_pips           = 0
max_positions          = 20
eval_interval          = 300
mc_level_pct           = 0.10
safety_multiplier      = 3.0
emergency_multiplier   = 1.5
max_session_loss_usd   = 15.0
max_drawdown_from_peak = 8.0
```

### XAUUSDm — Mode Konservatif

```
initial_batch          = 3
topup_batch            = 2
volume                 = 0.01
profit_target          = 2.0
sl_loss_multiplier     = 1.0
max_positions          = 10
eval_interval          = 600      ← lebih sabar, 10 menit
max_session_loss_usd   = 8.0
max_drawdown_from_peak = 5.0
```

### BTCUSDm

```
initial_batch          = 3
topup_batch            = 2
volume                 = 0.01
profit_target          = 5.0      ← target lebih besar, volatilitas tinggi
sl_loss_multiplier     = 1.0
max_positions          = 10
eval_interval          = 300
max_session_loss_usd   = 20.0
max_drawdown_from_peak = 10.0
```

### Forex (EURUSD, GBPUSD)

```
initial_batch          = 5
topup_batch            = 3
volume                 = 0.10
profit_target          = 1.0
sl_loss_multiplier     = 1.0
max_positions          = 20
eval_interval          = 180      ← lebih cepat, spread kecil
max_session_loss_usd   = 10.0
max_drawdown_from_peak = 5.0
```

---

## 13. Tampilan UI — Session Card {#tampilan-ui}

### Row 1: Identitas + Status

```
● XAUUSD  [BUY]  [OK]                          Up 45m30s  [STOP]
  │         │      │                               │
  dot       arah   MCGuard level               uptime
  hijau=aktif
```

### Row 2: Stats + P&L

```
11/20 open  TP:24  SL:3  EMG:0   B×5  B×3  S×3  |  +$22.50
                                  batch chips        P&L utama
                                                     (15px, bold)
             ▼ jika ada floating:                    float +$1.20
             ▼ jika ada peak:                        peak $25.00
```

**Batch chips** menunjukkan posisi terbuka per batch:
- `B×5` = 1 batch BUY dengan 5 posisi masih terbuka
- `S×3` = 1 batch SELL dengan 3 posisi masih terbuka

### Row 3: Last Action

```
Topup 3x BUY (pyramiding)
```

Atau jika error:
```
ERR: MT5 connection lost: 5 consecutive failures
```

### Row 4: Next Session Recommendation (hanya saat stopped)

```
Next session:  [BUY]  M1+M5+M15 vote
```

---

## 14. Troubleshooting {#troubleshooting}

### Session langsung berhenti "No clear trend"

**Penyebab:** Saat start, M1+M5+M15 vote tidak mencapai majority dalam 2 menit.

**Solusi:**
- Tunggu kondisi market lebih trending (hindari jam konsolidasi/news time)
- Kurangi `eval_interval` bukan solusinya — ini tentang kondisi awal
- Cek apakah MT5 terhubung dan OHLC data tersedia

---

### Posisi menumpuk terlalu banyak, max_positions cepat tercapai

**Penyebab:** `initial_batch` + `topup_batch` terlalu besar relatif terhadap `max_positions`.

**Solusi:**
```
Kurangi initial_batch atau topup_batch
Naikkan max_positions
Naikkan eval_interval (beri waktu lebih lama antar topup)
```

---

### Banyak flip, session terus rugi

**Penyebab:** Market choppy/ranging — trend berganti terus setiap eval. Cascade tidak cocok untuk kondisi ini.

**Solusi:**
- Hentikan session, tunggu market trending
- Naikkan `eval_interval` ke 600+ agar flip tidak terlalu sering
- Aktifkan `max_session_loss_usd` untuk membatasi kerugian otomatis
- Pertimbangkan gunakan Aggressive engine (lebih cocok untuk choppy)

---

### Posisi dari batch lama tidak pernah TP, floating loss terus naik

**Penyebab:** Trend berbalik dan batch lama (arah berlawanan) tidak ditutup secara otomatis.

**Solusi:**
- Aktifkan `sl_loss_multiplier = 1.0` untuk hard SL per posisi
- Aktifkan `hard_sl_pips` untuk broker-side SL sebagai safety net
- Set `max_drawdown_from_peak` untuk stop session saat drawdown terlalu dalam

---

### Session zombie (status running, tidak ada topup)

**Penyebab:** Koneksi MT5 gagal. Setelah **5 kegagalan berturut-turut**, session auto-stop.

**Tanda:** `error` field berisi `MT5 connection lost`.

**Solusi:**
1. Cek koneksi MT5 terminal
2. Restart MT5
3. Start session baru

---

### MCGuard terus CAUTION / WARNING, topup terus terbatas

**Penyebab:** Free margin mepet karena terlalu banyak posisi terbuka.

**Solusi:**
- Kurangi `volume` per posisi
- Kurangi `max_positions`
- Kurangi `initial_batch` dan `topup_batch`
- Tutup beberapa posisi manual via MT5 Terminal

---

*TradeOS Cascade Engine v2.1 — Batch-based pyramiding, M1+M5+M15 EMA vote, Hard SL, MCGuard 4 levels, Profit Guard, Connection watchdog.*
