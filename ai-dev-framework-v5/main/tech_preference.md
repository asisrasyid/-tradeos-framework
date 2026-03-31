# TECH PREFERENCE — TradeOS v5.1
## Stack Constraints | HMM + Bayesian Edition

> **For Agent:** Non-negotiable preferences. Read before every stack decision.
> Deviation requires documented justification in decision_log.md.

---

## FRONTEND
```
FRAMEWORK   : React 18+ (Vite — SPA, no SSR needed)
LANGUAGE    : TypeScript strict mode — mandatory
UI          : shadcn/ui + Tailwind CSS
STATE       : Zustand (client) + TanStack Query v5 (server)
CHARTS      : TradingView Lightweight Charts v4 (OHLC/candlestick)
              Recharts (equity curves, stat charts)
              Custom SVG (HMM state timeline, Bayesian probability gauge)
REALTIME    : @microsoft/signalr (WebSocket — matches C# SignalR)
THEME       : Dark mode default
              Colors: navy #0F172A bg, electric blue #3B82F6 accent,
                      emerald #10B981 BUY/WIN, red #EF4444 SELL/LOSS
              Font: Inter (UI), JetBrains Mono (prices, numbers, state labels)
PHILOSOPHY  : "Command Center" — every panel has an action, not just display
```

## BACKEND
```
RUNTIME     : C# — ASP.NET Core 8 Web API
PATTERN     : Modular monolith
              Modules: Pattern, Theory, Backtest, Signal, TradeLog, HMM, Bayesian
API STYLE   : REST (standard endpoints) + SignalR (WebSocket real-time)
AUTH        : JWT Bearer Token (stateless)
JOBS        : Hangfire Community (HMM training, backtest, score recalc)
ORM         : EF Core 8 (CRUD) + Dapper (complex queries, stored procs)
PYTHON CALL : HttpClient wrapper → Python sidecar (internal HTTP only)
              C# never does computation — always delegates to Python
```

## PYTHON SIDECAR
```
RUNTIME     : Python 3.11+
FRAMEWORK   : FastAPI (async, type-safe, auto-docs)
ROLE        : Computation only — called by C# backend

MANDATORY LIBRARIES:
  hmmlearn          — Gaussian HMM (state classification, Viterbi)
  smartmoneyconcepts— BOS, CHoCH, OB, FVG, liquidity, sessions
  pandas-ta         — ATR, momentum, z-score, 150+ indicators
  backtesting.py    — backtest engine per-theory
  vectorbt          — walk-forward analysis
  scipy             — percentileofscore, stats
  numpy             — matrix operations
  pandas            — data manipulation
  scikit-learn      — StandardScaler, BIC optimization
  hashlib           — SHA256 for state sequence hashing (stdlib)

DATA PROVIDERS:
  MetaTrader5       — PRIMARY: Forex + XAU intraday (free with any MT5 broker)
  yfinance          — FALLBACK: daily data, indices (NAS100)
  
NOTE: Python sidecar NOT exposed to internet — internal only
      Called via C# HttpClient on port 8000
```

## DATABASE
```
PRIMARY DB  : PostgreSQL 15+
ORM (C#)    : EF Core + Dapper
CACHE       : Redis 7 (C-Code results, HMM state cache per TF)
              TTL = candle duration (M1=60s, M5=300s, H1=3600s)
STORAGE     : HMM model pickles → PostgreSQL BYTEA (hmm_models table)

RULES:
  - UUID PKs everywhere (gen_random_uuid())
  - Soft delete (deleted_at TIMESTAMPTZ) on all major tables
  - JSONB for: state_sequence, factor_snapshot, equity_curve, state_labels
  - GIN index on trade_log.state_sequence for fast sequence queries
  - All migrations idempotent (CREATE TABLE IF NOT EXISTS)
```

## INFRASTRUCTURE
```
DEPLOYMENT  : Docker Compose (all 5 services)
SERVICES    : tradeos-db (PostgreSQL 15)
              tradeos-redis (Redis 7)
              tradeos-api (ASP.NET Core 8, port 5000)
              tradeos-python (Python FastAPI, port 8000 — internal only)
              tradeos-frontend (React/Nginx, port 3000)

CI/CD       : GitHub Actions
MONITORING  : Sentry (free tier) + Serilog structured logging
```

## CONSTRAINTS
```
MANDATORY   : React + TypeScript, ASP.NET Core C#, Python FastAPI,
              PostgreSQL, Redis, Docker Compose, hmmlearn, smartmoneyconcepts

FORBIDDEN   : Next.js / SSR frameworks, MongoDB as primary DB,
              Any LLM for pattern recognition or signal generation,
              Exact candle shape matching (cosine similarity on raw OHLC)

BUDGET      : Software = $0 (all open source)
              Infrastructure = ~$20/month VPS (optional, can run locally)

TIMELINE    : Phase 1 (Foundation) → Phase 2 (HMM Engine) →
              Phase 3 (Theory + Bayes) → Phase 4 (UI) → Phase 5 (Live)
```
