# IDEA FRAMEWORK — TradeOS v5.1
## Full System Specification | HMM + Bayesian Pattern Intelligence

**Status:** COMPLETE — All stages filled. Agent proceeds directly to implementation.
**Version:** 5.1 — HMM + Bayesian Edition (supersedes cosine similarity approach)

---

## STAGE 1 — PROJECT BRIEF

```
NAME: TradeOS — Algorithmic Trading Intelligence System

ONE LINE: Platform yang mengkodifikasi metodologi teknikal trader ke dalam
theory records yang dieksekusi secara algoritmik, dengan pattern matching
berbasis HMM state sequence dan self-learning via Bayesian probability.

PROBLEM SOLVED:
Trader harus menganalisa chart secara manual berulang-ulang. Tidak ada sistem
yang "mengingat" dan "mengeksekusi" teori teknikal secara konsisten dan terukur.
Keputusan trading tidak terrekam dengan baik sehingga tidak bisa di-improve
secara data-driven tanpa LLM.

PRIMARY USER: Solo trader dengan metodologi SMC/ICT yang ingin sistem
mengotomasi analisa, validasi, dan tracking performa.

SUCCESS LOOKS LIKE:
Sistem bisa "melihat" chart seperti trader berpengalaman — mengenali kondisi
pasar tanpa exact match, memberi probabilitas signal berdasarkan kombinasi
state + theory yang teruji backtest, dan terus improve dari data historis.

NON-NEGOTIABLES:
- React frontend + ASP.NET Core C# + Python sidecar + PostgreSQL
- Pattern = HMM state sequence, BUKAN cosine similarity candle shape
- Probability = Bayesian self-updating counter, BUKAN static weight
- No LLM — murni matematis dan probabilitas
- Backtest hanya untuk tuning/validation theory
- Instruments: Forex pairs, XAUUSD, NAS100
- Multi-timeframe: M1 hingga MN

ALL SOFTWARE IS FREE/OPEN SOURCE:
- Python libs: hmmlearn, smartmoneyconcepts, pandas-ta, backtesting.py,
  vectorbt, scipy, numpy, pandas, FastAPI — semua gratis
- Infrastructure: PostgreSQL, Redis, Docker Compose — semua gratis
- Only cost: VPS ~$20/month jika deploy ke server
```

---

## STAGE 5 — FINAL CONCEPT

### System Objective

TradeOS mengkodifikasi metodologi trading ke dalam **Theory Records** yang bisa
dieksekusi algoritmik. Sistem mendeteksi kondisi pasar via **Gaussian HMM**,
membangun **state sequence** sebagai representasi "pattern" yang scale-invariant
dan noise-tolerant, mengevaluasi theory via **weighted decision points**,
dan menghasilkan signal dengan **Bayesian probability** yang self-updating
dari setiap outcome trade.

### Core Intelligence Pipeline (12 Steps)

```
STEP 1  → Raw OHLC masuk (MT5 / yfinance)
STEP 2  → Feature extraction (scale-invariant, 6 features)
STEP 3  → HMM state classification (K=6 hidden states)
STEP 4  → State sequence = pattern (N states terakhir)
STEP 5  → C-Code evaluation (SMC conditions via smartmoneyconcepts)
STEP 6  → Theory composite scoring (decision points sum)
STEP 7  → Bayesian probability lookup P(WIN | seq, theory, instrument)
STEP 8  → Decision: BUY / SELL / WAIT + confidence %
STEP 9  → Simpan signal ke trade_log (with full snapshot)
STEP 10 → Eksekusi (Director manual di MT5, atau skip)
STEP 11 → Record outcome (WIN / LOSS / BE + pips)
STEP 12 → Update Bayesian counter + pattern_scores (self-learning)
```

### Core Philosophy

