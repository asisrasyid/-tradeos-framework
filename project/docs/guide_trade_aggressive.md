# Panduan Trading Engine — TradeOS
## Aggressive Engine & Cascade Engine

> **Filosofi:** *Play to win, not to get rich.* Engine ini adalah **pabrik kecil penghasil uang** — mengambil keuntungan kecil secara konsisten dari volatilitas pasar. SL bukan kekalahan, SL adalah **biaya operasional**. Posisi yang SL langsung dibuka ulang, tetap pada momentum.

---

## Daftar Isi

1. [Konsep Dasar](#1-konsep-dasar)
2. [Perbedaan AGGR vs CASCADE](#2-perbedaan-aggr-vs-cascade)
3. [Alur Kerja Engine](#3-alur-kerja-engine)
4. [Parameter Lengkap — AGGR](#4-parameter-lengkap--aggr)
5. [Parameter Lengkap — CASCADE](#5-parameter-lengkap--cascade)
6. [Sistem Analisa Trend (M1+M5+M15)](#6-sistem-analisa-trend-m1m5m15)
7. [Hard SL — Mekanisme Stop Loss](#7-hard-sl--mekanisme-stop-loss)
8. [Flip Mode (Anti-Trap) — AGGR only](#8-flip-mode-anti-trap--aggr-only)
9. [MCGuard — Perlindungan Equity](#9-mcguard--perlindungan-equity)
10. [Profit Guard — Perlindungan Profit Sesi](#10-profit-guard--perlindungan-profit-sesi)
11. [Rekomendasi Sesi Berikutnya](#11-rekomendasi-sesi-berikutnya)
12. [Contoh Setting](#12-contoh-setting)
13. [Dos and Don'ts](#13-dos-and-donts)
14. [Catatan Eksperimen](#14-catatan-eksperimen)

---

## 1. Konsep Dasar

Kedua engine bekerja dengan prinsip yang sama: **membuka banyak posisi kecil secara paralel**, memanen profit cepat, dan membuka ulang secara otomatis.

```
Buka N posisi
    ↓
Monitor setiap 5 detik
    ↓
Posisi profit ≥ target → Close → Buka ulang langsung
Posisi loss ≥ SL threshold → Close → Buka ulang langsung
    ↓
Loop terus selama sesi aktif
```

**Keunggulan pendekatan ini:**
- Tidak menunggu — setiap detik ada potensi profit
- SL tidak mematikan operasi — posisi langsung diganti yang baru
- Volume × kecepatan = hasil konsisten

**Kondisi market yang cocok:**
- London session / NY session (14:00–22:00 WIB) — volatilitas aktif
- XAUUSDm / XAGUSDm — spread lebih predictable
- Pasar ranging dengan volatilitas sedang

**Hindari:**
- Berita besar: NFP, FOMC, CPI, FOMC minutes
- Dini hari 00:00–07:00 WIB — market sepi, spread melebar
- Saat geopolitical shock tiba-tiba

---

## 2. Perbedaan AGGR vs CASCADE

| Aspek                     | AGGR (Aggressive)                         | CASCADE                               |
|---------------------------|-------------------------------------------|---------------------------------------|
| **Tujuan**                | Layer tetap N posisi                      | Pyramid + topup dinamis               |
| **Re-open**               | Langsung setelah TP/SL                    | Evaluasi per interval                 |
| **Arah**                  | BUY / SELL / BOTH                         | Satu arah, bisa flip                  |
| **Interval**              | 5 detik                                   | Configurable (default 5 menit)        |
| **Initial direction**     | Ditentukan user                           | Dianalisa dari M15 otomatis           |
| **Flip mode**             | Ya (counter/percentile/hybrid)            | Tidak (pakai trend vote)              |
| **Pyramiding**            | Tidak                                     | Ya (topup searah trend)               |
| **Cocok untuk**           | Scalping cepat, ranging                   | Trending market, swing lebih panjang  |

---

## 3. Alur Kerja Engine

### AGGR
```
START
  │
  ▼
Buka N layer (sesuai setting Direction)
  │
  ▼
Loop setiap 5 detik:
  ├─ [MCGuard] → cek equity/margin
  │     ├─ EMERGENCY → close semua, STOP
  │     ├─ DANGER    → close 3 terburuk, skip cycle
  │     └─ OK/CAUTION/WARNING → lanjut
  │
  ├─ [Profit Guard] → cek total_net (realized + floating)
  │     ├─ Net ≤ -Loss floor → close semua, STOP
  │     ├─ Net < Peak - Drawdown → close semua, STOP
  │     └─ OK → lanjut
  │
  ├─ [Hard SL] → cek per posisi
  │     └─ floating_loss ≥ SL Loss× × profit_target → close langsung
  │
  ├─ Cek posisi profit ≥ target → close + catat arah
  │
  ├─ [Trend Guide aktif] → vote M1+M5+M15
  │     ├─ BUY/SELL → set arah re-open
  │     └─ NEUTRAL  → pakai arah TP terakhir
  │
  ├─ [Flip Mode] → cek counter/percentile (jika Trend Guide NEUTRAL)
  │
  └─ Isi ulang layer kosong → buka posisi baru
```

### CASCADE
```
START
  │
  ▼
Analisa M15 → tentukan arah awal
  │
  ▼
Buka initial_batch posisi
  │
  ▼
Loop setiap eval_interval detik:
  ├─ [MCGuard] → cek equity/margin
  ├─ [Profit Guard] → cek total_net (realized + floating)
  ├─ Sync posisi yang sudah close (TP hit)
  ├─ Vote M1+M5+M15 → BUY / SELL / NEUTRAL
  │     └─ NEUTRAL → pakai arah TP terakhir (last_tp_direction)
  ├─ [Hard SL] → close posisi yang melewati threshold
  │
  ├─ Trend sama → topup (pyramiding)
  ├─ Trend beda → buka batch baru arah berlawanan
  └─ NEUTRAL + tidak ada last_tp → hold, tidak topup
```

---

## 4. Parameter Lengkap — AGGR

### Parameter Dasar

| Parameter                 | Label UI          | Deskripsi                                      | Default           | Range             |
|---------------------------|-------------------|------------------------------------------------|-------------------|-------------------|
| **Symbol**                | Symbol            | Instrument trading                             | `XAUUSDm`         | Dropdown          |
| **Direction**             | Direction         | Arah trading                                   | `BUY`             | BUY / SELL / BOTH |
| **Layers**                | Layers            | Jumlah posisi paralel yang selalu dijaga       | `10`              | 1–50              |
| **Volume**                | Volume            | Lot size per posisi                            | `0.01`            | > 0               |
| **Profit $**              | Profit tgt $      | Target profit per posisi (USD) → trigger close | `0.5`             | > 0               |
| **SL pips**               | SL pips           | Stop loss langsung di broker (0 = tidak pakai) | `0`               | ≥ 0               |

> **Note Direction BOTH:** Setiap cycle fill membuka BUY dan SELL secara bergantian. Layers dibagi dua. Cocok untuk ranging murni tanpa Trend Guide.

---

### Flip Mode (Anti-Trap)

| Parameter             | Label UI           | Deskripsi                            | Default   |
|-----------------------|--------------------|--------------------------------------|-----------|
| **Flip Mode**         | Flip               | Kapan engine ganti arah              | `none`    |
| **Flip Pct**          | Pct                | Threshold posisi harga dalam range   | `0.80`    |
| **Flip After**        | After              | Jumlah TP berturut sebelum flip      | `3`       |

| Mode          | Trigger flip               | Cocok untuk                      |
|---------------|----------------------------|----------------------------------|
| `none`        | Tidak pernah               | Trending + Trend Guide aktif     |
| `counter`     | Setelah N TP arah sama     | Ranging                          |
| `percentile`  | Harga di X% dari range     | Ranging dengan range jelas       |
| `hybrid`      | Salah satu terpenuhi       | Default aman                     |

---

### Trend Guide (M1+M5+M15)

| Parameter         | Label UI      | Deskripsi                                 | Default |
|-------------------|---------------|-------------------------------------------|---------|
| **Trend Guide**   | Trend Guide   | Aktifkan analisa trend sebelum re-open    | `false` |

Saat aktif: setelah setiap TP/SL, engine cek majority vote M1+M5+M15.
- Hasil BUY/SELL → override flip mode, paksa arah itu
- Hasil NEUTRAL → gunakan arah TP terakhir sebagai fallback

---

### MCGuard

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **MC Guard** | MCGuard | Aktifkan proteksi equity | `false` |
| **MC%** | MC level % | Level MC broker (% dari balance) | `0.10` = 10% |
| **Safety×** | Safety x | Faktor safety floor | `3.0` |
| **Emrg×** | Emrg x | Faktor emergency floor | `1.5` |

---

### Hard SL Per Posisi

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **SL Loss×** | SL Loss× | Multiplier × profit_target → threshold SL | `0` (disabled) |

```
Threshold = SL Loss× × Profit Target

Contoh: SL Loss× = 3.0, Profit Target = $0.50
Threshold = $1.50

Posisi floating loss ≥ $1.50 → close langsung, buka ulang
```

> **Tidak ada kondisi trend.** Close terjadi begitu threshold tercapai — momentum tetap terjaga karena langsung buka ulang.

---

### Profit Guard

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **Loss floor $** | Loss $ | Stop sesi jika total_net ≤ −nilai ini | `0` (disabled) |
| **Drawdown $** | DD $ | Stop sesi jika profit turun lebih dari ini dari puncak | `0` (disabled) |

```
total_net = realized profit + floating P&L semua posisi aktif

Contoh setup: Loss floor = $5, Drawdown = $3

Skenario A — Market chaos dari awal:
  total_net = -$5.01 → trigger floor → STOP, max rugi $5

Skenario B — Profit $10 lalu balik:
  Peak = $10.00
  Trigger drawdown di $10 - $3 = $7.00
  → Stop di $7, lock profit minimal $7
```

> Kedua kondisi bisa diaktifkan bersamaan — mana yang terpenuhi duluan yang trigger.
> `0` = fitur nonaktif.

---

## 5. Parameter Lengkap — CASCADE

### Parameter Dasar

| Parameter | Label UI | Deskripsi | Default | Range |
|-----------|----------|-----------|---------|-------|
| **Symbol** | Symbol | Instrument trading | `XAUUSDm` | Dropdown |
| **Init batch** | Init batch | Jumlah posisi awal | `10` | 1–50 |
| **Topup batch** | Topup batch | Posisi tambahan per topup | `5` | 1–20 |
| **Volume** | Volume | Lot size per posisi | `0.01` | ≥ 0.01 |
| **Profit tgt $** | Profit tgt $ | Target profit per posisi — basis perhitungan SL | `2.0` | > 0.1 |
| **Max pos** | Max pos | Hard cap total posisi terbuka | `30` | 1–200 |
| **Eval (sec)** | Eval (sec) | Interval evaluasi dalam detik | `300` | 30–3600 |

> **Initial direction** ditentukan otomatis dari analisa EMA5/EMA10 M15 saat sesi dimulai. Jika M15 NEUTRAL, engine retry hingga 2 menit sebelum berhenti.

---

### Hard SL Per Posisi

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **SL Loss×** | SL Loss× | Multiplier × profit_target | `3.0` |

Sama persis dengan AGGR — close langsung tanpa kondisi trend, buka ulang segera.

---

### MCGuard

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **MC level %** | MC level % | Level MC broker | `0.10` |
| **Safety x** | Safety x | Faktor safety floor | `3.0` |
| **Emergency x** | Emergency x | Faktor emergency floor | `1.5` |

---

### Profit Guard

| Parameter | Label UI | Deskripsi | Default |
|-----------|----------|-----------|---------|
| **Loss floor $** | Loss floor $ | Stop jika total_net ≤ −nilai ini | `0` (disabled) |
| **Drawdown $** | Drawdown $ | Stop jika profit turun dari puncak > nilai ini | `0` (disabled) |

---

## 6. Sistem Analisa Trend (M1+M5+M15)

Engine menggunakan **majority vote dari 3 timeframe** untuk menentukan arah market.

### Cara kerja
```
Untuk setiap TF (M1, M5, M15):
  EMA5  = rata-rata 5 close terakhir
  EMA10 = rata-rata 10 close terakhir
  Buffer = EMA10 × 0.0001  ← noise filter 1 pip

  EMA5 > EMA10 + buffer → vote BUY
  EMA5 < EMA10 - buffer → vote SELL
  Selain itu           → NEUTRAL (tidak vote)

Majority (min 2 dari 3):
  BUY ≥ 2  → trend BUY
  SELL ≥ 2 → trend SELL
  Lainnya  → NEUTRAL
```

### Fallback NEUTRAL

Saat hasil vote = NEUTRAL:
- **AGGR:** gunakan arah TP terakhir yang berhasil (`last_closed_dir`)
- **CASCADE:** gunakan arah TP terakhir yang terdeteksi (`last_tp_direction`)
- Jika belum ada TP sama sekali → tidak flip (pertahankan arah saat ini)

### Penggunaan di masing-masing engine

| Fungsi | AGGR | CASCADE |
|--------|------|---------|
| Analisa sebelum re-open | ✓ (jika Trend Guide ON) | ✓ (setiap eval) |
| Analisa awal sesi | — | Dari M15 |
| NEUTRAL fallback | last_closed_dir | last_tp_direction |
| Hard SL cek | Tidak pakai trend | Tidak pakai trend |
| Rekomendasi sesi akhir | ✓ | ✓ |

---

## 7. Hard SL — Mekanisme Stop Loss

### Prinsip

```
Threshold = SL Loss× × Profit Target

Setiap posisi:
  floating_loss = abs(profit) jika profit < 0

  jika floating_loss ≥ threshold:
    → Close posisi sekarang
    → Tidak perlu cek trend
    → Langsung buka ulang (engine tetap berjalan)
```

### Mengapa tidak ada kondisi trend?

Engine ini adalah **mesin momentum**. Saat SL terpaksa close:
1. Posisi lama ditutup (realisasi kerugian kecil)
2. Posisi baru langsung dibuka di harga sekarang
3. Posisi baru ini sudah ada di harga yang lebih baik

Menunggu konfirmasi trend sebelum SL hanya memperburuk kerugian. Kecepatan adalah proteksi.

### Rekomendasi nilai SL Loss×

| Gaya | Nilai | Keterangan |
|------|-------|------------|
| Agresif | `2.0` | Cut cepat, buka ulang lebih sering |
| Normal | `3.0` | Balance proteksi vs. ruang gerak |
| Konservatif | `5.0` | Beri ruang sebelum cut |
| Nonaktif | `0` | Tidak ada forced SL per posisi |

---

## 8. Flip Mode (Anti-Trap) — AGGR only

Mencegah engine terus buka posisi di arah yang salah saat harga sudah di ujung range.

### counter
```
Setelah N TP ke arah yang sama → flip arah
Contoh: After = 3, sudah 3× TP BUY → flip ke SELL
```

### percentile
```
Hitung posisi harga dalam range 20 bar terakhir (0.0–1.0)
BUY  + harga di atas Pct (misal 0.80) → flip ke SELL
SELL + harga di bawah (1 - Pct) → flip ke BUY
```

### hybrid
```
Flip jika SALAH SATU terpenuhi: counter ATAU percentile
Paling aman untuk market yang tidak selalu predictable
```

> **Trend Guide mengoverride Flip Mode.** Jika Trend Guide ON dan hasilnya tidak NEUTRAL, flip mode diabaikan. Flip mode hanya aktif saat trend NEUTRAL.

---

## 9. MCGuard — Perlindungan Equity

Berjalan setiap cycle, sebelum semua operasi lain (kecuali Profit Guard).

### Formula
```
mc_level        = balance × MC%
safety_floor    = mc_level × Safety×
emergency_floor = mc_level × Emrg×
```

### 4 Level

| Level | Kondisi | Tindakan |
|-------|---------|----------|
| **CAUTION** | free_margin < safety_floor × 1.5 | Skip buka posisi baru cycle ini |
| **WARNING** | free_margin < safety_floor | Blokir semua order baru |
| **DANGER** | free_margin < mc_level | Close 3 posisi paling rugi |
| **EMERGENCY** | equity < emergency_floor | Close SEMUA, stop engine |

### Contoh (Balance $1000, MC% 10%)
```
mc_level        = $100
safety_floor    = $100 × 3.0 = $300
emergency_floor = $100 × 1.5 = $150

free_margin < $300  → WARNING/CAUTION (stop buka baru)
free_margin < $100  → DANGER (tutup 3 terburuk)
equity < $150       → EMERGENCY (tutup semua, stop)
```

---

## 10. Profit Guard — Perlindungan Profit Sesi

Berjalan setiap cycle, setelah MCGuard.

### Mengapa diperlukan?

MCGuard melindungi **akun** dari margin call. Profit Guard melindungi **profit sesi** dari:
1. Kerugian kumulatif yang melebihi batas modal yang diizinkan
2. Profit yang sudah diraih tapi "dikembalikan ke market"

### Cara kerja
```
total_net = total_profit (realized) + floating_pnl (semua posisi aktif kita)

Update peak: jika total_net > peak_profit → simpan sebagai peak_profit baru

Check 1 — Floor:
  jika total_net ≤ −Loss floor $ → STOP SESSION

Check 2 — Drawdown dari peak:
  jika total_net < peak_profit − Drawdown $ → STOP SESSION

Saat stop: close semua posisi, sesi berhenti
```

### Contoh visual

```
Balance awal sesi: $0 (profit sesi)

Menit 10: total_net = +$8.00  ← peak = $8.00
Menit 20: total_net = +$6.50  ← masih di atas $8 - $3 = $5
Menit 30: total_net = +$5.10  ← masih OK
Menit 31: total_net = +$4.90  ← trigger! ($8 - $3 = $5)
→ Stop di $4.90, lock profit

Tanpa Profit Guard:
Menit 45: total_net = +$1.20  ← kehilangan $6.80 profit
Menit 60: total_net = -$2.00  ← baru sadar terlambat
```

### Tips setting

```
Untuk sesi scalping pendek (< 1 jam):
  Loss floor $ = 3–5   (batas rugi absolut)
  Drawdown $   = 2–3   (jaga profit yang sudah ada)

Untuk sesi panjang (> 2 jam):
  Loss floor $ = 8–15  (toleransi lebih untuk fluktuasi)
  Drawdown $   = 5–8   (tetap jaga profit signifikan)

Nonaktifkan (= 0) jika ingin engine berjalan tanpa batas
```

### Live stats di dashboard

Saat sesi berjalan, card menampilkan:
- **Net** — total_net saat ini (realized + floating)
- **Float** — floating P&L posisi yang masih terbuka
- **Peak** — nilai tertinggi total_net yang pernah dicapai sesi ini

---

## 11. Rekomendasi Sesi Berikutnya

Saat sesi berhenti (apapun alasannya), engine otomatis menjalankan satu kali analisa trend **M1+M5+M15** dan menampilkan hasilnya di card sesi.

```
Tampilan: "Rekomendasi sesi berikutnya: [BUY / SELL / NEUTRAL]"
           Analisa: M1+M5+M15 vote
```

### Cara menggunakan

| Hasil | Artinya | Tindakan |
|-------|---------|----------|
| **BUY** | 2 dari 3 TF menunjukkan uptrend | Mulai sesi baru dengan Direction = BUY |
| **SELL** | 2 dari 3 TF menunjukkan downtrend | Mulai sesi baru dengan Direction = SELL |
| **NEUTRAL** | Market belum jelas / sedang transisi | Tunggu 5–15 menit, cek ulang sebelum mulai |

> Rekomendasi ini adalah **petunjuk awal**, bukan jaminan. Selalu konfirmasi dengan kondisi market secara visual sebelum memulai sesi baru.

---

## 12. Contoh Setting

### AGGR — Pemula (Low Risk)
```
Symbol:     XAUUSDm
Direction:  BUY
Layers:     5
Volume:     0.01
Profit $:   0.30
SL pips:    0

Flip:       counter → After: 3
Trend Guide: ON

MCGuard:    ON → MC%: 0.10  Safety×: 4.0  Emrg×: 2.0
SL Loss×:   3.0

Profit Guard:
  Loss floor $: 2.0
  Drawdown $:   1.0
```

### AGGR — Balanced
```
Symbol:     XAUUSDm
Direction:  BUY
Layers:     10
Volume:     0.01
Profit $:   0.50
SL pips:    0

Flip:       hybrid → Pct: 0.80  After: 3
Trend Guide: ON

MCGuard:    ON → MC%: 0.10  Safety×: 3.0  Emrg×: 1.5
SL Loss×:   3.0

Profit Guard:
  Loss floor $: 5.0
  Drawdown $:   3.0
```

### AGGR — Agresif
```
Symbol:     XAUUSDm
Direction:  BOTH
Layers:     20
Volume:     0.01
Profit $:   1.00
SL pips:    0

Flip:       none
Trend Guide: ON

MCGuard:    ON → MC%: 0.10  Safety×: 2.5  Emrg×: 1.2
SL Loss×:   2.0

Profit Guard:
  Loss floor $: 10.0
  Drawdown $:   5.0
```

### CASCADE — Conservative
```
Symbol:      XAUUSDm
Init batch:  5
Topup batch: 3
Volume:      0.01
Profit tgt:  1.00
Max pos:     20
Eval (sec):  300

SL Loss×:    3.0

MCGuard:    MC%: 0.10  Safety×: 4.0  Emrg×: 2.0

Profit Guard:
  Loss floor $: 5.0
  Drawdown $:   2.0
```

### CASCADE — Balanced
```
Symbol:      XAUUSDm
Init batch:  10
Topup batch: 5
Volume:      0.01
Profit tgt:  2.00
Max pos:     30
Eval (sec):  300

SL Loss×:    3.0

MCGuard:    MC%: 0.10  Safety×: 3.0  Emrg×: 1.5

Profit Guard:
  Loss floor $: 10.0
  Drawdown $:   5.0
```

---

## 13. Dos and Don'ts

### DO ✓
- Selalu aktifkan **MCGuard** di live trading
- Aktifkan **Trend Guide** di AGGR agar tidak nyangkut di ujung
- Set **SL Loss×** — SL adalah biaya operasi, bukan kekalahan
- Set **Profit Guard** minimal Loss floor untuk lindungi modal
- Monitor badge `MC Status` dan stat `Net` / `Peak` di dashboard
- Test setting baru di akun demo minimal 2 jam sebelum live
- Jalankan di sesi aktif: London (14:00–19:00 WIB) atau NY overlap (19:00–22:00 WIB)
- Perhatikan rekomendasi setelah sesi stop sebelum mulai sesi baru

### DON'T ✗
- Jangan jalankan saat berita besar (NFP, FOMC, CPI, GDP)
- Jangan set Layers/Volume terlalu besar untuk margin yang tersedia
- Jangan matikan MCGuard di live trading
- Jangan tinggalkan engine tanpa dipantau > 30 menit
- Jangan langsung increase volume tanpa test di demo dulu
- Jangan abaikan rekomendasi NEUTRAL — pasar sedang tidak jelas
- Jangan set Loss floor terlalu ketat (akan stop terlalu cepat dari volatilitas normal)

---

## 14. Catatan Eksperimen

### AGGR — XAUUSDc tanpa Flip Mode
- Hasil: Positif awal, tapi nyangkut saat trend reversal
- **Pelajaran:** Flip mode atau Trend Guide wajib aktif

### AGGR — XAUUSDm dengan Trend Guide + Profit Guard
- Profit Guard (drawdown $3) berhasil lock profit $7 sebelum market reversal
- Tanpa Profit Guard: profit yang sama habis dalam 20 menit berikutnya
- **Pelajaran:** Profit Guard sangat efektif di market yang cepat reversal

### CASCADE — XAUUSDm dengan MCGuard
- Equity turun signifikan saat 15 posisi floating negatif bersamaan
- MCGuard DANGER aktif → close 3 terburuk → engine selamat
- **Pelajaran:** MCGuard adalah safety net yang benar-benar bekerja

### Hard SL — Perbandingan
- **Sebelum (kondisi trend):** Posisi rugi menunggu konfirmasi trend → kerugian membesar
- **Sesudah (hard threshold):** Posisi cut langsung, buka ulang di harga baru → total rugi lebih kecil
- **Pelajaran:** Kecepatan eksekusi lebih penting dari konfirmasi untuk scalping

### Temuan Umum
- XAUUSDm lebih stabil dari XAUUSDc (spread lebih predictable)
- Waktu terbaik: 14:00–22:00 WIB
- Hindari: 00:00–07:00 WIB (spread melebar, sinyal palsu)
- SL Loss× = 3.0 adalah sweet spot untuk $0.50 target
- Profit Guard Drawdown = 50–60% dari expected session profit adalah angka aman

---

*Dokumen ini diperbarui sesuai versi engine terbaru. Untuk spesifikasi teknis sistem HMM/Bayesian, lihat `hmm_bayesian_spec.md`.*
