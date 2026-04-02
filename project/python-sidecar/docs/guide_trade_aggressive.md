# TradeOS — Panduan Aggressive Engine

> Versi: v2.1 | Diperbarui: 2026-04-02

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Alur Kerja Engine (Lifecycle)](#alur-kerja-engine)
3. [Parameter Lengkap](#parameter-lengkap)
4. [Direction — Cara Engine Menentukan Arah](#direction)
5. [HMM Gate — Proteksi Kondisi Berbahaya](#hmm-gate)
6. [Auto Direction HMM](#auto-direction-hmm)
7. [Limit Orders](#limit-orders)
8. [SL Cooldown — Anti Revenge Trading](#sl-cooldown)
9. [Flip Mode — Anti-Trap](#flip-mode)
10. [MCGuard — Proteksi Equity Account](#mcguard)
11. [Profit Guard — Proteksi Per-Session](#profit-guard)
12. [Expected Value — Matematika Profitabilitas](#expected-value)
13. [Rekomendasi Setting per Instrumen](#rekomendasi-setting)
14. [Troubleshooting](#troubleshooting)

---

## 1. Gambaran Umum {#gambaran-umum}

Aggressive Engine adalah **execution engine berbasis layering**. Prinsipnya sederhana:

```
Buka N posisi sekaligus (layers) → tunggu masing-masing mencapai profit_target → tutup → buka ulang
```

Engine berjalan di thread tersendiri, poll setiap **2 detik**, dan berkomunikasi langsung dengan MT5 (bukan via HTTP). Ini menghasilkan eksekusi order yang sangat cepat (10–30ms vs 50–150ms sebelumnya).

**Filosofi utama:** Speed + volume = edge. Banyak posisi kecil yang masing-masing meraih profit kecil, diulang ribuan kali.

**Apa yang dilakukan engine setiap 2 detik:**
1. Cek MCGuard (proteksi equity) — prioritas tertinggi
2. Ambil posisi terbuka dari MT5
3. Kelola pending limit orders (jika aktif)
4. Cek Profit Guard — stop jika loss melebihi batas
5. Cek SL per posisi — tutup posisi yang merugi terlalu dalam
6. Deteksi TP hit dari broker — catat sebagai WIN
7. Setelah TP: tentukan direction baru (P1→P2→P3→P4)
8. Panggil `_fill_layers()` — buka posisi baru sampai penuh (dengan HMM Gate di dalamnya)
9. Update floating PnL untuk tampilan UI

---

## 2. Alur Kerja Engine (Lifecycle) {#alur-kerja-engine}

### Start Session

```
User klik START AGGR
    ↓
Engine buat AggressiveSession (semua config tersimpan di sini)
    ↓
Thread dimulai (daemon thread, mati otomatis jika main process mati)
    ↓
_fill_layers() pertama kali — buka N posisi sesuai layers
    ↓
Loop poll setiap 2 detik selama sess.active = True
```

### Poll Loop (setiap 2 detik)

```
MCGuard check
    ↓ OK
Ambil posisi dari MT5
    ↓
Kelola pending orders
    ↓
Profit Guard check
    ↓ OK
SL check (per posisi)
    ↓
Deteksi closed tickets (TP hit / manual close)
    ├─ Manual close → catat, TIDAK buka ulang
    └─ Broker TP   → update wins, tentukan direction baru → _fill_layers()
    ↓
_fill_layers() (unconditional — lihat catatan HMM Gate)
    ↓
Update floating PnL
```

> **Catatan penting:** `_fill_layers()` dipanggil unconditional (tanpa kondisi) setiap siklus.
> Ini disengaja agar HMM Gate bisa re-check secara berkala bahkan saat tidak ada posisi terbuka.
> Jika dipanggil conditional (hanya setelah TP), HMM Gate yang aktif saat 0 posisi akan deadlock selamanya.

### Stop Session

```
User klik STOP  →  sess.active = False
    ↓
Thread berhenti di siklus berikutnya
    ↓
Engine hitung next_recommendation (EMA20 M5 arah saat ini)
    ↓
Session tetap di list (stopped state) untuk riwayat
```

---

## 3. Parameter Lengkap {#parameter-lengkap}

### Core Config

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `symbol` | XAUUSDm | Instrumen trading |
| `direction` | BUY | `BUY` / `SELL` / `BOTH` / `AUTO` |
| `layers` | 10 | Jumlah posisi concurrent yang dipertahankan |
| `volume` | 0.01 | Lot per posisi |
| `profit_target` | 0.50 | USD profit per posisi — dikonversi ke harga TP di broker |

### Risk Controls

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `sl_loss_multiplier` | 0.0 | Hard SL per posisi: tutup jika loss ≥ N × profit_target. `0` = disabled |
| `sl_cooldown_sec` | 0.0 | Detik jeda setelah SL sebelum buka ulang. `0` = langsung |
| `max_session_loss_usd` | 0.0 | Stop session jika total loss (realized + floating) ≥ nilai ini. `0` = off |
| `max_drawdown_from_peak` | 0.0 | Stop jika profit turun N dollar dari peak tertinggi. `0` = off |
| `mc_guard` | false | Aktifkan MCGuard equity protection |

### HMM Gate

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `hmm_gate_enabled` | false | Aktifkan HMM Gate |
| `hmm_cooldown_sec` | 60.0 | Interval re-check (detik) — BUKAN durasi tunggu |
| `auto_direction_hmm` | false | Gunakan HMM vote untuk menentukan direction setelah TP |

### Entry Orders

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `limit_atr_mult` | 0.0 | Faktor ATR untuk offset limit order. `0` = market order |
| `pending_expiry_sec` | 15.0 | Detik sebelum pending limit order di-cancel otomatis |

### Flip Mode (Anti-Trap)

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `flip_mode` | none | `none` / `counter` / `percentile` / `hybrid` |
| `flip_after` | 3 | Jumlah TP beruntun sebelum flip (mode `counter`) |
| `flip_percentile` | 0.80 | Threshold percentile untuk flip (mode `percentile`) |
| `lookback_bars` | 20 | Jumlah bar untuk kalkulasi percentile |

> **Parameter deprecated (tetap ada untuk kompatibilitas API):** `sl_pips`, `tp_pips`, `trend_guided` — tidak digunakan. Selalu 0 / diabaikan.

---

## 4. Direction — Cara Engine Menentukan Arah {#direction}

Direction ditentukan **setiap kali setelah TP hit** menggunakan sistem prioritas berlapis:

```
P1: Daily S/R proximity
    Apakah harga mendekati level S/R harian?
    → BUY jika dekat support (bounce ke atas)
    → SELL jika dekat resistance (bounce ke bawah)
    → Skip jika tidak ada sinyal S/R
    ↓ (jika P1 tidak ada sinyal)

P2: EMA20 M5 trend
    Hitung EMA20 pada timeframe M5
    → BUY jika EMA20 slope naik
    → SELL jika EMA20 slope turun
    → NEUTRAL jika flat
    ↓ (jika P2 = NEUTRAL)

P3: flip_mode (backward compat)
    Hanya aktif jika flip_mode ≠ none
    → counter: flip setelah N TP beruntun
    → percentile: flip berdasarkan posisi harga relatif
    → hybrid: gabungan counter + percentile
    ↓ (jika P3 tidak trigger)

P4: Pertahankan arah saat ini
    Tidak ada yang berubah → lanjut dengan direction yang sama
```

### Mode Direction

| Mode | Perilaku |
|------|----------|
| `BUY` | Selalu buka posisi BUY. Direction bisa berubah jika P1/P2 mendeteksi kondisi berbeda dan flip terjadi. |
| `SELL` | Selalu buka posisi SELL. |
| `BOTH` | Alternasi BUY/SELL bergiliran per posisi (genap=BUY, ganjil=SELL). Tidak terpengaruh P1-P4. |
| `AUTO` | Resolusi awal menggunakan HMM vote (jika `auto_direction_hmm=True`) atau EMA20 M5. Setelah itu ikuti P1-P4. |

### Tampilan di UI

```
BUY              → direction tetap
AUTO→BUY         → AUTO mode, saat ini resolved ke BUY
BUY→SELL         → direction awal BUY, sekarang flipped ke SELL
```

---

## 5. HMM Gate — Proteksi Kondisi Berbahaya {#hmm-gate}

### Apa itu HMM Gate?

HMM Gate adalah **firewall pre-fill**. Sebelum engine membuka posisi baru, ia mengecek kondisi market via analisis HMM multi-timeframe (M5 + M15). Jika kondisi berbahaya terdeteksi, fills di-pause.

**Ini BUKAN timer.** HMM Gate tidak menunggu N detik lalu lanjut. Ia menunggu sampai kondisi benar-benar tidak lagi berbahaya.

### Kondisi yang Dianggap Berbahaya

| Tag | Kondisi | Contoh |
|-----|---------|--------|
| `S/R` | Harga mendekati resistance saat BUY, atau mendekati support saat SELL (confidence ≥ 65%) | Buka BUY tapi harga tepat di bawah resistance kuat |
| `MOM` | Momentum ekstrem berlawanan arah (severity=danger) | BUY tapi momentum z-score sangat negatif (oversell parah) |
| `DIV` | Cross-TF divergence (LTF vs HTF berlawanan) | M5 bullish tapi H1/H4 bearish kuat = bull trap |

Jika **tidak ada** kondisi di atas → aman → fills lanjut normal.

### Lifecycle HMM Gate (Lengkap)

```
Setiap siklus fill:
│
├─ [hmm_in_danger = False] ← kondisi normal
│   │
│   └─ Sudah waktunya pre-check? (sejak last_check ≥ hmm_cooldown_sec)
│       │
│       ├─ Belum waktunya → lanjut fill normal
│       │
│       └─ Waktunya → panggil _hmm_danger_check(symbol, current_direction)
│           │
│           ├─ Tidak ada bahaya → lanjut fill normal, catat waktu check
│           │
│           └─ BAHAYA TERDETEKSI
│               → hmm_in_danger = True
│               → catat reason + waktu check
│               → LOG WARNING
│               → return (fill di-skip siklus ini) ← GATE AKTIF
│
└─ [hmm_in_danger = True] ← gate sedang aktif, fills paused
    │
    └─ Sudah waktunya re-check? (sejak last_check ≥ hmm_cooldown_sec)
        │
        ├─ Belum waktunya
        │   → tampilkan countdown "HMM danger — re-check in Xs"
        │   → return (tetap paused)
        │
        └─ Waktunya → panggil _hmm_vote(symbol) ← cek apakah sudah aman
            │
            ├─ Vote TIDAK berlawanan arah (netral atau searah)
            │   → hmm_in_danger = False ← GATE CLEARED
            │   → lanjut fill di SIKLUS YANG SAMA INI (tidak tunggu)
            │
            └─ Vote MASIH berlawanan
                → tetap hmm_in_danger = True
                → countdown reset
                → return (masih paused)
```

### Pertanyaan Umum

**Q: Setelah gate cleared, apakah HMM Gate mati?**
A: **Tidak.** Gate tetap berjalan. Setiap `hmm_cooldown_sec` detik, engine melakukan pre-fill check. Jika kondisi berbahaya muncul lagi (kapanpun), gate **akan aktif lagi otomatis**.

**Q: Berapa kali gate bisa aktif dalam satu session?**
A: Tidak terbatas. Selama session aktif dan `hmm_gate_enabled=True`, siklus ini berjalan selamanya.

**Q: Apa yang terjadi jika server analisis HMM tidak bisa dihubungi?**
A: **Fail-open** — dianggap tidak ada bahaya, fills lanjut normal. Engine tidak berhenti hanya karena endpoint analisis tidak responsif.

**Q: Apakah posisi yang sudah terbuka ikut ditutup saat gate aktif?**
A: **Tidak.** Gate hanya memblokir pembukaan posisi baru. Posisi yang sudah terbuka tetap berjalan, TP/SL tetap aktif di broker.

### Setting hmm_cooldown_sec

```
hmm_cooldown_sec = 30   → check setiap 30 detik (reaktif, cocok untuk M1/M5 trading)
hmm_cooldown_sec = 60   → check setiap 1 menit (default, balance antara responsif dan API load)
hmm_cooldown_sec = 120  → check setiap 2 menit (konservatif, cocok untuk M15+ trading)
```

### Tampilan di UI (Session Card)

| Badge | Kondisi | Arti |
|-------|---------|------|
| `HMM` (ungu redup) | Gate aktif, kondisi aman | Normal — gate berjalan, tidak ada bahaya |
| `⏳ HMM 45s` (ungu terang, berkedip) | Gate aktif, dalam danger | Fills di-pause, re-check dalam 45 detik. Hover untuk lihat alasan. |
| _(tidak ada badge)_ | Gate disabled | `hmm_gate_enabled = false` |

---

## 6. Auto Direction HMM {#auto-direction-hmm}

Jika `auto_direction_hmm = True`, setelah setiap **TP hit**, engine menggunakan HMM vote untuk menentukan direction berikutnya (bukan hanya EMA20 M5).

### Cara Kerja Vote

```python
# Query /python/analysis/multi-tf dengan timeframes=["M5", "M15"]
# Kumpulkan confidence per arah:
buy_score  = sum(confidence) untuk semua alert dengan action=BUY
sell_score = sum(confidence) untuk semua alert dengan action=SELL

total = buy_score + sell_score
if total < 0.5:      → NEUTRAL (sinyal terlalu lemah)
if buy/total ≥ 0.65: → BUY (65% weight atau lebih ke BUY)
if buy/total ≤ 0.35: → SELL (65% weight atau lebih ke SELL)
else:                → NEUTRAL
```

### Priority setelah TP (dengan auto_direction_hmm=True)

```
HMM vote (M5+M15)
    ├─ BUY atau SELL → gunakan langsung sebagai direction baru
    └─ NEUTRAL       → fallback ke _decide_direction() normal (P1→P2→P3→P4)
```

### Kapan Gunakan auto_direction_hmm?

- Saat market sering berganti arah (ranging/choppy)
- Saat `direction=AUTO` untuk resolusi arah awal
- Sebaiknya **tidak** diaktifkan saat trending kuat (HMM bisa terlambat menangkap tren panjang)

---

## 7. Limit Orders {#limit-orders}

Jika `limit_atr_mult > 0`, engine tidak membuka market order. Sebaliknya, ia menempatkan **pending limit order** pada harga yang lebih baik (offset dari harga saat ini berdasarkan ATR).

### Cara Kerja

```
limit_atr_mult = 0.5
ATR current    = $0.80

BUY_LIMIT ditempatkan di: current_price - (0.5 × $0.80) = $0.40 di bawah harga saat ini
SELL_LIMIT ditempatkan di: current_price + (0.5 × $0.80) = $0.40 di atas harga saat ini
```

Logika: masuk di posisi yang lebih baik (sedikit pullback/retracement) daripada langsung di market price.

### Pending Order Management

Setiap 2 detik, engine cek semua pending orders:
- **Jika terisi** → pindah dari `pending_tickets` ke `active_tickets`
- **Jika sudah `pending_expiry_sec` detik tidak terisi** → auto-cancel via MT5

```
limit_atr_mult = 0.5, pending_expiry_sec = 15

→ Limit order ditempatkan
→ Jika 15 detik tidak ada fill → cancel
→ Buka market order sebagai fallback? → Tidak, tunggu siklus berikutnya
```

### Kapan Gunakan Limit Orders?

- Market dengan banyak bounce/retracement
- Saat spread sedang lebar (limit order masuk di spread yang lebih baik)
- **Jangan** gunakan saat trending kuat (limit order tidak pernah terisi)

---

## 8. SL Cooldown — Anti Revenge Trading {#sl-cooldown}

Setelah SL terpicu, engine menunggu `sl_cooldown_sec` detik sebelum membuka posisi baru.

```
sl_cooldown_sec = 0    → langsung buka ulang (default, mode agresif)
sl_cooldown_sec = 30   → tunggu 30 detik
sl_cooldown_sec = 60   → tunggu 1 menit
sl_cooldown_sec = 300  → tunggu 5 menit (mode konservatif)
```

**Tanda di UI:** Badge merah `⏸ Xs` di session card menunjukkan SL cooldown aktif beserta sisa detiknya.

**Kapan gunakan cooldown?**
- Market choppy / sideways: `sl_cooldown_sec = 60–300`
- Trending kuat: `sl_cooldown_sec = 0–30`
- Saat SL sering beruntun (revenge pattern): `sl_cooldown_sec = 120`

---

## 9. Flip Mode — Anti-Trap {#flip-mode}

Flip mode adalah mekanisme **P3 dalam direction decision** — hanya aktif jika P1 (Daily S/R) dan P2 (EMA20) tidak memberikan sinyal.

| Mode | Perilaku |
|------|----------|
| `none` | Tidak ada flip otomatis. Arah dipertahankan kecuali P1/P2 berkata beda. |
| `counter` | Flip arah setelah `flip_after` TP berturut-turut. Asumsi: tren biasanya membalik setelah banyak win beruntun. |
| `percentile` | Flip jika harga close saat ini di atas `flip_percentile` (untuk SELL) atau di bawah (1-flip_percentile) (untuk BUY) dari range `lookback_bars` bar terakhir. |
| `hybrid` | Gabungan counter + percentile. Flip hanya jika KEDUANYA setuju. Lebih selektif. |

> **Rekomendasi:** `flip_mode = none` untuk sebagian besar kondisi. P1 (Daily S/R) dan P2 (EMA20) sudah lebih reliabel dari counter/percentile sederhana.

---

## 10. MCGuard — Proteksi Equity Account {#mcguard}

MCGuard memantau free margin account secara real-time. Aktif jika `mc_guard = True`.

### Level MCGuard

| Level | Kondisi | Tindakan |
|-------|---------|---------|
| `OK` | Free margin normal | Tidak ada tindakan |
| `CAUTION` | Free margin mulai tertekan | Log warning, fills lanjut |
| `WARNING` | Free margin lebih rendah | Fill di-block sementara |
| `DANGER` | Free margin kritis | Tutup 3 posisi terburuk, skip fill siklus ini |
| `EMERGENCY` | Free margin sangat kritis | Tutup SEMUA posisi, stop session |

Parameter terkait:
```
mc_level_pct         = 0.10  → trigger saat equity ≤ 10% balance
safety_multiplier    = 3.0   → kurangi volume ke 1/3 di level WARNING
emergency_multiplier = 1.5   → kurangi lagi ke 1/1.5 di level DANGER
```

**Koordinasi antar session:** Jika multiple session aktif dan semua MCGuard mencapai EMERGENCY, hanya **satu** yang akan mengeksekusi close-all (menggunakan claim token eksklusif). Session lain akan stop tanpa close.

---

## 11. Profit Guard — Proteksi Per-Session {#profit-guard}

Dua mekanisme proteksi profit yang dievaluasi setiap siklus:

### Floor Loss (max_session_loss_usd)

```
max_session_loss_usd = 10.0
→ Hitung: realized_pnl + floating_pnl (semua posisi terbuka)
→ Jika total ≤ -$10 → tutup semua posisi → stop session
```

### Peak Drawdown (max_drawdown_from_peak)

```
max_drawdown_from_peak = 5.0
→ Pantau peak_profit (profit tertinggi yang pernah dicapai session ini)
→ Jika current_net < peak_profit - $5 → tutup semua → stop session

Contoh:
  Profit naik ke $8 (peak = $8)
  Profit turun ke $2.90 ($8 - $2.90 = $5.10 > $5) → STOP
```

> Gunakan keduanya bersama untuk perlindungan dua arah:
> `max_session_loss_usd` = batas kerugian absolut
> `max_drawdown_from_peak` = batas kerugian relatif dari puncak

---

## 12. Expected Value — Matematika Profitabilitas {#expected-value}

### Formula

```
EV per siklus = (WinRate × Profit per siklus) − (LossRate × Loss per siklus)
```

### Contoh (10 layers, profit_target = $0.50, sl_loss_multiplier = 1.0)

```
Profit per siklus = 10 × $0.50 = $5.00
Loss per siklus   = 10 × ($0.50 × 1.0) = $5.00
Break-even winrate = 50%
```

| sl_loss_multiplier | Break-even WR | Catatan |
|--------------------|---------------|---------|
| 0.0 (disabled) | 0% (tidak ada SL) | Berisiko tinggi jika posisi tidak pernah TP |
| **1.0** | **50%** | **Default — realistis** |
| 2.0 | 66.7% | Perlu winrate tinggi |
| 3.0 | 75% | Sangat sulit dicapai |

### Contoh Nyata (XAUUSDm, vol=0.01, 20 siklus)

```
Winrate 50%: (10 × $5) − (10 × $5) = $0.00 (break-even)
Winrate 55%: (11 × $5) − (9 × $5)  = +$10.00 (11 win, 9 loss)
Winrate 60%: (12 × $5) − (8 × $5)  = +$20.00
```

**Kesimpulan:** Di `sl_loss_multiplier = 1.0`, bahkan winrate 52% sudah menghasilkan EV positif. Target realistis dengan trend filter aktif.

---

## 13. Rekomendasi Setting per Instrumen {#rekomendasi-setting}

### XAUUSDm (Gold) — Recommended Start

```
symbol                 = XAUUSDm
direction              = AUTO
layers                 = 10
volume                 = 0.01
profit_target          = 0.50
sl_loss_multiplier     = 1.0
sl_cooldown_sec        = 30
hmm_gate_enabled       = true
hmm_cooldown_sec       = 60
auto_direction_hmm     = true
max_session_loss_usd   = 8.0
max_drawdown_from_peak = 4.0
```

### XAUUSDm — Mode Konservatif

```
layers                 = 5
volume                 = 0.01
profit_target          = 0.80
sl_loss_multiplier     = 1.0
sl_cooldown_sec        = 120
hmm_gate_enabled       = true
hmm_cooldown_sec       = 60
max_session_loss_usd   = 5.0
max_drawdown_from_peak = 3.0
```

### BTCUSDm (Bitcoin)

```
layers                 = 5      ← kurangi karena volatilitas tinggi
volume                 = 0.01
profit_target          = 1.50   ← target lebih besar
sl_loss_multiplier     = 1.0
sl_cooldown_sec        = 60
hmm_gate_enabled       = true
hmm_cooldown_sec       = 60
max_session_loss_usd   = 10.0
max_drawdown_from_peak = 5.0
```

### Forex (EURUSD, GBPUSD, dll)

```
layers                 = 10
volume                 = 0.10   ← pip value lebih kecil
profit_target          = 0.30   ← spread lebih kecil
sl_loss_multiplier     = 1.0
sl_cooldown_sec        = 15
hmm_gate_enabled       = true
hmm_cooldown_sec       = 60
max_session_loss_usd   = 5.0
max_drawdown_from_peak = 3.0
```

---

## 14. Troubleshooting {#troubleshooting}

### Session terus SL, tidak pernah TP

**Kemungkinan penyebab:**
1. `sl_loss_multiplier` terlalu kecil (misal 0.3) → SL terlalu dekat dengan noise market
2. `profit_target` terlalu besar → harga tidak mencapai target sebelum berbalik
3. Direction salah (BUY di downtrend, SELL di uptrend)

**Solusi:**
- Pastikan `sl_loss_multiplier = 1.0` (minimal)
- Aktifkan `hmm_gate_enabled = true` untuk hindari entry saat kondisi berbahaya
- Naikkan `sl_cooldown_sec = 60–120` untuk hindari revenge pattern

---

### HMM Gate terus aktif, fills tidak pernah resume

**Kemungkinan penyebab:**
1. Market benar-benar dalam kondisi berbahaya (divergence H1 vs M5 — ini memang harus di-pause)
2. `hmm_cooldown_sec` terlalu panjang (misal 600 detik = 10 menit)
3. Server analisis HMM tidak bisa diakses (endpoint `/python/analysis/multi-tf` down)

**Solusi:**
- Cek log engine untuk alasan gate aktif (terlihat di `last_action` session card)
- Turunkan `hmm_cooldown_sec` ke 30–60 detik agar re-check lebih sering
- Jika server down: gate fail-open (aman), tapi re-check tidak bisa resolve → restart sidecar

---

### Session zombie (status running tapi tidak ada aktivitas)

Engine mendeteksi kegagalan koneksi MT5 secara otomatis. Setelah **5 kegagalan berturut-turut**, session auto-stop dengan error `MT5 connection lost`.

**Solusi:**
1. Cek koneksi MT5 terminal (login, server, internet)
2. Restart MT5 terminal
3. Start session baru

---

### SL cooldown badge muncul terus-menerus

Artinya SL sering beruntun — biasanya terjadi saat:
- Market sideways/choppy dengan momentum tidak konsisten
- `sl_loss_multiplier` terlalu kecil
- Direction bertentangan dengan tren utama

**Solusi:**
- Hentikan session, tunggu kondisi lebih jelas
- Aktifkan `hmm_gate_enabled = true` untuk filter entry
- Naikkan `profit_target` agar TP lebih mudah tercapai sebelum reversal

---

### Fill failures berulang (posisi tidak terbuka)

Engine memiliki backoff otomatis setelah fill failure. Setelah **10 consecutive failures**, session auto-stop.

**Kemungkinan penyebab:**
1. MT5 tidak terhubung ke broker
2. Margin tidak cukup untuk volume yang diminta
3. Simbol tidak tersedia / market tutup

**Solusi:**
- Cek margin account
- Kurangi `volume` atau `layers`
- Verifikasi simbol aktif di MT5

---

### next_recommendation setelah stop tidak akurat

`next_recommendation` dihitung dari EMA20 M5 saat session berhenti — ini hanya snapshot satu momen. Jika market bergerak setelah session stop, rekomendasi bisa basi.

Selalu konfirmasi dengan analisis sendiri sebelum start session baru.

---

*TradeOS Aggressive Engine v2.1 — Direct MT5, Broker TP, HMM Gate, Auto Direction HMM, Limit Orders, MCGuard, Profit Guard, SL Cooldown, Flip Mode.*