- **Probabilistic not deterministic** — sistem memberi peluang, bukan prediksi
- **State not shape** — pattern adalah kondisi pasar, bukan bentuk candle
- **Self-learning without LLM** — Bayesian counter update dari setiap outcome
- **Scale-invariant** — 20 candle dan 200 candle bisa menghasilkan state sequence sama
- **Noise-tolerant** — state dihitung dari distribusi statistik, bukan raw price
- **Command over observation** — UI dirancang untuk aksi, bukan sekadar tampilan

---

## FEATURE EXTRACTION SPECIFICATION

### 6 Scale-Invariant Features (per candle, per timeframe)

```
f0 = ATR_percentile
     → Posisi ATR saat ini vs distribusi ATR 100 candle terakhir (0.0–1.0)
     → 0.0 = volatilitas sangat rendah, 1.0 = spike tinggi
     → Formula: scipy.stats.percentileofscore(atr_100, atr_current) / 100

f1 = price_momentum_zscore
     → Z-score dari return N candle terakhir
     → Formula: (close - mean_close_N) / std_close_N
     → Normalized sehingga tidak tergantung skala harga absolut

f2 = swing_proximity_ratio
     → Jarak harga ke swing high/low terdekat, dinormalisasi per ATR
     → Formula: (swing_level - close) / ATR
     → Negatif = di bawah swing, positif = di atas swing

f3 = body_dominance
     → Rasio body candle terhadap full range (high - low)
     → Formula: abs(close - open) / (high - low + epsilon)
     → 0.0 = doji, 1.0 = full body candle

f4 = htf_trend_slope
     → Kemiringan regresi linear harga di H4 (N=20 candle H4)
     → Dinormalisasi per ATR H4
     → Positif = uptrend H4, negatif = downtrend H4

f5 = liquidity_proximity
     → Seberapa dekat harga ke liquidity pool (EQH/EQL)
     → Dari smartmoneyconcepts liquidity detection
     → 0.0 = jauh, 1.0 = tepat di zona liquidity
```

### Feature Vector per Candle

```python
F_t = [f0, f1, f2, f3, f4, f5]  # shape: (6,)
Feature matrix untuk HMM training: shape (N_candles, 6)
```

---

## HMM SPECIFICATION

### Model Architecture

```
Model: Gaussian HMM (hmmlearn.hmm.GaussianHMM)
Hidden states K: 6 (optimized via BIC criterion per instrument)
Covariance type: "full" (menangkap korelasi antar features)
Training data: minimum 1 tahun data historis per instrument
```

### Hidden States Definition (XAUUSD example)

```
S0 = Trending Bull
     Signature: f1 > 0.5 (momentum positif), f4 > 0.3 (HTF slope naik),
                f0 = 0.4–0.7 (volatilitas normal)
     Meaning: "Pasar sedang dalam uptrend yang sehat"

S1 = Trending Bear
     Signature: f1 < -0.5, f4 < -0.3, f0 = 0.4–0.7
     Meaning: "Pasar sedang dalam downtrend yang sehat"

S2 = Ranging Low Volatility
     Signature: f0 < 0.3 (ATR rendah), f1 ≈ 0 (momentum netral),
                f2 ≈ 0 (dekat middle swing)
     Meaning: "Market sideways / accumulation / distribusi"

S3 = Post-BOS Expansion
     Signature: f0 > 0.6 (volatilitas naik), f1 extreme (+/-),
                swing_proximity baru terbentuk
     Meaning: "Baru terjadi breakout / BOS, momentum kuat"

S4 = Retest / Pullback Zone
     Signature: f2 kecil (dekat ke swing level), f0 turun dari S3,
                f1 berkurang (momentum melemah)
     Meaning: "Harga kembali ke level penting setelah BOS"

S5 = High Volatility / Event
     Signature: f0 > 0.85 (ATR spike), f1 extreme
     Meaning: "Spike volatilitas — berita, event, liquidity hunt"
```

### Training Protocol

