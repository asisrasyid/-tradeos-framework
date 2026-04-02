# TradeOS — Algorithmic Trading Intelligence System
### v2.1 | HMM + Execution Engine Edition
### Stack: React · ASP.NET Core 8 · PostgreSQL · Python FastAPI

---

## AGENT BOOTSTRAP — READ THIS FIRST

You are an AI agent starting or resuming a development session for **TradeOS**.
Follow this sequence **without exception**:

```
STEP 1 : Read this README.md completely (you are doing this now)
STEP 2 : Read ai-dev-framework-v5/main/guide_line.md
STEP 3 : Read ai-dev-framework-v5/main/idea_framework.md   ← full spec, FILLED
STEP 4 : Read ai-dev-framework-v5/main/tech_preference.md  ← stack, FILLED
STEP 5 : Read project/ai/user.md                           ← find STATUS: start / progress
STEP 6 : Read project/ai/system_snap.md                    ← current build state
STEP 7 : Read project/ai/memory.md                         ← completed milestones
STEP 8 : Read project/ai/log.md                            ← last session activity
STEP 9 : Read ai-dev-framework-v5/output/*.md              ← all design artifacts
STEP 10: Begin work on active task in user.md
```

> **MASTER** — After reading ALL context files above, write the single word
> **"master"** at the very top of your first response. This confirms full
> context is loaded. It is mandatory — do not skip it.

> **DO NOT start from scratch** when log.md / memory.md already have entries.

---

## Language Rules

| Context | Language |
|---------|----------|
| Code, logs, artifacts, comments | **English** |
| Communication to Director | **Bahasa Indonesia** |

---

## System Architecture

```
[React :3000]
     │
     ▼
[C# ASP.NET Core :5206]  ◄──► [PostgreSQL :5432]
     │
     ▼
[Python FastAPI Sidecar :8001]
     │
     ▼
[MetaTrader 5 Terminal]
```

| Layer | Stack | Role |
|-------|-------|------|
| Frontend | React 18 + TypeScript + Vite + TailwindCSS | Dashboard, Live Trading UI, charts |
| Backend | ASP.NET Core 8 C# | REST API, auth, DB, bridge to Python |
| Python Sidecar | FastAPI + hmmlearn + pandas-ta | HMM engine, trading execution engines |
| Database | PostgreSQL 15 | OHLC cache, theories, patterns, trade logs |
| Market Data | MetaTrader 5 / yfinance | Live + historical OHLC |

---

## Intelligence Pipeline

```
Layer 1 — FEATURE EXTRACTION
  Raw OHLC → 6 scale-invariant features per candle:
  [ATR percentile, momentum z-score, swing proximity,
   body dominance, HTF slope, liquidity proximity]

Layer 2 — HMM STATE CLASSIFICATION
  Features → hidden market state (S0…S5)
  Gaussian HMM, BIC-selected K=4..8
  Viterbi decoding — each candle gets a state label

Layer 3 — PATTERN MATCHING
  State sequence → similarity vs user-defined patterns
  Markov log-probability for sequence scoring

Layer 4 — EXECUTION ENGINES
  Signal → trade decision → MT5 order execution
  Aggressive Engine: N-layer concurrent scalping
  Cascade Engine: batch pyramiding with trend confirmation
  Smart Engine: Aggressive + LLM (Claude) gate
```

**Pattern = state sequence, NOT candle shape.**
This makes matching scale-invariant and noise-tolerant across instruments and timeframes.

---

## Execution Engines (v2.1)

### Aggressive Engine
- Opens N concurrent positions (layers), closes on profit_target, reopens immediately
- Direction priority: P1 Daily S/R → P2 EMA20 M5 → P3 flip_mode → P4 hold
- HMM Gate: pauses new fills when M5+M15 analysis detects dangerous conditions (S/R trap, extreme momentum, cross-TF divergence)
- Auto Direction HMM: confidence-weighted M5+M15 vote for direction after each TP
- Limit Orders: ATR-based pending orders with auto-expiry
- MCGuard: 4-level equity protection (CAUTION/WARNING/DANGER/EMERGENCY)
- Profit Guard: floor loss + peak drawdown stop
- Poll interval: 2 seconds (direct MT5 Python API)

### Cascade Engine
- Opens initial_batch, evaluates every eval_interval seconds
- Pyramiding: adds topup_batch when M1+M5+M15 trend confirms direction
- Flip: opens new batch in opposite direction when trend reverses (old positions stay open)
- Hard SL per position (monitored) + broker-side SL (pips)
- MCGuard always active (no toggle)

### Smart Aggressive Engine
- Aggressive + LLM (Claude) gate
- AI evaluates each entry decision with configurable confidence threshold
- Rate limited: max_calls_per_hour prevents excessive API spend

---

## Project Structure

