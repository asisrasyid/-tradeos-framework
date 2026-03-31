# TradeOS — Jurnal Lengkap: Membangun HMM Model untuk Trading

> Versi: v1.0 | Dibuat: 2026-03-28
> Untuk: Solo Trader yang ingin memahami sistem dari nol sampai live signal

---

## Daftar Isi

1. [Konsep Besar — Apa itu HMM dan Kenapa Penting?](#1-konsep-besar)
2. [Peta Sistem — Gambaran Besar Semua Komponen](#2-peta-sistem)
3. [6 Fitur HMM — Apa yang "Dilihat" oleh Model?](#3-6-fitur-hmm)
4. [State HMM — Kondisi Pasar dalam Angka](#4-state-hmm)
5. [Langkah 1: Training HMM Model](#5-langkah-1-training-hmm-model)
6. [Langkah 2: Membuat Pattern](#6-langkah-2-membuat-pattern)
7. [Langkah 3: Membuat Theory](#7-langkah-3-membuat-theory)
8. [Langkah 4: Menambahkan Factor ke Theory](#8-langkah-4-menambahkan-factor)
9. [Langkah 5: Menjalankan Backtest](#9-langkah-5-backtest)
10. [Langkah 6: Membaca Hasil Backtest](#10-langkah-6-membaca-hasil-backtest)
11. [Langkah 7: Mengaktifkan Signal Engine (Live)](#11-langkah-7-signal-engine-live)
12. [Workflow End-to-End dengan Contoh Nyata](#12-workflow-end-to-end)
13. [Tips & Troubleshooting](#13-tips--troubleshooting)
14. [Kamus Istilah](#14-kamus-istilah)

---

## 1. Konsep Besar

### Apa itu HMM?

**Hidden Markov Model (HMM)** adalah algoritma statistik yang mendeteksi "kondisi tersembunyi" dari data pasar.

Bayangkan pasar seperti seseorang dengan berbagai "mood":
- Mood **Trending Kuat** → harga bergerak satu arah
- Mood **Choppy/Ranging** → harga naik-turun tanpa arah
- Mood **Breakout** → volatilitas meledak
- Mood **Retest** → harga kembali ke level penting

Kamu tidak bisa langsung "melihat" mood ini dari candlestick tunggal. Tapi HMM bisa **mendeteksinya** dengan menganalisis pola volatilitas, momentum, dan posisi harga secara bersamaan — dan menyebutnya sebagai **State** (S0, S1, S2, dst).

### Kenapa HMM lebih baik dari indikator biasa?

| Indikator Biasa | HMM |
|-----------------|-----|
| Satu dimensi (misal RSI hanya ukur overbought) | 6 dimensi sekaligus (volatilitas + momentum + trend + dll) |
| Lagging (reaktif terhadap harga) | Probabilistik (mengklasifikasi kondisi, bukan harga) |
| Fixed parameter | Self-learning dari data historis |
| Tidak tahu "konteks" | Tau urutan state sebelumnya (Markov chain) |

### Flow Besar Sistem TradeOS

```
Data OHLC historis
    ↓
[Training HMM] → Model belajar "kondisi pasar"
    ↓
[Pattern] → Kamu definisikan urutan kondisi yang bagus untuk entry
    ↓
[Theory] → Kamu bungkus pattern + aturan dalam 1 "strategi"
    ↓
[Backtest] → Uji theory di data historis — seberapa bagus hasilnya?
    ↓
[Signal Engine] → Jalankan theory secara live, kirim sinyal ke engine trade
    ↓
[Aggressive/Cascade Engine] → Eksekusi trade berdasarkan sinyal
```

---

## 2. Peta Sistem

```
┌─────────────────────────────────────────────────────────────┐
│  HALAMAN          FUNGSI                       OUTPUT       │
├─────────────────────────────────────────────────────────────┤
│  HMM Models  →  Train model dari data historis  → Model     │
│  Patterns    →  Definisi urutan state           → Pattern   │
│  Theories    →  Buat strategi                   → Theory    │
│  TheoryDetail→  Tambah factor/pattern ke theory → Theory++  │
│  Backtest    →  Uji strategy di historis        → Metrics   │
│  Live        →  Start signal engine + trade     → Trades    │
└─────────────────────────────────────────────────────────────┘
```

**Urutan wajib:**
```
HMM Models → Patterns → Theory → Theory Detail (add factor) → Backtest → Live
```

Setiap langkah adalah prerequisite untuk langkah berikutnya.

---

## 3. 6 Fitur HMM

Model HMM tidak melihat candlestick mentah. Ia melihat **6 fitur terstandarisasi** yang diekstrak dari setiap candle. Semua fitur dinormalisasi — tidak bergantung pada harga absolut, jadi model yang sama bisa dipakai di Gold ($2000) maupun Forex (1.10).

### Fitur F0: ATR Percentile (Volatilitas Relatif)
```
Formula: rank(ATR_sekarang) / 100  dari 100 bar terakhir
Range: [0.0 – 1.0]
```
**Artinya:** Di mana volatilitas sekarang dibandingkan 100 bar terakhir?
- `0.10` = volatilitas sangat rendah (bottom 10%) → pasar sepi
- `0.90` = volatilitas sangat tinggi (top 10%) → pasar aktif/breakout

### Fitur F1: Momentum Z-Score (Kekuatan Momentum)
```
Formula: (close - mean_close_20) / std_close_20
Range: -3 hingga +3
```
**Artinya:** Berapa standar deviasi harga sekarang dari rata-rata 20 candle?
- `+2.5` = harga jauh di atas rata-rata → strong bullish momentum
- `-2.5` = harga jauh di bawah rata-rata → strong bearish momentum
- `0.0` = harga tepat di rata-rata → pasar flat

### Fitur F2: Swing Proximity (Jarak ke Swing Level)
```
Formula: (swing_level - close) / ATR  (signed)
Range: ±10
```
**Artinya:** Seberapa dekat harga ke swing high/low terdekat (20 bar)?
- Positif = harga di bawah swing (mendekat resistance)
- Negatif = harga di atas swing (mendekat support dari atas)
- `0` = harga tepat di swing level

### Fitur F3: Body Dominance (Kekuatan Candle)
```
Formula: body_size / (high - low)
Range: [0.0 – 1.0]
```
**Artinya:** Seberapa dominan body dibanding total range candle?
- `0.0` = doji (tidak ada body, banyak wick) → ketidakpastian
- `1.0` = full body tanpa wick → keyakinan kuat

### Fitur F4: HTF Trend Slope (Arah Trend)
```
Formula: linear_regression_slope(20 close) / ATR
Range: ±10
```
**Artinya:** Kemiringan trend dalam satuan ATR?
- Positif = uptrend
- Negatif = downtrend
- `0` = flat/sideways

### Fitur F5: Liquidity Proximity (Dekat Level Likuiditas)
```
Formula: 1 - (jarak_ke_cluster / (2 × ATR))
Range: [0.0 – 1.0]
```
**Artinya:** Seberapa dekat harga ke area support/resistance (cluster)?
- `1.0` = tepat di area S/R → reversal potential tinggi
- `0.0` = jauh dari semua area S/R

### Ringkasan Visual

```
F0  Volatility    [░░░░░░░░░░] rendah ← → tinggi
F1  Momentum      [-3 ←————→ 0 ←————→ +3] bearish/bullish
F2  Swing Dist    [negatif ←→ 0 ←→ positif] atas/bawah swing
F3  Candle Body   [░░░░░░░░░░] doji ← → full body
F4  Trend Slope   [negatif ←→ 0 ←→ positif] down/flat/up
F5  Liquidity     [░░░░░░░░░░] jauh ← → dekat S/R
```

---

## 4. State HMM

Setelah HMM dilatih, ia mengelompokkan setiap candle ke dalam **K state** (jumlah state dipilih otomatis 4-8 berdasarkan BIC score — ukuran kualitas model).

### State adalah Cluster Kondisi Pasar

Misalkan model menemukan 5 state:

| State | Warna UI | Kondisi Tipikal | F0 (vol) | F1 (mom) | F3 (body) | F4 (trend) |
|-------|----------|-----------------|----------|----------|-----------|------------|
| S0 | Hijau | Trending Up Kuat | Tinggi | +2 sd | Tinggi | +5 |
| S1 | Merah | Trending Down Kuat | Tinggi | -2 sd | Tinggi | -5 |
| S2 | Amber | Ranging/Choppy | Rendah | ±0.5 | Rendah | ±1 |
| S3 | Biru | Breakout/Volatil | Sangat tinggi | ±1 | Sedang | Berubah |
| S4 | Ungu | Retest/Pullback | Sedang | ±1 | Sedang | +3 (tapi pullback) |

> **PENTING:** Label state (S0 = Trending Up, dll) tidak ditentukan otomatis oleh sistem — kamu harus **menginterpretasikannya sendiri** dengan melihat backtest dan pola chart yang cocok. State hanyalah angka (0, 1, 2, ...).

### Cara Mengetahui Arti Setiap State

1. Jalankan backtest untuk theory dengan pattern yang sederhana (misalnya hanya S0 saja)
2. Lihat `state_distribution` — state mana yang paling sering muncul?
3. Lihat `best_seq_repr` — urutan state mana yang paling menguntungkan?
4. Eksplorasi di chart mana state tertentu sering muncul

---

## 5. Langkah 1: Training HMM Model

### Halaman: **HMM Models**

Ini adalah langkah pertama dan fondasi seluruh sistem. Model HMM harus dilatih sebelum apapun bisa berjalan.

### Apa yang terjadi saat Training?

```
Data OHLC (mis. XAUUSDm M15, 2023-2024)
    ↓
Ekstrak 6 fitur per candle → Matrix (N, 6)
    ↓
Normalize fitur (StandardScaler)
    ↓
Latih GaussianHMM dengan K = 4, 5, 6, 7, 8
    ↓
Pilih K terbaik berdasarkan BIC score (semakin kecil = semakin baik)
    ↓
Simpan model + scaler ke database
    ↓
Model siap dipakai untuk klasifikasi dan backtest
```

### Cara Penggunaan di UI

1. Buka menu **HMM Models**
2. Isi form:
   - **Instrument**: `XAUUSDm` (sesuaikan dengan symbol MT5 kamu)
   - **Timeframe**: `M15` (recommended untuk Aggressive Engine)
   - **Date From**: Minimal 6 bulan ke belakang (mis. `2024-01-01`)
   - **Date To**: Kemarin atau hari ini (mis. `2025-12-31`)
3. Klik **Train Model**
4. Sistem akan return **Job ID** — training berjalan di background
5. Tunggu beberapa menit, refresh tabel
6. Model muncul dengan kolom: Version, Instrument, TF, K States, BIC Score, Status

### Parameter yang Perlu Diperhatikan

| Parameter | Rekomendasi | Alasan |
|-----------|-------------|--------|
| Date range | Minimal 6 bulan, ideal 1-2 tahun | Data lebih banyak = model lebih akurat |
| Timeframe | Sama dengan TF yang akan dipakai live | Model M15 hanya valid untuk sinyal M15 |
| Instrument | Sama persis dengan symbol MT5 | `XAUUSDm` ≠ `XAUUSD` ≠ `XAUUSDc` |

### Kenapa BIC Score Penting?

BIC (Bayesian Information Criterion) mengukur trade-off antara fit model dan kompleksitas. Model dengan K=8 selalu lebih fit dari K=4, tapi bisa **overfit**. BIC memberikan penalti untuk kompleksitas.

```
BIC rendah → Model lebih baik
Contoh:
  K=4: BIC = -52,400  ← lebih baik
  K=5: BIC = -52,100
  K=6: BIC = -51,800  ← lebih buruk (overfit)
```

Sistem otomatis memilih K terbaik — kamu tidak perlu khawatir soal ini.

### Checklist Sebelum Lanjut

- [ ] Training berhasil (status: completed)
- [ ] Model muncul di tabel dengan BIC score
- [ ] Instrument dan timeframe sesuai dengan rencana trading

---

## 6. Langkah 2: Membuat Pattern

### Halaman: **Patterns**

Pattern adalah **urutan state** yang kamu percaya sebagai sinyal entry yang bagus. Ini adalah "jantung" dari strategi HMM.

### Analogi Pattern

Bayangkan kamu mau masuk BUY di Gold. Setup favorit kamu adalah:
1. Pasar sedang **pullback** (Retest setelah trend)
2. Lalu muncul **momentum bullish** kembali
3. Disertai **body candle kuat**

Dalam bahasa HMM: `[S4, S0, S0]` — tergantung arti S4 dan S0 di model kamu.

### Cara Penggunaan di UI

1. Buka menu **Patterns**
2. Klik **New Pattern**
3. Isi form:
   - **Code**: Kode pendek, misalnya `GOLD_BUY_RETEST_V1` (alphanumeric, no spasi)
   - **Name**: Nama deskriptif, misalnya `Gold Buy — Retest after Trend`
   - **Timeframe**: `M15` (harus sama dengan model dan plan live)
4. Bangun **State Sequence**:
   - Klik dropdown state pertama, pilih angka state (0–5 atau 0–7 tergantung K model)
   - Klik **+ Add State** untuk state berikutnya
   - Ulangi sampai pattern selesai
5. Preview akan menampilkan chip warna: `S4 → S0 → S0`
6. Klik **Create Pattern**

### Aturan Pattern — Opsi A (Ordered Subsequence)

Pattern di TradeOS menggunakan **Opsi A matching** — state dalam pattern harus muncul **secara berurutan** di data nyata, tapi **boleh ada state lain di antaranya**.

```
Pattern kamu:   [4, 0, 0]
Data aktual:    [2, 4, 1, 0, 3, 0]   → MATCH (score = 3/3 = 1.00)
Data aktual:    [2, 4, 3, 3, 3, 2]   → PARTIAL (score = 1/3 = 0.33) — hanya S4 yang cocok
Data aktual:    [0, 4, 0, 2, 2, 1]   → PARTIAL (score = 2/3 = 0.67) — S4 dan S0 pertama cocok, S0 kedua tidak setelah S0 pertama
```

Sistem akan **fire signal** jika score ≥ similarity_threshold (default 0.60 = 60%).

### Strategi Menentukan Pattern

#### Cara A — Eksplorasi Backtest (Recommended)

1. Buat pattern dengan hanya 1-2 state (misal `[0]` saja)
2. Backtest dengan threshold 0.60
3. Lihat `best_seq_repr` di hasil — urutan state apa yang paling menguntungkan?
4. Buat pattern baru berdasarkan temuan tersebut
5. Iterasi

#### Cara B — Intuisi Trading

Jika kamu sudah paham kondisi pasar mana yang biasanya profitable:
- BUY setup sering keluar setelah pullback → cari state yang "pullback-like" (body kecil, trend masih up)
- Breakout setup → cari state dengan volatilitas tinggi (F0 tinggi)
- Reversal → cari state dekat S/R (F5 tinggi)

#### Cara C — Mulai Sederhana

Mulai dengan pattern **1 state** saja, lihat hasil backtest, lalu perpanjang jika perlu.

### Tips Pattern

```
Pattern terlalu panjang → Jarang match → Sedikit sinyal (tapi lebih selektif)
Pattern terlalu pendek  → Sering match → Banyak sinyal (tapi less selective)

Ideal: 2-4 state, threshold 0.60-0.75
```

---

## 7. Langkah 3: Membuat Theory

### Halaman: **Theory Builder** (menu Theories → + New Theory)

Theory adalah **kerangka strategi** yang menggabungkan:
- Instrumen dan arah trade
- Threshold sinyal
- Minimum confidence (probabilitas menang)

Theory sendiri belum "lengkap" — masih perlu factor/pattern di langkah berikutnya.

### Cara Penggunaan di UI

1. Buka menu **Theories** → klik **+ New Theory** (atau navigasi ke `/theories/new`)
2. Isi form:

| Field | Contoh Nilai | Penjelasan |
|-------|-------------|------------|
| **Name** | `Gold M15 BUY Retest` | Nama deskriptif unik |
| **Description** | `Setup: Retest level setelah trend up M15` | Catatan setup-mu |
| **Instrument** | `XAUUSDm` | Symbol MT5 yang akan dipakai |
| **Direction** | `LONG` | `LONG` = BUY only, `SHORT` = SELL only, `BOTH` = dua arah |
| **Threshold** | `60` | Score composite minimum (1-100) untuk emit sinyal |
| **Min Confidence** | `55` | Minimum win rate Bayesian (50-100%) |

3. Klik **Create Theory**
4. Sistem redirect ke halaman **Theory Detail**

### Memahami Threshold dan Min Confidence

**Threshold (Composite Score)**:
- Score dihitung dari semua factor yang ditambahkan ke theory
- Semakin tinggi threshold → sinyal lebih jarang, tapi lebih terseleksi
- Default yang bagus: `55-65`

**Min Confidence (Bayesian Win Probability)**:
- Probability win berdasarkan data historis
- `55` artinya: hanya entry jika Bayesian P(win) ≥ 55%
- Lebih tinggi = lebih konservatif
- Default yang bagus: `55-60`

---

## 8. Langkah 4: Menambahkan Factor ke Theory

### Halaman: **Theory Detail** (klik theory di list Theories)

Factor adalah **aturan entry tambahan** dalam theory. Ada dua jenis:

### Jenis Factor

| Jenis | Code | Fungsi |
|-------|------|--------|
| `state_sequence_match` | Pattern HMM | Apakah urutan state cocok dengan pattern? |
| `c_code_condition` | C-Code key | Kondisi teknikal tambahan (trend, session, dll) |
| `pattern_match` | Pattern | Match terhadap pattern yang lebih kompleks |

### Menambahkan Factor HMM Pattern (Wajib!)

Untuk Signal Engine bisa berjalan, theory **harus** punya minimal 1 factor dengan **Pattern linked** (state sequence). Tanpa ini, Signal Engine tidak bisa menemukan `pattern_states`.

1. Di halaman Theory Detail, klik **+ Add Factor**
2. Pilih **Factor Code**: `HMM_STATE_SEQ_MATCH`
3. Pilih **Type**: `state_sequence_match`
4. **Decision Points**: `10` (bobot factor ini dalam composite score)
5. **Timeframe**: `M15` (harus sama)
6. **Required**: centang jika factor ini wajib terpenuhi (recommended: centang)

> Catatan: Linking pattern ke factor saat ini dilakukan secara internal via database. Pastikan pattern sudah dibuat sebelum ini.

### Factor C-Code Opsional (Untuk Filter Tambahan)

Beberapa C-Code yang berguna:

| C-Code | Fungsi | Kapan Dipakai |
|--------|--------|---------------|
| `MARKET_TRENDING` | Hanya trade saat ada trend | Setup trend-following |
| `ABOVE_200EMA` | Hanya BUY di atas 200 EMA | Setup bullish bias |
| `SESSION_LONDON` | Hanya trade saat London session | Menghindari low-volume |
| `SESSION_NY` | Hanya trade saat NY session | Liquidity tinggi |
| `ATR_NORMAL` | ATR dalam range normal | Hindari choppy/breakout ekstrem |
| `CANDLE_MOMENTUM_BULL` | Bullish candle momentum | Konfirmasi arah |
| `HTF_BIAS_BULLISH` | Higher TF trend bullish | Multi-TF confluence |

### Contoh Setup Factor untuk Gold BUY

```
Factor 1:
  Code: HMM_STATE_SEQ_MATCH
  Type: state_sequence_match
  DecisionPt: 10
  Required: Ya

Factor 2 (opsional):
  Code: MARKET_TRENDING
  Type: c_code_condition
  DecisionPt: 5
  Required: Tidak

Factor 3 (opsional):
  Code: SESSION_LONDON
  Type: c_code_condition
  DecisionPt: 3
  Required: Tidak
```

---

## 9. Langkah 5: Backtest

### Halaman: **Backtest**

Setelah theory lengkap, uji performanya di data historis sebelum live.

### Cara Penggunaan di UI

1. Buka menu **Backtest**
2. Isi form:
   - **Theory**: Pilih theory yang sudah dibuat
   - **Instrument**: `XAUUSDm`
   - **Timeframe**: `M15`
   - **Date From**: Periode test (mis. `2024-01-01`)
   - **Date To**: Akhir periode (mis. `2025-06-01`)
3. Klik **Run Backtest**
4. Sistem return Job ID, job berjalan di background
5. Status update: queued → running → completed/failed

### Yang Terjadi di Balik Layar

```
1. Ambil data OHLC historis (dateFrom → dateTo)
2. Ekstrak 6 fitur untuk setiap candle
3. Load HMM model untuk (instrument, timeframe)
4. Viterbi decode seluruh data → array state
5. Loop setiap candle:
   a. Ambil 10 state terakhir
   b. Hitung similarity dengan pattern_states
   c. Jika similarity ≥ threshold → catat sinyal
   d. Simulasi TP = entry ± 2×ATR
      Simulasi SL = entry ∓ 1×ATR
   e. Lookahead 20 candle → Win/Loss/Breakeven
6. Hitung semua metrik
7. Simpan hasil
```

### Parameter Backtest di Kode

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| `SEQ_WINDOW` | 10 | Panjang jendela state yang dibandingkan |
| `LOOKBACK` | 50 | Bar minimum sebelum sinyal bisa muncul |
| `TP_ATR_MULT` | 2.0 | TP = 2× ATR dari entry |
| `SL_ATR_MULT` | 1.0 | SL = 1× ATR dari entry (RR = 2:1) |
| `MAX_BARS_TO_OUTCOME` | 20 | Lookahead untuk cek TP/SL |
| `DEFAULT_SIMILARITY` | 0.60 | Threshold default similarity |

---

## 10. Langkah 6: Membaca Hasil Backtest

Hasil backtest menampilkan metrik berikut:

### Metrik Utama

| Metrik | Ideal | Waspada Jika |
|--------|-------|--------------|
| **Win Rate** | > 50% | < 45% |
| **Profit Factor** | > 1.3 | < 1.0 |
| **Sharpe Ratio** | > 1.0 | < 0.5 |
| **Max Drawdown** | < 20% | > 35% |
| **Total Signals** | > 50 | < 20 (kurang sampel) |

### Cara Membaca Hasil

#### Win Rate 55%, Profit Factor 1.4 → Layak Live
```
Dari 100 sinyal:
  55 menang × 2 pips = +110 pips
  45 kalah × 1 pip  = -45 pips
  Net: +65 pips, PF = 110/45 = 2.44
```

#### Win Rate 45%, Profit Factor 0.9 → Jangan Live
```
Sistem merugi di jangka panjang — ganti pattern atau ubah threshold
```

#### Total Signals = 8 → Sampel Terlalu Sedikit
```
Pattern terlalu spesifik (threshold terlalu tinggi atau pattern terlalu panjang)
→ Turunkan threshold atau perpendek pattern
```

### Interpretasi best_seq_repr

`best_seq_repr` menunjukkan urutan state yang paling menguntungkan, misalnya `S4S0S0`.

Ini artinya: pasar yang melewati S4 lalu S0 dua kali berturut-turut paling sering menghasilkan trade menang. Gunakan ini untuk **memperbarui pattern** kamu!

### Iterasi Pattern Berdasarkan Backtest

```
Backtest Pertama:
  Pattern: [0]
  Win rate: 52%, PF: 1.1
  best_seq_repr: "S4S0S0"

Update Pattern:
  Pattern: [4, 0, 0]   ← tambah S4 di depan

Backtest Kedua:
  Win rate: 58%, PF: 1.4  ← lebih baik!
  Total signals: 45        ← masih cukup banyak

→ Siap untuk live!
```

---

## 11. Langkah 7: Signal Engine (Live)

### Halaman: **Live** (badge HMM di header)

Setelah backtest memuaskan, aktifkan Signal Engine untuk monitoring real-time.

### Cara Mengaktifkan

1. Buka halaman **Live Trading**
2. Klik badge **HMM** di header (pojok kanan atas, di samping "Live Trading")
3. Di dropdown → pilih tab **ENGINE**
4. Di section "QUICK START":
   - **Theory**: Pilih theory yang sudah teruji di backtest
   - **Timeframe**: `M15`
5. Klik **▶ Start**
6. Badge HMM akan berubah dari `○ HMM offline` ke `◌ HMM · XAUUSDm`
7. Setelah bar M15 berikutnya close dan similarity ≥ threshold → badge berubah ke:
   - `● HMM · BUY 0.72 · 2m` (hijau — sinyal fresh)

### Apa yang Terjadi di Background

```
Setiap bar M15 close:
1. Fetch 60 bar terakhir dari MT5
2. Ekstrak 6 fitur
3. HMM classify → sequence state terakhir 10 bar
4. Hitung similarity dengan pattern_states dari theory
5. Jika similarity ≥ threshold:
   a. Hitung entry/TP/SL berdasarkan ATR
   b. POST sinyal ke C# callback
   c. Badge di Live page berubah warna
   d. Log sinyal ke database
6. Kamu (trader) melihat badge → keputusan: start Aggressive/Cascade atau tidak
```

### Badge Status HMM

| Badge | Warna | Artinya |
|-------|-------|---------|
| `○ HMM offline` | Abu | Signal Engine belum distart |
| `◌ HMM · XAUUSDm` | Abu | Engine running, belum ada sinyal |
| `● HMM · BUY 0.72 · 2m` | Hijau | Sinyal BUY fresh (< 5 menit lalu) |
| `◑ HMM · SELL 0.65 · 8m` | Kuning | Sinyal ada tapi mulai stale (> 5 menit) |
| `⚠` di session list | Kuning | 20+ bar tanpa sinyal — cek pattern_states |

### Integrasi dengan Aggressive Engine

Signal Engine **tidak otomatis** mengeksekusi trade (kecuali `auto_execute = true` yang tidak direkomendasikan). Ia hanya memberikan informasi.

Workflow yang direkomendasikan:
1. Signal Engine running (badge aktif)
2. Badge berubah hijau → ada setup BUY
3. Kamu evaluasi: apakah kondisi market cocok? Session London/NY?
4. Jika cocok → Start Aggressive session dengan `direction=BUY`
5. Aggressive Engine dengan `trend_guided=true` (EMA M1+M5+M15) akan filter entry secara taktis

```
HMM Signal      = Level Strategis (kapan MULAI session?)
EMA trend_guided = Level Taktis (kapan BUKA posisi?)
```

---

## 12. Workflow End-to-End dengan Contoh Nyata

### Skenario: Setup Gold BUY pada M15

#### Step 0: Persiapan Data
- MT5 sudah terhubung dengan symbol `XAUUSDm`
- Data historis tersedia dari MT5 untuk range 2024-2025

#### Step 1: Train HMM Model
```
Halaman: HMM Models
Input:
  Instrument: XAUUSDm
  Timeframe:  M15
  Date From:  2024-01-01
  Date To:    2025-12-31
→ Klik Train Model
→ Tunggu hingga status: completed
→ Catat: K=5, BIC=-52,400
```

#### Step 2: Eksplorasi State (Backtest Awal)
```
Buat Theory awal (untuk eksplorasi):
  Name: XAUUSD_M15_EXPLORE
  Instrument: XAUUSDm
  Direction: LONG
  Threshold: 60
  MinConfidence: 50

Buat Pattern eksplorasi:
  Code: EXPLORE_S0
  Sequence: [0]

Backtest:
  Theory: XAUUSD_M15_EXPLORE
  Instrument: XAUUSDm
  Timeframe: M15
  Date: 2024-01-01 to 2024-12-31

→ Baca hasil:
   - state_distribution: S0=15%, S1=25%, S2=35%, S3=10%, S4=15%
   - best_seq_repr: "S4S0S0" (win rate 61%)
   - worst_seq_repr: "S2S2S2" (win rate 38%)
```

#### Step 3: Buat Pattern Final

```
Dari eksplorasi: S4→S0→S0 adalah setup terbaik

Halaman: Patterns
  Code: GOLD_BUY_RETEST_V1
  Name: Gold M15 BUY — Retest ke Trend
  Timeframe: M15
  Sequence: [4, 0, 0]   ← S4 dulu, lalu S0 dua kali
```

#### Step 4: Buat Theory Final

```
Halaman: Theory Builder
  Name: Gold M15 BUY Retest v1
  Description: Setup retest setelah trend M15, S4→S0→S0
  Instrument: XAUUSDm
  Direction: LONG
  Threshold: 65
  MinConfidence: 55
```

#### Step 5: Tambah Factor

```
Halaman: Theory Detail (Gold M15 BUY Retest v1)
Add Factor:
  Code: HMM_STATE_SEQ_MATCH
  Type: state_sequence_match
  DecisionPt: 10
  Required: Ya
  Timeframe: M15

Add Factor (optional):
  Code: MARKET_TRENDING
  Type: c_code_condition
  DecisionPt: 5
  Required: Tidak
  Timeframe: M15
```

#### Step 6: Backtest Final

```
Halaman: Backtest
  Theory: Gold M15 BUY Retest v1
  Instrument: XAUUSDm
  Timeframe: M15
  Date: 2024-06-01 to 2025-12-31  ← data berbeda dari training!

Hasil yang diharapkan:
  Win Rate: 57%
  Profit Factor: 1.35
  Sharpe: 1.1
  Max Drawdown: 15%
  Total Signals: 68

→ Acceptable untuk live!
```

> **PENTING:** Gunakan data yang berbeda untuk backtest dan training. Jika training pakai 2024, backtest pakai 2025 untuk out-of-sample validation.

#### Step 7: Aktifkan Signal Engine

```
Halaman: Live Trading
Klik badge HMM → Tab ENGINE → QUICK START
  Theory: Gold M15 BUY Retest v1
  Timeframe: M15
→ Klik ▶ Start

Tunggu bar M15 berikutnya close...
Badge berubah: ● HMM · BUY 0.71 · 1m (hijau)
```

#### Step 8: Start Aggressive Session

```
Halaman: Live Trading → Aggressive tab
  Symbol: XAUUSDm
  Direction: BUY   ← sesuai sinyal HMM
  Layers: 10
  Volume: 0.01
  Profit Target: $0.50
  SL Multiplier: 1.0
  Trend Guided: ON  ← default
  Max Session Loss: $8.00
  Max Drawdown: $4.00
→ Start Session
```

---

## 13. Tips & Troubleshooting

### Signal Engine Berjalan Tapi Badge Tidak Berubah

**Kemungkinan:**
1. Pattern tidak cocok dengan kondisi market saat ini
2. `pattern_states` tidak ditemukan di theory (pastikan factor `HMM_STATE_SEQ_MATCH` ada)
3. HMM model belum di-load untuk instrument/timeframe ini

**Cek:**
- Lihat kolom di engine session list: jika `⚠` muncul setelah 20 bar → pattern tidak matching
- Turunkan threshold atau sederhanakan pattern

### Backtest Win Rate Rendah < 45%

**Kemungkinan:**
1. Pattern terlalu umum (semua kondisi market cocok, termasuk yang jelek)
2. Pattern salah arah — coba SHORT jika kamu testing LONG di downtrend
3. Data training dan backtest terlap (overfitting)

**Solusi:**
- Eksplorasi state distribution — state mana yang seharusnya SELL bukan BUY?
- Buat theory SHORT dengan state yang sama, bandingkan hasilnya

### Total Signals Backtest < 20

**Kemungkinan:**
1. Pattern terlalu spesifik (similarity threshold terlalu tinggi)
2. Pattern terlalu panjang (jarang cocok di data)

**Solusi:**
- Turunkan similarity threshold di backtest (coba 0.50)
- Perpendek pattern (hapus satu state)

### Terlalu Banyak Sinyal (> 200 dalam 6 bulan)

**Kemungkinan:**
1. Pattern terlalu umum (setiap bar cocok)
2. Threshold terlalu rendah

**Solusi:**
- Naikkan threshold ke 0.80+
- Perpanjang pattern (tambah state)

### Error "No pattern_states found" Saat Start Signal Engine

**Artinya:** Theory belum punya factor dengan pattern linked ke state sequence.

**Solusi:**
1. Buka Theory Detail
2. Tambah factor dengan Code `HMM_STATE_SEQ_MATCH`, Type `state_sequence_match`
3. Pastikan pattern sudah dibuat di halaman Patterns
4. Coba start engine lagi

### BIC Score Sangat Tinggi (Positif atau Mendekati 0)

**Artinya:** Model tidak fit dengan baik ke data.

**Kemungkinan:**
1. Data terlalu sedikit (< 3 bulan)
2. Instrument sangat berbeda dari yang biasa (model tidak konvergen)

**Solusi:**
- Tambah range tanggal training
- Coba ulang training (training bersifat stochastic, hasil bisa berbeda tiap run)

---

## 14. Kamus Istilah

| Istilah | Definisi |
|---------|----------|
| **HMM** | Hidden Markov Model — algoritma statistik yang mendeteksi state tersembunyi dari data berurutan |
| **State** | Kondisi pasar yang terdeteksi oleh HMM (S0, S1, S2, ...) |
| **K (n_states)** | Jumlah state dalam model HMM (dipilih otomatis 4-8 oleh BIC) |
| **BIC Score** | Bayesian Information Criterion — ukuran kualitas model (lebih kecil = lebih baik) |
| **Feature** | Salah satu dari 6 nilai terstandarisasi yang diextract dari candle |
| **ATR** | Average True Range — ukuran volatilitas, dipakai sebagai skala normalisasi |
| **Pattern** | Urutan state yang didefinisikan sebagai sinyal entry |
| **Opsi A** | Algoritma matching: pattern harus muncul berurutan tapi boleh ada state lain di antara |
| **Similarity Score** | Persentase pattern yang cocok dengan data (0.0–1.0) |
| **Threshold** | Minimum similarity score untuk trigger sinyal (default 0.60) |
| **Theory** | Kerangka strategi: instrument + direction + factor + threshold |
| **Factor** | Aturan entry dalam theory (HMM pattern, C-Code condition, dll) |
| **Backtest** | Simulasi strategi di data historis untuk evaluasi performa |
| **Signal Engine** | Proses background yang monitor bar close dan emit sinyal jika pattern match |
| **SEQ_WINDOW** | Panjang jendela state terbaru untuk dibandingkan (10 state terakhir) |
| **Viterbi** | Algoritma untuk decode urutan state paling probable dari data |
| **Win Rate** | Persentase trade yang menguntungkan |
| **Profit Factor** | Total keuntungan / total kerugian |
| **Sharpe Ratio** | Return rata-rata / volatilitas return |
| **Max Drawdown** | Penurunan terbesar dari peak equity |
| **TP/SL** | Take Profit / Stop Loss — target exit dari posisi |
| **EMA Trend Guided** | Filter taktis: EMA M1+M5+M15 vote untuk konfirmasi arah per-posisi |
| **HMM Advisory** | HMM sebagai info strategis (kapan mulai session) bukan filter per-posisi |
| **Cascade Engine** | Engine yang buka initial batch lalu topup jika trend terkonfirmasi |
| **Aggressive Engine** | Engine yang buka N layer sekaligus, tutup per-layer saat TP tercapai |

---

## Ringkasan Cepat — Checklist Siap Live

```
□ 1. Train HMM Model
      → HMM Models | Instrument, Timeframe, min 6 bulan data
      → Status: completed, ada BIC score

□ 2. Buat Pattern
      → Patterns | Code, Name, Timeframe, Sequence [angka state]
      → Sequence berdasarkan eksplorasi backtest atau intuisi trading

□ 3. Buat Theory
      → Theory Builder | Name, Instrument, Direction, Threshold=60, MinConf=55

□ 4. Tambah Factor ke Theory
      → Theory Detail | Factor: HMM_STATE_SEQ_MATCH, type: state_sequence_match
      → Tambah C-Code factor opsional (MARKET_TRENDING, SESSION_LONDON, dll)

□ 5. Backtest Theory
      → Backtest | Theory, Instrument, Timeframe, date range (out-of-sample)
      → Target: Win Rate > 50%, Profit Factor > 1.2, Total Signals > 30

□ 6. Aktifkan Signal Engine
      → Live → Badge HMM → Tab ENGINE → Quick Start → pilih theory → ▶ Start
      → Badge berubah dari abu ke hijau saat sinyal muncul

□ 7. Start Trade Engine (berdasarkan sinyal HMM)
      → Live → Aggressive/Cascade tab → Start Session
      → Trend Guided: ON (filter taktis EMA)
      → Set Profit Guard (max_session_loss, max_drawdown)
```

---

*TradeOS — Jurnal HMM v1.0 | Dibuat 2026-03-28*
*Sistem ini dirancang untuk pemahaman mendalam, bukan trading impulsif. Selalu backtest sebelum live.*