```python
# Pseudocode — implementasi di python-sidecar/services/hmm_trainer.py
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

# 1. Kumpulkan data historis (min 1 tahun, semua TF relevan)
features = extract_features_bulk(ohlc_historical)  # shape: (N, 6)

# 2. Standardize features
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

# 3. Pilih K optimal via BIC
best_k, best_bic = 4, float('inf')
for k in range(4, 9):
    model = GaussianHMM(n_components=k, covariance_type="full",
                        n_iter=100, random_state=42)
    model.fit(features_scaled)
    bic = -2 * model.score(features_scaled) + k * np.log(len(features_scaled))
    if bic < best_bic:
        best_k, best_bic, best_model = k, bic, model

# 4. Simpan model + scaler ke PostgreSQL (JSONB) atau file pickle
save_hmm_model(best_model, scaler, instrument, timeframe)
```

### State Classification (Live)

```python
def classify_state(ohlc_recent: pd.DataFrame, model, scaler) -> int:
    features = extract_features(ohlc_recent)          # shape: (1, 6)
    features_scaled = scaler.transform(features)
    state = model.predict(features_scaled)[-1]        # latest state label
    return int(state)  # 0–5
```

### Pattern Matching via Viterbi

```python
def compute_sequence_score(
    recent_features: np.ndarray,  # shape: (N, 6) — recent N candles
    model: GaussianHMM,
    scaler: StandardScaler
) -> tuple[list[int], float]:
    """
    Returns state_sequence and log_probability of that sequence.
    Higher log_prob = more consistent with trained market dynamics.
    """
    features_scaled = scaler.transform(recent_features)
    log_prob, state_seq = model.decode(features_scaled, algorithm="viterbi")
    return state_seq.tolist(), log_prob
```

---

## BAYESIAN PROBABILITY SPECIFICATION

### Data Structure

```sql
-- Stored in: bayesian_counters table
-- Key: (theory_id, state_seq_hash, instrument, timeframe)
-- Updated after every outcome recording

CREATE TABLE bayesian_counters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    state_seq_hash  VARCHAR(64) NOT NULL,  -- SHA256 of state sequence string
    state_seq_repr  VARCHAR(50) NOT NULL,  -- human-readable: "S0S0S3S2S4"
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    breakeven       INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(theory_id, state_seq_hash, instrument, timeframe)
);
```

### Probability Formula (Laplace Smoothing)

```
P(WIN | seq, theory, instrument) = (wins + α) / (total + 2α)

Where:
  α = 1  (Laplace smoothing constant — prevents P=0 or P=1 on small samples)
  
Examples:
  0 wins, 0 total  → P = (0+1)/(0+2)  = 0.500  (50% — no data, neutral)
  1 wins, 1 total  → P = (1+1)/(1+2)  = 0.667
  5 wins, 8 total  → P = (5+1)/(8+2)  = 0.600
  52 wins, 70 total→ P = (52+1)/(70+2) = 0.736  (reliable)
```

### Confidence Tier

```
total < 10   → "insufficient data" — show P but flag as unreliable
10 ≤ total < 30 → "developing" — P improving but use with caution
total ≥ 30   → "reliable" — probability is statistically meaningful
total ≥ 100  → "strong" — high confidence in the probability estimate
```

### Update Logic (after outcome recorded)

```python
def update_bayesian_counter(
    theory_id: str,
    state_sequence: list[int],
    instrument: str,
    timeframe: str,
    outcome: str  # "WIN" | "LOSS" | "BREAK_EVEN"
) -> dict:
    seq_repr = "".join(f"S{s}" for s in state_sequence)   # "S0S0S3S2S4"
    seq_hash = hashlib.sha256(seq_repr.encode()).hexdigest()[:16]

    # Upsert counter
    counter = get_or_create_counter(theory_id, seq_hash, instrument, timeframe)
    counter.total += 1
    if outcome == "WIN":      counter.wins += 1
    elif outcome == "LOSS":   counter.losses += 1
    else:                     counter.breakeven += 1

    # Compute new probability
    p_win = (counter.wins + 1) / (counter.total + 2)
    return {"p_win": p_win, "total": counter.total, "wins": counter.wins}
```

---

## DATABASE SCHEMA — FULL DEFINITION