```
tradeos-framework-v2/
│
├── README.md                        ← YOU ARE HERE
│
├── ai-dev-framework-v5/
│   ├── main/
│   │   ├── idea_framework.md        ← Full system spec (FILLED)
│   │   ├── guide_line.md            ← Dev constitution
│   │   └── tech_preference.md       ← Stack constraints (FILLED)
│   ├── log/
│   │   ├── change_log.md
│   │   └── log_dev.md
│   └── output/
│       ├── framework_arc.md
│       ├── feature_list.md
│       ├── system_design.md
│       ├── frontend_design.md
│       ├── tech_stack.md
│       ├── database.md
│       ├── decision_log.md
│       ├── improvement_log.md
│       └── templates/
│
└── project/
    ├── ai/
    │   ├── user.md          ← Task register — Director writes here
    │   ├── system_snap.md   ← Current build state
    │   ├── memory.md        ← Milestone tracker
    │   └── log.md           ← Dev activity log
    ├── docs/
    │   ├── CLAUDE.md                ← Quick dev rules reference
    │   ├── guide_trade_aggressive.md← Panduan Aggressive Engine
    │   └── hmm_bayesian_spec.md     ← Math spec HMM + Bayesian
    ├── backend/
    │   └── TradeOS.Api/             ← C# ASP.NET Core 8
    ├── frontend/                    ← React 18 + TypeScript + Vite
    ├── python-sidecar/
    │   ├── main.py                  ← Entry point, 13 routers registered
    │   ├── routers/                 ← REST endpoint handlers
    │   │   ├── aggressive.py        ← /python/aggressive/*
    │   │   ├── cascade.py           ← /python/cascade/*
    │   │   ├── smart_aggressive.py  ← /python/smart-aggressive/*
    │   │   ├── signal_engine.py     ← /python/signal-engine/*
    │   │   ├── analysis.py          ← /python/analysis/multi-tf
    │   │   ├── hmm.py               ← /python/hmm/*
    │   │   ├── ohlc.py              ← /python/ohlc/*
    │   │   ├── mt5.py               ← /python/mt5/*
    │   │   ├── backtest.py          ← /python/backtest/*
    │   │   ├── pattern.py           ← /python/pattern/*
    │   │   ├── features.py          ← /python/features/*
    │   │   ├── ccode.py             ← /python/ccode/*
    │   │   └── ohlc_data.py         ← /python/ohlc-data/*
    │   ├── services/                ← Core engine logic
    │   │   ├── aggressive_engine.py ← Aggressive execution engine
    │   │   ├── cascade_engine.py    ← Cascade execution engine
    │   │   ├── smart_aggressive_engine.py
    │   │   ├── signal_engine.py     ← HMM signal loop
    │   │   ├── hmm_trainer.py       ← GaussianHMM training
    │   │   ├── hmm_classifier.py    ← Viterbi decode + pattern match
    │   │   ├── feature_extractor.py ← 6-feature extraction
    │   │   ├── mt5_executor.py      ← Direct MT5 API calls
    │   │   ├── equity_cache.py      ← Shared MCGuard state
    │   │   ├── ohlc_store.py        ← PostgreSQL OHLC cache
    │   │   ├── ohlc_syncer.py       ← Background MT5→DB sync
    │   │   ├── backtest_runner.py
    │   │   └── ccode_calculator.py  ← 27 C-codes via SMC + pandas-ta
    │   ├── docs/                    ← Panduan penggunaan engine
    │   │   ├── guide_hmm_complete.md
    │   │   ├── guide_trade_aggressive.md
    │   │   └── guide_trade_cascade.md
    │   └── requirements.txt
    └── database/
        └── migrations/              ← PostgreSQL V1–V10 SQL files
```

---

## Key Design Rules

1. **Pattern = state sequence** — matching is scale-invariant, not shape-based
2. **Viterbi decoding** for HMM state classification (not forward algorithm)
3. **Aggressive engine: direct MT5 calls** — no HTTP self-calls for orders (10–30ms latency)
4. **Cascade engine: HTTP self-calls** to `/python/mt5/*`
5. **MCGuard uses shared equity_cache** — cross-engine coordination, single EMERGENCY actor
6. **HMM Gate is permanent loop** — not one-shot; re-activates whenever conditions become dangerous again
7. **M5+M15 for HMM vote** (not M1) — M1 too noisy for HMM analysis
8. **Aggressive engine uses threading** (not asyncio) — Windows/uvicorn compatibility

---

## Director Quick Commands

```
# Start new task
→ Write new entry in project/ai/user.md, set STATUS: start

# Resume session
→ "Baca README.md. Lanjutkan dari task progress di user.md."

# Check progress
→ "Baca README.md. Buat ringkasan dari memory.md dan log.md terbaru."

# Generate specific artifact
→ "Baca README.md. Generate artifact: [nama file]"
```

---

## Super Team

| Role | Responsibility |
|------|---------------|
| Architect | Coherence, scalability, HMM integration integrity |
| Product Analyst | Real user value, scope control |
| Tech Lead | Reads tech_preference.md before every stack decision |
| UX Strategist | Command Center UX, friction elimination |
| Database Expert | Schema, JSONB discipline, query performance |
| Devil's Advocate | Stress-test HMM assumptions, execution engine edge cases |
| Scribe | Maintains all log files, append-only |

---

## Setup

Lihat `project/setup_readme.md` untuk panduan instalasi lengkap.

---

*TradeOS v2.1 | HMM State Intelligence + Aggressive/Cascade Execution Engines*
*Stack: React · ASP.NET Core 8 · Python FastAPI · PostgreSQL*
