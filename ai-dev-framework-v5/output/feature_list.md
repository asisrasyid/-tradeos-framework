# FEATURE LIST — TradeOS v5.1

## Phase 1 — Foundation
| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| 1 | PostgreSQL migrations (10 tables) | Critical | |
| 2 | Docker Compose (5 services) | Critical | |
| 3 | ASP.NET Core skeleton + modules | Critical | |
| 4 | Python FastAPI skeleton + requirements | Critical | |
| 5 | React + Vite + TS skeleton | Critical | |
| 6 | JWT auth | Critical | |

## Phase 2 — HMM Engine
| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| 7 | OHLC ingestion (MT5 + yfinance) | Critical | |
| 8 | Feature extraction (6 features) | Critical | Needs OHLC |
| 9 | HMM trainer (BIC K selection) | Critical | Needs features |
| 10 | State classifier (live) | Critical | Needs trained model |
| 11 | Viterbi state sequence decoder | Critical | Needs classifier |
| 12 | Pattern match scorer (Markov) | Critical | Needs sequence |
| 13 | HMM model storage (BYTEA) | High | |
| 14 | HMM retraining job (Hangfire) | High | Monthly schedule |

## Phase 3 — Theory + Bayesian
| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| 15 | Pattern CRUD API | Critical | |
| 16 | Theory CRUD + versioning | Critical | |
| 17 | Theory factors API | Critical | |
| 18 | C-Code calculator (all codes) | Critical | |
| 19 | Theory evaluation engine | Critical | Calls sp_evaluate_theory |
| 20 | Bayesian counter CRUD | Critical | |
| 21 | P(WIN) calculator | Critical | |
| 22 | Decision gate (SIGNAL/WATCH/SKIP) | Critical | |
| 23 | Backtest runner (backtesting.py) | High | |
| 24 | Backtest results storage | High | |
| 25 | Theory rollback | High | |

## Phase 4 — Command Center UI
| # | Feature | Priority | Status | Notes |
|---|---------|----------|--------|-------|
| 26 | App shell + routing + design tokens | Critical | ✅ Done | |
| 27 | Live signals panel (WebSocket) | Critical | ✅ Done | SignalR |
| 28 | Theory Builder page | Critical | ✅ Done | |
| 29 | Pattern Manager page | High | ✅ Done | |
| 30 | HMM State Monitor (state timeline) | High | ✅ Done | |
| 31 | Bayesian Probability Panel | High | ✅ Done | |
| 32 | Backtest Runner page | High | ✅ Done | |
| 33 | Trade Log page | High | ✅ Done | |
| 34 | OHLC chart (TradingView LW) | Medium | ⏳ Pending | |
| 35 | Equity curve (Recharts) | Medium | ✅ Done | In Backtest page |
| 36 | MT5 Terminal page | Critical | ✅ Done | Account+Positions+Order |
| 37 | MT5 Python router (7 endpoints) | Critical | ✅ Done | Verified live orders |
| 38 | MT5 C# module (Model/Service/Controller) | Critical | ✅ Done | |
| 39 | Master launcher run_all.bat | High | ✅ Done | 1-click all services |

## Phase 5 — Live Engine
| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| 40 | Real-time candle processing loop (live_feed.py) | Critical | MT5 copy_rates_from_pos |
| 41 | SignalR push on new signal | Critical | |
| 42 | Signal expiry handler | High | Per-TF window (M1=5m, H1=5h, dll) |
| 43 | Outcome recording + Bayesian update | Critical | Self-learning loop |
| 44 | Auto-order execution (HMM signal → MT5 order) | Critical | Uses /python/mt5/order |
| 45 | Open position monitor (SL/TP hit detection) | High | |
| 46 | Circuit breaker + daily risk limit | High | Max loss per day |

## MVP Definition
Phases 1–4 complete + items 36, 37, 39 from Phase 5.