### Table 1: patterns

```sql
CREATE TABLE patterns (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                 VARCHAR(100) UNIQUE NOT NULL,
    name                 VARCHAR(200) NOT NULL,
    description          TEXT,
    pattern_type         VARCHAR(50) NOT NULL,
    -- 'state_sequence'  ← primary type (HMM-based)
    -- 'c_code_combo'    ← pure condition combination
    -- 'composite'       ← state_sequence + c_code_combo
    timeframe            VARCHAR(10),
    state_sequence       JSONB,
    -- {"seq": [0,0,3,2,4], "min_log_prob": -8.5, "label": "S0S0S3S2S4"}
    state_seq_repr       VARCHAR(50),            -- "S0S0S3S2S4" (human-readable)
    hmm_model_version    VARCHAR(50),            -- which HMM model generated this
    source               VARCHAR(20) DEFAULT 'manual',
    -- 'manual' | 'mined_from_wins' | 'hmm_discovered'
    version              INTEGER DEFAULT 1,
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    deleted_at           TIMESTAMPTZ
);
```

### Table 2: theories

```sql
CREATE TABLE theories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    instrument      VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,   -- 'LONG' | 'SHORT' | 'BOTH'
    threshold       INTEGER NOT NULL DEFAULT 10,
    min_confidence  DECIMAL(5,2) DEFAULT 60.0, -- min P(WIN)% to fire signal
    version         INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
```

### Table 3: theory_factors

```sql
CREATE TABLE theory_factors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    pattern_id      UUID REFERENCES patterns(id),
    factor_code     VARCHAR(100) NOT NULL,
    factor_type     VARCHAR(30) NOT NULL,
    -- 'state_sequence_match'  ← HMM pattern match
    -- 'c_code_condition'      ← SMC condition
    -- 'hmm_state_current'     ← current state must be X
    decision_point  INTEGER NOT NULL,
    is_required     BOOLEAN DEFAULT FALSE,
    condition_logic TEXT,
    operator        VARCHAR(20),
    threshold_value DECIMAL(12,6),
    timeframe       VARCHAR(10),
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Table 4: trade_log

```sql
CREATE TABLE trade_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id           UUID NOT NULL REFERENCES theories(id),
    instrument          VARCHAR(20) NOT NULL,
    timeframe           VARCHAR(10) NOT NULL,
    signal_time         TIMESTAMPTZ NOT NULL,
    direction           VARCHAR(10) NOT NULL,
    entry_price         DECIMAL(12,5),
    sl_price            DECIMAL(12,5),
    tp_price            DECIMAL(12,5),
    composite_score     INTEGER NOT NULL,
    confidence_pct      DECIMAL(5,2),
    p_win_at_signal     DECIMAL(5,4),           -- Bayesian P(WIN) saat signal
    bayesian_sample_n   INTEGER,                -- berapa total sample saat signal
    state_sequence      JSONB NOT NULL,
    -- {"seq": [0,0,3,2,4], "repr": "S0S0S3S2S4", "log_prob": -8.5}
    factor_snapshot     JSONB NOT NULL,
    -- {"HTF_BIAS_BULLISH": {"met": true, "score": 1.0, "dp": 3}, ...}
    hmm_model_version   VARCHAR(50),
    outcome             VARCHAR(15),            -- 'WIN'|'LOSS'|'BREAK_EVEN'|NULL
    pnl_pips            DECIMAL(8,2),
    rr_actual           DECIMAL(6,3),
    signal_expired      BOOLEAN DEFAULT FALSE,
    executed            BOOLEAN DEFAULT FALSE,  -- apakah Director eksekusi
    closed_at           TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trade_log_theory ON trade_log(theory_id);
