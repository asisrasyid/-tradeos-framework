# TradeOS — Panduan Trading: Aggressive & Cascade Engine

> Versi: v2.1 | Diperbarui: 2026-03-28

---

## Daftar Isi

1. [Konsep Dasar](#konsep-dasar)
2. [Expected Value (EV) — Matematika Profitabilitas](#expected-value)
3. [Aggressive Engine](#aggressive-engine)
4. [Cascade Engine](#cascade-engine)
5. [HMM Filter — Pre-condition Gate](#hmm-filter)
6. [MCGuard — Proteksi Equity](#mcguard)
7. [Profit Guard — Proteksi Session](#profit-guard)
8. [Rekomendasi Setting per Instrumen](#rekomendasi-setting)
9. [Troubleshooting](#troubleshooting)

---

## 1. Konsep Dasar {#konsep-dasar}

TradeOS menjalankan tiga engine yang dapat beroperasi secara bersamaan:

| Engine | Strategi | Cocok untuk |
|--------|----------|-------------|
| **Aggressive** | Buka N layer sekaligus, tutup tiap layer saat profit_target tercapai, buka ulang | Trending market, high-frequency |
| **Cascade** | Buka initial_batch, topup saat trend terkonfirmasi | Trend-following dengan DCA |
| **Signal (HMM)** | Deteksi pola HMM, hasilkan sinyal BUY/SELL | Sumber sinyal untuk Aggressive/Cascade |

**Prinsip utama:** Aggressive dan Cascade adalah *execution engines*. Signal Engine adalah *filter/gate* opsional yang meningkatkan selektivitas entry.

---

## 2. Expected Value (EV) — Matematika Profitabilitas {#expected-value}

### Formula

```
EV per siklus = (WinRate × Profit) - (LossRate × Loss)
```

Dengan parameter default (10 layers, profit_target = $0.50, sl_loss_multiplier = 1.0):

```
Profit per siklus  = 10 layers × $0.50 = $5.00
Loss per siklus    = 10 layers × ($0.50 × 1.0) = $5.00
```

| sl_loss_multiplier | Loss per siklus | Win rate break-even |
|--------------------|-----------------|---------------------|
| 0.0 (disabled)     | $0              | Engine tidak pernah stop via SL |
| **1.0 (default)**  | $5.00           | **50% — realistis** |
| 2.0                | $10.00          | 66.7% |
| 3.0                | $15.00          | 75% — sangat sulit |

> **Rekomendasi:** Gunakan `sl_loss_multiplier = 1.0`. Dengan winrate 50-55% dari trend filter, EV positif tipis tapi konsisten.

### Contoh kalkulasi nyata (XAUUSDm, 10 layers, vol=0.01):

```
Profit target  = $0.50/pos → $5.00/siklus jika semua menang
SL threshold   = $0.50 × 1.0 = $0.50/pos → $5.00/siklus jika semua kalah
Sesudah 10 siklus menang + 10 siklus kalah:
  Net = (10 × $5.00) - (10 × $5.00) = $0 (break-even di 50%)
Jika winrate 55%:
  Net = (11 × $5.00) - (9 × $5.00) = +$10.00 untuk 20 siklus
```

---

## 3. Aggressive Engine {#aggressive-engine}

### Parameter Lengkap

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `symbol` | XAUUSDm | Instrumen trading |
| `direction` | BUY | BUY / SELL / BOTH / AUTO |
| `layers` | 10 | Jumlah posisi concurrent |
| `volume` | 0.01 | Lot per posisi |
| `profit_target` | 0.50 | USD profit per posisi untuk trigger close |
| `sl_loss_multiplier` | **1.0** | Hard SL: tutup jika loss ≥ N × profit_target |
| `sl_cooldown_sec` | 0.0 | Detik jeda setelah SL sebelum buka ulang |
| `trend_guided` | **true** | EMA M1+M5+M15 trend filter — default ON (filter taktis utama) |
| `flip_mode` | none | Anti-trap: none / percentile / counter / hybrid |
| `mc_guard` | false | Aktifkan MCGuard equity protection |
| `max_session_loss_usd` | 0.0 | Stop jika net loss session melebihi nilai ini (0=off) |
| `max_drawdown_from_peak` | 0.0 | Stop jika profit turun dari peak (0=off) |

> **Parameter yang dihapus dari UI:** `sl_pips`, `tp_pips` — selalu 0 (engine monitor profit secara internal).

### SL Cooldown — Anti Revenge Trading

Setelah SL terpicu, engine menunggu `sl_cooldown_sec` detik sebelum membuka posisi baru.

```
sl_cooldown_sec = 0    → langsung buka ulang (default, mode agresif)
sl_cooldown_sec = 30   → tunggu 30 detik
sl_cooldown_sec = 300  → tunggu 5 menit (mode konservatif)
```

Di UI, badge merah **"⏸ cooldown Xs"** muncul di session card saat cooldown aktif.

**Kapan gunakan cooldown?**
- Market choppy / sideway: `sl_cooldown_sec = 60-300`
- Trending kuat: `sl_cooldown_sec = 0-30`

### Trend EMA (Cara Kerja Internal)

Engine menggunakan **EMA yang benar** (bukan SMA) untuk deteksi trend:

```python
# EMA yang benar:
alpha = 2 / (period + 1)
EMA = price × alpha + EMA_prev × (1 - alpha)

# EMA5 lebih responsif (bereaksi cepat terhadap perubahan harga)
# EMA10 lebih smooth (filter noise)
# Sinyal: EMA5 > EMA10 → BUY, EMA5 < EMA10 → SELL
```

> **Catatan:** Sebelum v2.1, engine menggunakan SMA (rata-rata aritmatik) yang terlalu lambat. Sekarang sudah diperbaiki ke EMA sejati.

---

## 4. Cascade Engine {#cascade-engine}

### Parameter Lengkap

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `symbol` | XAUUSDm | Instrumen trading |
| `initial_batch` | 10 | Posisi yang dibuka di awal |
| `topup_batch` | 5 | Posisi tambahan per topup saat trend terkonfirmasi |
| `volume` | 0.01 | Lot per posisi |
| `profit_target` | 2.0 | USD profit target per posisi (threshold besar karena DCA) |
| `sl_loss_multiplier` | **1.0** | Hard SL threshold multiplier |
| `max_positions` | 30 | Maksimum total posisi terbuka |
| `eval_interval` | 300 | Interval evaluasi topup (detik) |

### Alur Cascade

```
[Start] → Buka initial_batch posisi
    ↓
[Setiap eval_interval detik]
    ↓
Cek trend (M1 + M5 + M15) ← arah dari multi-timeframe
    ↓ trend terkonfirmasi + (HMM filter lulus jika aktif)
Buka topup_batch posisi baru
    ↓
Ulangi sampai max_positions tercapai atau stop manual
```

> **Perbaikan v2.1:** Initial direction sekarang menggunakan M1+M5+M15 (sama dengan evaluasi topup). Sebelumnya hanya M15 yang menyebabkan inkonsistensi arah awal.

---

## 5. HMM Advisory — Session Decision Support {#hmm-filter}

### Filosofi: Dua Level Keputusan

```
LEVEL STRATEGIS  →  HMM Signal Engine
(kapan MULAI session)     "Apakah setup saat ini layak untuk launch?"
                           Keputusan TRADER, bukan engine otomatis

LEVEL TAKTIS     →  EMA Trend (trend_guided = true, DEFAULT ON)
(kapan BUKA posisi)        Real-time, M1+M5+M15 majority vote
                           Dijalankan oleh ENGINE secara otomatis
```

**Mengapa HMM tidak dipakai sebagai per-position gate:**

HMM bekerja pada M15 bar close — artinya sinyal baru muncul setiap 15 menit. Jika digunakan sebagai filter per-posisi, engine hanya bisa buka posisi dalam 5 menit pertama setelah sinyal (hmm_max_age_s=300), lalu BLOCKED selama 10 menit berikutnya. Ini membunuh filosofi "speed + volume = edge" dari Aggressive engine.

### HMM Advisory Badge di UI

Di atas form Start Session, terdapat badge informasi HMM yang refresh setiap 30 detik:

| Badge | Warna | Arti |
|-------|-------|------|
| `HMM: BUY 0.72 \| 2m` | Hijau | Sinyal BUY fresh, similarity 0.72, 2 menit lalu |
| `HMM: SELL 0.65 \| 8m` | Kuning | Sinyal ada tapi mulai stale (>5 menit) |
| `HMM: no signal` | Abu | Tidak ada sinyal untuk symbol ini |
| `HMM offline` | Abu | Signal Engine tidak running |

**Badge ini hanya informatif** — tidak memblokir engine apapun.

### Cara Trading dengan Signal Engine + Aggressive (Recommended Flow)

1. Buka tab Signal Engine, start session untuk symbol yang sama (misal XAUUSDm)
2. Tunggu badge HMM berubah ke **hijau** (sinyal fresh muncul)
3. Perhatikan arah sinyal (BUY/SELL) dan similarity score
4. Jika setup cocok dengan analisa Anda → start Aggressive session
5. Engine berjalan dengan `trend_guided = true` (EMA M1+M5+M15) sebagai filter taktis

### Signal Engine No-Signal Warning

Jika Signal Engine berjalan lebih dari 20 bar (≈5 jam di M15) tanpa sinyal yang fire, akan muncul log WARNING:
```
[Engine] XAUUSDm/M15: No signal fired after 20 bars. Check pattern_states configuration.
```
Dan field `no_signal_warning: true` muncul di status. Ini menandakan `pattern_states` mungkin tidak cocok dengan kondisi market saat ini.

---

## 6. MCGuard — Proteksi Equity {#mcguard}

MCGuard memantau equity account secara real-time dan mengurangi lot saat mendekati margin call.

```
mc_level_pct = 0.10  → trigger saat equity ≤ 10% dari balance
safety_multiplier = 3.0  → kurangi volume ke 1/3 dari normal
emergency_multiplier = 1.5  → jika masih turun, kurangi lagi ke 1/1.5
```

**Cascade** selalu mengaktifkan MCGuard secara internal. **Aggressive** membutuhkan `mc_guard = true`.

---

## 7. Profit Guard — Proteksi Session {#profit-guard}

Dua mekanisme proteksi profit per session:

### Floor Loss (max_session_loss_usd)

```
max_session_loss_usd = 10.0  → stop session jika net loss (realized + floating) ≥ $10
max_session_loss_usd = 0.0   → disabled
```

### Drawdown dari Peak (max_drawdown_from_peak)

```
max_drawdown_from_peak = 5.0  → stop jika profit turun $5 dari peak tertinggi
                                 Contoh: profit mencapai $8, lalu turun ke $3 → STOP
max_drawdown_from_peak = 0.0  → disabled
```

> Net loss = `realized_pnl + floating_pnl` (mencakup posisi terbuka)

---

## 8. Rekomendasi Setting per Instrumen {#rekomendasi-setting}

### XAUUSDm (Gold)

```
volume             = 0.01
layers             = 10
profit_target      = 0.50
sl_loss_multiplier = 1.0
sl_cooldown_sec    = 30
trend_guided       = true  ← default on, tidak perlu diset manual
max_session_loss_usd    = 8.0
max_drawdown_from_peak  = 4.0
```

### BTCUSDm (Bitcoin)

```
volume             = 0.01
layers             = 5     ← kurangi layer karena volatilitas tinggi
profit_target      = 1.0   ← target lebih besar karena spread/volatilitas
sl_loss_multiplier = 1.0
sl_cooldown_sec    = 60    ← cooldown lebih panjang
trend_guided       = true  ← default on
max_session_loss_usd    = 10.0
max_drawdown_from_peak  = 5.0
```

### Forex (EURUSD, GBPUSD, dll)

```
volume             = 0.10  ← pip value lebih kecil
layers             = 10
profit_target      = 0.30  ← target lebih kecil karena spread kecil
sl_loss_multiplier = 1.0
sl_cooldown_sec    = 15
trend_guided       = true  ← default on
max_session_loss_usd    = 5.0
max_drawdown_from_peak  = 3.0
```

### Cascade XAUUSDm

```
initial_batch      = 5     ← mulai kecil
topup_batch        = 3
volume             = 0.01
profit_target      = 1.50
sl_loss_multiplier = 1.0
eval_interval      = 300
max_positions      = 20
max_session_loss_usd    = 15.0
max_drawdown_from_peak  = 8.0
```

---

## 9. Troubleshooting {#troubleshooting}

### Session terus SL, tidak pernah TP

**Kemungkinan penyebab:**
1. `sl_loss_multiplier` terlalu kecil (misal 0.1) → SL terlalu dekat
2. `profit_target` terlalu besar → posisi tidak pernah mencapai target sebelum market berbalik
3. Direction salah (BUY di downtrend)

**Solusi:**
- Set `sl_loss_multiplier = 1.0`
- Aktifkan `trend_guided = true`
- Aktifkan `hmm_filter = true` untuk filter entry yang lebih selektif
- Set `sl_cooldown_sec = 60` untuk hindari revenge trading

### HMM Filter tidak pernah lulus (posisi tidak terbuka)

**Kemungkinan penyebab:**
1. Signal Engine tidak running untuk symbol yang sama
2. `hmm_min_similarity` terlalu tinggi
3. `hmm_max_age_s` terlalu kecil (sinyal sudah expired)

**Solusi:**
- Pastikan Signal Engine running: cek `GET /python/signal-engine/status`
- Turunkan `hmm_min_similarity` ke 0.55
- Naikkan `hmm_max_age_s` ke 600

### Session zombie (tidak ada aktivitas, status running)

Engine secara otomatis mendeteksi kegagalan koneksi MT5. Setelah **5 kegagalan berturut-turut**, session akan auto-stop dengan status `error_zombie`.

Jika terjadi:
1. Cek koneksi MT5 terminal
2. Restart MT5 terminal
3. Start session baru

### Cooldown badge merah muncul terus-menerus

Artinya SL sering terpicu. Ini normal jika:
- Market sideways dengan `sl_cooldown_sec` yang panjang
- `sl_loss_multiplier` rendah sehingga SL cepat tercapai

Pertimbangkan menghentikan session dan menunggu kondisi market yang lebih trending.

---

*TradeOS v2.2 — Phase 1-4: EMA fix, SL Cooldown, zombie detection, Profit Guard, HMM reposisi sebagai advisory tool, MCGuard shared equity cache, fill failure backoff, session cleanup, Signal Engine no-signal warning.*
