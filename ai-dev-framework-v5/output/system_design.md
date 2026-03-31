# SYSTEM DESIGN — TradeOS v5.1

## File Structure

### Backend (C#)
```
backend/TradeOS.Api/
  Modules/
    Pattern/Controllers/PatternController.cs
    Theory/Controllers/TheoryController.cs  | TheoryController.cs
    Backtest/Controllers/BacktestController.cs
    Signal/Controllers/SignalController.cs
    TradeLog/Controllers/TradeLogController.cs
    HMM/Controllers/HmmController.cs
    Bayesian/Controllers/BayesianController.cs
    MT5/                                      ← BARU (Phase 4)
      Controllers/MT5Controller.cs            ← 7 endpoints /api/mt5/*
      Services/MT5Service.cs                  ← calls Python /python/mt5/*
      Models/MT5Models.cs                     ← 11 record types

  Infrastructure/
    Python/
      PythonClient.cs     ← HttpClient wrapper, JsonOpts SnakeCaseLower
      IPythonClient.cs
    Jobs/
      BacktestJob.cs | HmmTrainingJob.cs | BayesianRecalcJob.cs
```

### Python Sidecar
```
python-sidecar/
  main.py               ← registers all 7 routers
  start.bat             ← kill port 8001 + clear cache + uvicorn (no --reload)
  routers/
    ohlc.py             ← /python/ohlc/*
    features.py         ← /python/features/*
    hmm.py              ← /python/hmm/*
    ccode.py            ← /python/ccode/*
    backtest.py         ← /python/backtest/*
    pattern.py          ← /python/pattern/*
    mt5.py              ← /python/mt5/*  ← BARU (Phase 4)
      POST /connect      — login MT5
      GET  /account      — account info
      POST /ohlc         — OHLC bars
      POST /order        — market order BUY/SELL
      POST /close        — close position by ticket
      GET  /positions    — all open positions
      DELETE /disconnect — shutdown MT5
  services/
    data_service.py         ← MT5 + yfinance ingestion
    feature_extractor.py    ← 6 features implementation
    hmm_trainer.py          ← GaussianHMM + BIC selection
    hmm_classifier.py       ← live state classification
    sequence_decoder.py     ← Viterbi + pattern match score
    ccode_calculator.py     ← all C-Codes via smc + pandas-ta
    backtest_runner.py      ← full replay loop
    pattern_miner.py        ← mine patterns from WIN trades
  lib_local/              ← MetaTrader5 DLL + numpy/pandas (Windows-only)
  requirements.txt

MT5 Notes:
  - Exness symbol suffix: m (XAUUSDm, EURUSDm, GBPUSDm)
  - JANGAN .upper() pada symbol — akan merusak suffix
  - OrderRequest: Pydantic aliases slPips/tpPips + populate_by_name=True
  - TF_MAP: M1=1, M5=5, H1=16385, H4=16388, D1=16408
```

### Frontend (React)
```
frontend/src/
  pages/
    Live.tsx           ← Command Center (default)
    Theories.tsx       | TheoryBuilder.tsx | TheoryDetail.tsx
    Patterns.tsx       | HMMModels.tsx
    Backtest.tsx       | TradeLog.tsx
    Login.tsx          ← JWT auth
    MT5Terminal.tsx    ← Trading terminal  ← BARU (Phase 4)
      - Account panel: balance, equity, margin, profit (auto-refresh 3s)
      - Positions table: ticket, type, vol, price, SL/TP, profit, Close button
      - New Order panel: symbol, BUY/SELL, volume, SL pips, TP pips
  components/
    layout/AppLayout.tsx  ← sidebar nav (termasuk MT5 Terminal link)
  store/
    authStore.ts       ← Zustand persist: token, setToken, logout
  lib/
    api.ts             ← semua API calls termasuk 6 MT5 methods
    signalr.ts         ← SignalR HubConnection
  styles/tokens.css    ← full design token system
```

### Database
```
database/migrations/
  V1__create_tables.sql   ← all 10 tables
  V2__indexes.sql         ← all indexes including GIN
  V3__stored_procs.sql    ← sp_evaluate_theory + helpers
  V4__seed_ccodes.sql     ← C-Code definitions seed data
```

## Critical Implementation Order
```
1. V1__create_tables.sql     (everything depends on this)
2. V2__indexes.sql
3. V3__stored_procs.sql
4. Docker Compose + services run
5. Python feature_extractor.py
6. Python hmm_trainer.py + hmm_classifier.py
7. Python ccode_calculator.py
8. C# Theory + Pattern CRUD
9. C# Theory evaluation engine (calls sp_evaluate_theory)
10. C# Bayesian service
11. C# Signal generation + SignalR
12. React skeleton + live panel
```