CREATE INDEX idx_trade_log_instrument_time ON trade_log(instrument, signal_time DESC);
CREATE INDEX idx_trade_log_state_seq ON trade_log USING GIN(state_sequence);
```

### Table 5: bayesian_counters

```sql
CREATE TABLE bayesian_counters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    state_seq_hash  VARCHAR(16) NOT NULL,
    state_seq_repr  VARCHAR(50) NOT NULL,
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    breakeven       INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    p_win_current   DECIMAL(5,4) DEFAULT 0.5000,
    confidence_tier VARCHAR(20) DEFAULT 'insufficient',
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(theory_id, state_seq_hash, instrument, timeframe)
);

CREATE INDEX idx_bayes_lookup
    ON bayesian_counters(theory_id, state_seq_hash, instrument, timeframe);
```

### Table 6: hmm_models

```sql
CREATE TABLE hmm_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    version         VARCHAR(50) NOT NULL,       -- "XAUUSD_H1_v1_20260324"
    n_states        INTEGER NOT NULL,
    bic_score       DECIMAL(12,4),
    training_from   TIMESTAMPTZ NOT NULL,
    training_to     TIMESTAMPTZ NOT NULL,
    n_samples       INTEGER NOT NULL,
    model_pickle    BYTEA NOT NULL,             -- serialized hmmlearn model
    scaler_pickle   BYTEA NOT NULL,             -- serialized StandardScaler
    state_labels    JSONB,
    -- {"0": "Trending Bull", "1": "Trending Bear", ...}
    feature_names   JSONB,
    -- ["ATR_pct", "momentum_z", "swing_prox", "body_dom", "htf_slope", "liq_prox"]
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Table 7: backtest_sessions

```sql
CREATE TABLE backtest_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    theory_version  INTEGER NOT NULL,
    hmm_model_id    UUID REFERENCES hmm_models(id),
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    date_from       TIMESTAMPTZ NOT NULL,
    date_to         TIMESTAMPTZ NOT NULL,
    params          JSONB DEFAULT '{}',
    status          VARCHAR(20) DEFAULT 'pending',
    triggered_by    VARCHAR(30) DEFAULT 'manual',
    ran_at          TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Table 8: backtest_results

```sql
CREATE TABLE backtest_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES backtest_sessions(id),
    total_signals       INTEGER DEFAULT 0,
    wins                INTEGER DEFAULT 0,
    losses              INTEGER DEFAULT 0,
    breakeven           INTEGER DEFAULT 0,
    win_rate            DECIMAL(5,2),
    profit_factor       DECIMAL(8,3),
    sharpe_ratio        DECIMAL(8,4),
    sortino_ratio       DECIMAL(8,4),
    max_drawdown        DECIMAL(5,2),
    avg_rr              DECIMAL(6,3),
    total_pips          DECIMAL(10,2),
    equity_curve        JSONB,
    state_distribution  JSONB,
    -- {"S0": 0.35, "S1": 0.10, "S2": 0.25, "S3": 0.15, "S4": 0.12, "S5": 0.03}
    best_seq_repr       VARCHAR(50),            -- best performing state sequence
    worst_seq_repr      VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### Table 9: pattern_scores

```sql
CREATE TABLE pattern_scores (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id           UUID NOT NULL REFERENCES patterns(id),
    theory_id            UUID NOT NULL REFERENCES theories(id),
    instrument           VARCHAR(20) NOT NULL,
    timeframe            VARCHAR(10),
    total_appearances    INTEGER DEFAULT 0,
    confirmed_wins       INTEGER DEFAULT 0,
    confirmed_losses     INTEGER DEFAULT 0,
    win_rate             DECIMAL(5,2),
    avg_log_prob         DECIMAL(8,4),          -- average HMM log probability
    last_updated         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pattern_id, theory_id, instrument, timeframe)
);
```

### Table 10: theory_versions

```sql
CREATE TABLE theory_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id           UUID NOT NULL REFERENCES theories(id),
    version_number      INTEGER NOT NULL,
    snapshot            JSONB NOT NULL,
    change_notes        TEXT,
    win_rate_at_save    DECIMAL(5,2),
    backtest_session_id UUID REFERENCES backtest_sessions(id),
    saved_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(theory_id, version_number)
);
```

---

## C-CODE CATALOGUE

Standard condition codes evaluated by Python sidecar via smartmoneyconcepts + pandas-ta.

### Market Structure
| Code | Library | Score |
|------|---------|-------|
| BOS_BULLISH | smartmoneyconcepts | 0/1 |
| BOS_BEARISH | smartmoneyconcepts | 0/1 |
| CHOCH_BULLISH | smartmoneyconcepts | 0/1 |
| CHOCH_BEARISH | smartmoneyconcepts | 0/1 |
| OB_BULLISH_ACTIVE | smartmoneyconcepts | 0/1 |
| OB_BEARISH_ACTIVE | smartmoneyconcepts | 0/1 |
| PRICE_IN_OB_BULL | smartmoneyconcepts | 0/1 |
| PRICE_IN_OB_BEAR | smartmoneyconcepts | 0/1 |
| FVG_BULLISH | smartmoneyconcepts | 0/1 |
| FVG_BEARISH | smartmoneyconcepts | 0/1 |
| EQH_SWEPT | smartmoneyconcepts | 0/1 |
| EQL_SWEPT | smartmoneyconcepts | 0/1 |

### Trend & Regime
| Code | Library | Score |
|------|---------|-------|
| HTF_BIAS_BULLISH | custom (HMM S0 on H4) | 0/1 |
| HTF_BIAS_BEARISH | custom (HMM S1 on H4) | 0/1 |
| HMM_STATE_CURRENT | hmmlearn | 0–5 (state label) |
| HMM_STATE_IS_RETEST | hmmlearn (S4) | 0/1 |
| HMM_STATE_IS_POST_BOS | hmmlearn (S3) | 0/1 |
| HMM_STATE_IS_RANGING | hmmlearn (S2) | 0/1 |
| MARKET_TRENDING | pandas-ta ADX | 0.0–1.0 |
| ABOVE_200EMA | pandas-ta | 0/1 |

### Momentum & Candle
| Code | Library | Score |
|------|---------|-------|
| CANDLE_MOMENTUM_BULL | pandas-ta | 0.0–1.0 |
| CANDLE_MOMENTUM_BEAR | pandas-ta | 0.0–1.0 |
| HIGH_VOLUME | pandas-ta | 0/1 |
| ATR_NORMAL | pandas-ta | 0/1 |

### Session
| Code | Library | Score |
|------|---------|-------|
| SESSION_LONDON | smartmoneyconcepts | 0/1 |
| SESSION_NY | smartmoneyconcepts | 0/1 |
| SESSION_LONDON_OPEN_KZ | smartmoneyconcepts | 0/1 |
| SESSION_NY_KZ | smartmoneyconcepts | 0/1 |

---

## API ENDPOINT CATALOGUE

### Pattern Module
```
GET    /api/patterns                        list all patterns
GET    /api/patterns/{id}                   pattern detail
POST   /api/patterns                        create pattern (manual)
POST   /api/patterns/mine-from-wins         trigger pattern mining
PUT    /api/patterns/{id}                   update pattern
DELETE /api/patterns/{id}                   soft delete
GET    /api/patterns/{id}/scores            win-rate scores per instrument
```

### Theory Module
```
GET    /api/theories                        list all theories
GET    /api/theories/{id}                   theory detail + factors
POST   /api/theories                        create theory
PUT    /api/theories/{id}                   update (auto-saves version)
DELETE /api/theories/{id}                   soft delete
GET    /api/theories/{id}/versions          version history
POST   /api/theories/{id}/rollback/{v}      rollback to version v
POST   /api/theories/{id}/factors           add factor
PUT    /api/theories/{id}/factors/{fid}     update factor
DELETE /api/theories/{id}/factors/{fid}     remove factor
```

### Backtest Module
```
POST   /api/backtest/run                    queue backtest job
GET    /api/backtest/sessions               list sessions
GET    /api/backtest/sessions/{id}/results  full results
GET    /api/backtest/compare                compare sessions
```

### Signal Module
```
GET    /api/signals/live                    current active signals
GET    /api/signals/history                 paginated history
POST   /api/signals/{id}/outcome            record WIN/LOSS/BE
WS     /hubs/signals                        real-time push (SignalR)
```

### Trade Log Module
```
GET    /api/trades                          paginated trade log
GET    /api/trades/{id}                     detail + factor snapshot
GET    /api/trades/recap                    aggregated stats
GET    /api/trades/by-theory/{id}           grouped by theory
```

### HMM Module
```
POST   /api/hmm/train                       queue HMM training job
GET    /api/hmm/models                      list trained models
GET    /api/hmm/models/{id}/states          state distribution
GET    /api/hmm/classify                    classify current state (live)
GET    /api/hmm/sequence                    get recent state sequence
```

### Bayesian Module
```
GET    /api/bayes/probability               P(WIN) for given theory+seq+instrument
GET    /api/bayes/counters/{theory_id}      all counters for a theory
GET    /api/bayes/top-sequences             best performing sequences
```

### Python Sidecar Endpoints (internal, called by C# only)
```
POST   /python/ohlc/fetch                   fetch + normalize OHLC
POST   /python/features/extract             OHLC → feature vector
POST   /python/hmm/train                    train new HMM model
POST   /python/hmm/classify                 classify state for features
POST   /python/hmm/sequence                 get state sequence + log_prob
POST   /python/ccode/calculate              compute all C-Codes
POST   /python/backtest/run                 execute backtest
POST   /python/pattern/mine-from-wins       mine patterns from WIN trades
```

---

## THEORY EXAMPLE — FULL SPEC

```
Theory: "Break & Retest Bullish — XAUUSD H1"
Instrument: XAUUSD | Direction: LONG | Threshold: 12 | Min confidence: 62%

Factors:
  ┌─────────────────────────────┬──────────┬────────┬────────────────────────────────────┐
  │ Factor Code                 │ Type     │ DP     │ Condition                          │
  ├─────────────────────────────┼──────────┼────────┼────────────────────────────────────┤
  │ HMM_STATE_SEQ_MATCH         │ pattern  │ +5     │ seq matches S0→S3→S2→S4           │
  │ HTF_BIAS_BULLISH            │ c_code   │ +3     │ H4 HMM state = S0 (trending bull)  │
  │ EQL_SWEPT                   │ c_code   │ +2     │ equal lows liquidity swept         │
  │ PRICE_IN_OB_BULL            │ c_code   │ +2     │ price in bullish OB zone           │
  │ HMM_STATE_IS_RETEST         │ c_code   │ +2     │ current state = S4 (retest)        │
  │ HMM_STATE_IS_RANGING        │ c_code   │ -4     │ current state = S2 (soft veto)     │
  │ CANDLE_MOMENTUM_BULL        │ c_code   │ +1     │ score > 0.70                       │
  │ SESSION_LONDON_OPEN_KZ      │ c_code   │ +1     │ active                             │
  └─────────────────────────────┴──────────┴────────┴────────────────────────────────────┘

Evaluation example:
  HMM seq match: 0.87 match → +5 × 0.87 = +4.35
  HTF_BIAS_BULLISH: met → +3.0
  EQL_SWEPT: met → +2.0
  PRICE_IN_OB_BULL: 0.88 → +1.76
  HMM_RETEST: met → +2.0
  HMM_RANGING: NOT met → 0 (veto not triggered — good)
  CANDLE_MOMENTUM: 0.91 → +0.91
  SESSION_LDN_KZ: met → +1.0
  ─────────────────────────────
  composite_score = 15.02
  threshold = 12 → PASSED ✓

  Bayesian lookup: theory_id + "S0S0S3S2S4" + XAUUSD + H1
  → wins=52, total=70 → P(WIN) = 53/72 = 73.6%
  → confidence tier: "reliable" (total ≥ 30)

  Final signal: BUY | score: 15.02 | confidence: 73.6% | tier: reliable
```
