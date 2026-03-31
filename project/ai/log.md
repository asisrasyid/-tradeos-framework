# DEV LOG — TradeOS v5.1
## Full Activity Log | English Only | Append Only

---

## [2026-03-24 00:00] — session:v51-framework-init

**Phase:** Pre-development
**Task:** Framework v5.1 documentation — HMM + Bayesian upgrade

### Done
- Rebuilt complete framework from scratch for HMM + Bayesian architecture
- Wrote full intelligence pipeline spec (12 steps, Raw OHLC → self-learning)
- Feature extraction: 6 scale-invariant features with Python code
  (ATR percentile, momentum z-score, swing proximity, body dominance,
   HTF slope, liquidity proximity)
- HMM spec: GaussianHMM, BIC K selection, state labeling, training protocol
- Viterbi decoding for state sequence generation
- Pattern matching via Markov transition probability (replaces cosine similarity)
- Scale invariance proof: same state sequence regardless of absolute price level
- Bayesian P(WIN) with Laplace smoothing, confidence tiers
- Decision gate: SIGNAL | WATCH | SKIP (not binary)
- 10-table schema (2 new tables: hmm_models, bayesian_counters)
- Extended trade_log: state_sequence JSONB, p_win_at_signal, hmm_model_version
- Extended C-Code catalogue: HMM state codes (HMM_STATE_CURRENT, HMM_STATE_IS_RETEST, etc)
- Extended API: HMM module (5 endpoints) + Bayesian module (3 endpoints)
- Theory example with full numeric walkthrough
- hmm_bayesian_spec.md: complete Python pseudocode for all components
- CLAUDE.md: HMM state color system, Bayesian quick formula
- All project/ai/ context files written

### In Progress
- None — documentation phase complete

### Blockers
- None

### Next
- Agent reads README.md, writes "master"
- Phase 1: V1__create_tables.sql through Docker Compose setup
- Refer to project/ai/user.md URUTAN [1]

---

## [2026-03-24 00:30] — session:phase1-foundation

**Phase:** Foundation
**Task:** URUTAN [1] — Build TradeOS from scratch, Phase 1

### Done
- Created PostgreSQL database `tradeos` (localhost:5432, pg18)
- Executed V1__create_tables.sql — 10 tables created
- Executed V2__indexes.sql — 23 indexes created
- Executed V3__stored_procs.sql — fn_set_updated_at, sp_evaluate_theory, fn_update_bayesian_counter
- Executed V4__seed_ccodes.sql — 27 C-Code patterns seeded
- Scaffolded ASP.NET Core 8 project (TradeOS.Api)
  - NuGet: EF Core 8, Npgsql, Dapper, JWT, Hangfire, SignalR, Redis, Serilog, Swagger
  - 7 modules with controllers, services, models, interfaces
  - TradeOsDbContext with all 10 entities
  - PythonClient HttpClient wrapper
  - Program.cs with full DI wiring
  - appsettings.json configured for local DB
  - BUILD: 0 errors, 0 warnings ✅
- Scaffolded Python FastAPI sidecar
  - requirements.txt (all mandatory: hmmlearn, smartmoneyconcepts, pandas-ta, etc.)
  - 6 routers: ohlc, features, hmm, ccode, backtest, pattern
  - models/schemas.py with all Pydantic models
  - Feature extraction: all 6 scale-invariant features implemented
  - HMM training: BIC K selection (4–8), state auto-labeling
  - Viterbi sequence decoding
  - C-Code evaluation via smartmoneyconcepts + pandas-ta
- Scaffolded React 18 + Vite frontend
  - npm packages: Tailwind v4, TanStack Query v5, Zustand, SignalR, react-router-dom
  - tokens.css: HMM state colors, navy bg, emerald/red buy/sell
  - 7 pages: Live, Theories, TheoryBuilder, Patterns, Backtest, TradeLog, HMMModels
  - API client (lib/api.ts) with full typed methods
  - SignalR client (lib/signalr.ts)
  - AppLayout with sidebar nav
  - BUILD: 0 errors ✅
- Written Docker Compose (5 services + Dockerfiles + nginx.conf + .env.example)

### In Progress
- None — all Phase 1 checklist items complete

### Blockers
- None

### Next
- Phase 2: HMM Engine
  - Implement IHmmTrainingJob (Hangfire job that calls Python /train + saves model to DB)
  - Implement IPatternMiningJob
  - Wire live signal generation pipeline (C# evaluates theories → calls Python → generates trade_log)
  - Auth endpoint (POST /api/auth/login) for JWT token
  - Connect frontend to live backend

---

---

## [2026-03-24] — session:v51-phase2-hmm-engine

**Phase:** Phase 2 — HMM Engine
**Task:** Build all HMM computation services (Python + C#)

### Done

**Python services (project/python-sidecar/services/):**
- `feature_extractor.py` — 6 scale-invariant features from OHLC (N, 6) matrix.
  Unit tests: 15/15 passed. Tested shape, range validity, directionality, scale invariance.
- `hmm_trainer.py` — GaussianHMM BIC K=4..8 selection. HmmTrainResult dataclass.
  State auto-labeling via un-standardized means (Trending Bull/Bear, Ranging, Post-BOS, etc.)
- `hmm_classifier.py` — HmmClassifier singleton with in-memory (instrument, timeframe) cache.
  classify_current_state(), get_state_sequence() Viterbi, compute_pattern_match_score()
  using Markov transition probability. Score = 0.7×Markov + 0.3×exact_match.
- `ccode_calculator.py` — 27 C-Codes: SMC (BOS/CHoCH/OB/FVG/Liquidity/Sessions) +
  TA (ADX/EMA200/RSI/ATR/Volume) + HMM state injection. Graceful degradation if lib missing.

**Routers refactored:**
- `routers/features.py` → delegates to services/feature_extractor.py
- `routers/hmm.py` → uses services/hmm_trainer + hmm_classifier. asyncpg DB loading.

**C# backend (project/backend/TradeOS.Api/):**
- `Infrastructure/Jobs/HmmTrainingJob.cs` — Hangfire IHmmTrainingJob implementation.
  Flow: POST /python/hmm/train → base64 decode → ExecuteUpdateAsync(deactivate old) → INSERT hmm_models.
- `Modules/Signal/Services/SignalService.cs` — 9-step EvaluateTheoryAsync pipeline:
  OHLC → features → HMM classify+sequence → H4 HMM → C-codes → pattern match →
  sp_evaluate_theory → Bayesian P(WIN) → INSERT trade_log → SignalR push.
- `Modules/Auth/Controllers/AuthController.cs` — POST /api/auth/login → JWT HS256.
  SHA256 password hash validation. appsettings Auth:Username + Auth:PasswordHash.
- Updated: ISignalService (added EvaluateTheoryAsync), appsettings.json (Auth+JwtExpiry),
  Program.cs (IHmmTrainingJob scoped registration).
- Build: 0 errors, 0 warnings ✅

### Blockers
- None

### Next (Phase 3 — Integration)
- Python ccode router: wire `/python/ccode/evaluate` to call sp_evaluate_theory via asyncpg
- MT5 live tick integration (replace yfinance fallback in dev)
- Redis OHLC cache (5-min expiry) for SignalService OHLC fetch
- Frontend: wire Live page to SignalR NewSignal events
- End-to-end test: POST /api/hmm/train → job runs → classify → evaluate theory → SIGNAL

---

---

## [2026-03-24] — session:v51-phase3-bayesian-engine

**Phase:** Phase 3 — Theory + Bayesian + Backtest Engine

### Done

**C# fixes and completions:**
- `TradeLogService.cs` — Added `Guid? theoryId` filter to ListAsync.
  RecordOutcomeAsync: EF transaction → update outcome fields → BayesianService.UpdateCounterAsync
  (seqRepr built from JSON int array `[0,0,3,2,4]` → "S0S0S3S2S4") → pattern_scores bulk update
  (TotalAppearances++, ConfirmedWins/Losses++, WinRate recomputed). Rollback on exception.
- `TheoryService.RollbackAsync` — Now saves current state as a new version BEFORE restoring target.
- `SignalService.GetLiveSignalsAsync` — Expiry sweep with per-TF windows + ExecuteUpdateAsync.
- `Infrastructure/Jobs/BacktestJob.cs` — Created. Calls /python/backtest/run → stores results.
- `Program.cs` — IBacktestJob → BacktestJob registered.
- Build: 0 errors, 0 warnings ✅

**Python:**
- `services/backtest_runner.py` — Full replay loop. Features → HMM → C-codes → score →
  TP/SL simulation (ATR×2/×1) → equity curve → Sharpe/Sortino/max_drawdown/state_dist.
- `routers/backtest.py` — Refactored to delegate to services/backtest_runner.py.

**Database:**
- `V5__sp_save_theory_version.sql` — executed. sp_save_theory_version() + fn_expire_signals().

### Blockers
- None

### Next (Phase 4 — Frontend + Integration)
- React: wire all 7 pages to real C# API (TanStack Query, real endpoints)
- Live page: SignalR connection → real-time NewSignal display with HMM state chip
- Auth: login page → store JWT → protected routes
- Docker: full-stack docker-compose up (verify all 5 services start and communicate)
- Pattern mining job: implement IPatternMiningJob concrete class

---

## [2026-03-25] — session:v51-phase4-frontend

**Phase:** Phase 4 — Command Center UI (Bagian A selesai)

### Done

**Frontend (project/frontend/src/):**
- `pages/Login.tsx` — POST /api/auth/login → JWT stored via authStore → navigate ke /
- `store/authStore.ts` — Zustand persist: token, setToken, logout
- `App.tsx` — ProtectedRoute + /login + /theories/:id → TheoryDetail + fallback *→/
- `components/layout/AppLayout.tsx` — sidebar nav + logout button + Phase 4 footer
- `pages/TheoryDetail.tsx` — detail theory + factors table + Evaluate Now panel
  Fixed: onSuccess → useEffect (TanStack Query v5), added <TheoryDetail> generic,
  TheoryFactor type annotation
- `lib/api.ts` — tambah: login(), evaluateTheory(), getTheoryDetail()
  tambah types: LoginResponse, EvaluateResult
- `pages/Live.tsx` — SignalCard + ProbabilityGauge + SignalR real-time + RecordOutcome
- `pages/Theories.tsx` — list wired ke api.listTheories + link ke TheoryDetail
- `pages/TheoryBuilder.tsx` — create theory form + redirect
- `pages/Patterns.tsx` — grid + create form
- `pages/Backtest.tsx` — form + run + sessions list
- `pages/TradeLog.tsx` — paginated + recap + outcome recording
- `pages/HMMModels.tsx` — list + train form
- Build: 0 errors, 0 warnings ✅ (tsc -b && vite build)

**Backend (tidak ada perubahan baru — semua Phase 2+3 tetap valid):**
- POST /api/signals/evaluate sudah ada di SignalController.cs
- AuthController: password default "123456" (SHA256 hardcoded)

### Blockers
- Bagian B butuh semua 3 services berjalan:
  dotnet run + uvicorn + npm run dev

### Next (Phase 4 — Bagian B)
- Jalankan 3 services lokal, login ke http://localhost:5173
- Ambil data historis XAUUSD H1 via MT5
- Train HMM model, inject pattern + theory, run backtest
- Validasi manual ≥ 4/5 signal sebelum Phase 5

---

*Append new session logs below.*

---

## [2026-03-25] — session:v51-mt5-live-execution

**Phase:** Phase 4 Bagian B + MT5 Terminal
**Task:** Koneksi MT5 Exness + live order execution dari UI

### Done

**Infrastructure — Startup & Process Management:**
- `project/python-sidecar/start.bat` — diupdate: kill port 8001 dulu, clear __pycache__,
  jalankan uvicorn TANPA `--reload` (fix Windows Store AppContainer spawn bug)
- `project/run_all.bat` — dibuat baru: master launcher 1 klik untuk semua 3 service.
  Kill ports 8001/5206/3000 → clear cache → start Python (no --reload) → C# API → React
- Root cause ghost process: Windows Store Python AppContainer PID virtualization.
  Fix: `powershell.exe -Command "Get-Process python* | Stop-Process -Force"`

**Python Sidecar:**
- `routers/mt5.py` — BARU. 7 endpoint MT5:
  - POST /python/mt5/connect — login MT5 dengan credentials
  - GET  /python/mt5/account — account info (balance, equity, margin, profit)
  - POST /python/mt5/ohlc — ambil OHLC bars per symbol + timeframe
  - POST /python/mt5/order — send market order BUY/SELL dengan SL/TP dalam pips
  - POST /python/mt5/close — close/partial close posisi by ticket
  - GET  /python/mt5/positions — daftar semua open positions
  - DELETE /python/mt5/disconnect — shutdown MT5
  Fix: symbol TIDAK di-.upper() (Exness pakai suffix m: XAUUSDm, EURUSDm)
  Fix: OrderRequest menggunakan Pydantic aliases (slPips, tpPips) untuk kompatibilitas C#
- `main.py` — tambah import mt5 router + include_router /python/mt5

**C# Backend:**
- `Modules/MT5/Models/MT5Models.cs` — BARU. 11 record types:
  MT5ConnectRequest, MT5AccountInfo, MT5OhlcRequest, MT5OhlcBar, MT5OhlcResponse,
  MT5OrderRequest, MT5OrderResult, MT5CloseRequest, MT5CloseResult, MT5PositionInfo
- `Modules/MT5/Services/MT5Service.cs` — BARU. Calls Python /python/mt5/* via IPythonClient
- `Modules/MT5/Controllers/MT5Controller.cs` — BARU. 7 REST endpoint /api/mt5/*
- `Infrastructure/Python/PythonClient.cs` — FIX KRITIS: line 17
  `JsonSerializer.Serialize(payload)` → `JsonSerializer.Serialize(payload, JsonOpts)`
  JsonOpts punya `SnakeCaseLower` policy → fix 422 error (SlPips → sl_pips)

**Frontend:**
- `pages/MT5Terminal.tsx` — BARU. Trading terminal lengkap:
  - Account panel: auto-detect MT5 connected on mount, auto-refresh 3s
  - Positions table: ticket, symbol, type, volume, open price, SL/TP, profit, tombol Close
  - New Order panel: symbol dropdown (XAUUSDm dll), BUY/SELL, volume, SL/TP pips
  - Default symbol: XAUUSDm (Exness m-suffix)
  Fix: query `enabled: connected` dihapus → runs on mount
- `lib/api.ts` — tambah 6 MT5 methods + 9 interface types
- `App.tsx` — tambah route `/mt5` → MT5Terminal
- `components/layout/AppLayout.tsx` — tambah "MT5 Terminal" nav item

**MT5 Connected:**
- Akun: 413564586 | Server: Exness-MT5Trial6
- Balance: $9,973.33 | Trade allowed: true
- Order BUY/SELL dari UI berhasil masuk MT5 ✅
- Exness symbol naming: suffix `m` (XAUUSDm bukan XAUUSD)

### Bugs Found & Fixed
1. **Ghost AppContainer uvicorn** — PID dalam netstat tidak bisa di-kill via taskkill biasa.
   Fix: kill ALL python processes via powershell.
2. **uvicorn --reload** — spawn subprocess gagal load file di AppContainer virtual FS.
   Fix: hapus --reload flag.
3. **Symbol not found XAUUSD** — Exness pakai m-suffix (XAUUSDm).
4. **symbol.upper()** — `XAUUSDm.upper()` → `XAUUSDM` (wrong). Hapus semua .upper() pada symbol.
5. **422 Unprocessable Entity (pertama)** — Python model pakai sl_pips tapi C# kirim slPips.
   Fix: Pydantic aliases + ConfigDict(populate_by_name=True).
6. **422 Unprocessable Entity (kedua)** — PythonClient.Serialize tanpa JsonOpts → PascalCase.
   Fix: JsonSerializer.Serialize(payload, JsonOpts).
7. **Agent blocked (retcode 10027)** — MT5 AutoTrading button (Trading Algo) harus hijau.

### Blockers
- None

### Next (Phase 5 — Live Engine)
- Implementasi live candle loop (services/live_feed.py)
- Auto-signal dari HMM pipeline → auto-order execution via MT5
- Circuit breaker + daily risk limit
- Train HMM XAUUSD H1, inject theory BnR, validasi ≥ 4/5 signal manual

---

## [2026-03-29] — session:v51-ui-enhancements-alert-log

**Phase:** Phase 4 Post-MT5 — UI Enhancements + HMM Live Alert Log
**Task:** URUTAN [5] — Delete/Sort, Instrument Toggle, HMM Alert Log System

### Done

**Bug Fixes:**
- `Backtest.tsx` — Fixed `EquitySpark` crash (`curve.map is not a function`).
  Root cause: C# `JsonSerializer.Serialize(list<float>)` → stored as JSON string in DB.
  Frontend runtime parse: `JSON.parse(rawCurve)` + `!Array.isArray(curve)` guard.

**UX — Delete & Sort:**
- `Theories.tsx` — Sort (Terbaru/Terlama/A→Z/Z→A) + delete per theory row with confirm.
  Changed `<Link>` wrapper to flex div with inner Link + delete button.
- `Patterns.tsx` — Sort + delete per row + TypeBadge component (HMM vs other) +
  type filter toggle (Semua / HMM) + "no sequence" italic placeholder. colSpan updated 7→8.
- `Backtest.tsx` — Sort state + `sortedSessions` useMemo + `deleteMut` + `handleDelete`.
  Delete button per row (stopPropagation prevents expand). Session count shown.
- `tokens.css` — `.btn-icon-danger` class: transparent bg, `var(--sell)` on hover, disabled opacity.
- `BacktestService.cs` + `IBacktestService.cs` — `DeleteAsync`: cascades BacktestTrades →
  BacktestResults → BacktestSession. Returns bool.
- `BacktestController.cs` — `[HttpDelete("sessions/{id:guid}")]` endpoint added.
- `PatternService.cs` — Bugfix: `.Where(p => p.DeletedAt == null)` added to `ListAsync`.

**Instrument Field Toggle:**
- `HMMModels.tsx` — freetext `<input>` when `trainDataSource === 'mt5'`, dropdown when DB.
- `Backtest.tsx` — same pattern with `dataSource` state.

**HMM Live Alert Log — Python:**
- `routers/analysis.py` (NEW) — Multi-TF HMM analysis router.
  `_Raw` dataclass: tf, tag, msg, severity, confidence, group_key, action.
  5 alert types per TF: STATE, S/R, LIQ, VOL, MOM.
  Cross-TF divergence: LTF (M1/M5/M15) vs HTF (H1/H4) momentum z-score.
  `_merge(group)`: sorts TFs M1→H4, max conf + `(n-1)/5×0.20` agreement bonus.
  Action logic: STATE_BULL→BUY, STATE_BEAR→SELL, SR resistance→SELL, support→BUY,
    LIQ/VOL→NEUTRAL, MOM extreme ob→SELL, os→BUY, MOM strong bull→BUY, bear→SELL,
    DIV_BULL→SELL, DIV_BEAR→BUY.
- `main.py` — `app.include_router(analysis_router.router, prefix="/python/analysis")`.

**HMM Live Alert Log — C#:**
- `Modules/Analysis/Controllers/AnalysisController.cs` (NEW) — 1 endpoint:
  `POST /api/analysis/multi-tf` → proxy to Python `/python/analysis/multi-tf`.
  `MultiTfRequest` record: `Instrument`, `Timeframes`.

**HMM Live Alert Log — Frontend:**
- `api.ts` — `deletePattern`, `deleteBacktestSession`, `getMultiTfAnalysis`,
  `AlertItem` interface with `tf, tag, severity, msg, confidence, action`.
- `useHmmAlertLog.ts` (NEW) — `AlertLog` interface + `getTFsForNow()` smart TF selection.
  30s `setInterval` polling, `latestRef` for stale closure safety.
  localStorage `hmm_alert_log_v1`, max 500 FIFO. `addSystemLog` + `clearLogs`.
- `HmmAlertLog.tsx` (NEW) — `TfBadges`, `ConfBadge`, `ActionBadge` sub-components.
  `LogEntry`: row1 ts · TfBadges · tag badge · ConfBadge · ActionBadge (right-align)
              row2 message text.
  Collapsible panel: 36px tab with vertical "HMM LOG" text + live dot when collapsed.
  Confidence legend + status bar.
- `Live.tsx` — 3-col grid `3fr|4fr|3fr` (log open) / `3fr|4fr|36px` (collapsed).
  `isLogOpen` + `logInstrument` state. `anyRunning` from 3 status queries (React Query dedup).

### Blockers
- None

### Next (Phase 5 — Live Engine)
- Implementasi live candle loop (services/live_feed.py)
- Auto-signal dari HMM pipeline → auto-order execution via MT5
- Circuit breaker + daily risk limit
- Direktur: validasi manual ≥ 4/5 signal (user.md URUTAN [4] item 16) sebelum auto-order

---

## [2026-03-25] — session:v51-debug-api-connectivity

**Phase:** Phase 4 Bagian B — API Debug & Fix

### Done

**Services verified running:**
- Python sidecar: http://localhost:8001 ✅
- C# API: http://localhost:5206 ✅
- React frontend: http://localhost:3000 ✅

**Bug fixes:**
- `vite.config.ts` — Vite proxy diperbaiki: port 5000 → 5206 (sesuai C# API aktual)
- `routers/ccode.py` — tambah `POST /python/ccode/evaluate` (calls sp_evaluate_theory via asyncpg)
- `routers/pattern.py` — tambah `POST /python/pattern/match` (Markov score + exact match fallback)
- `frontend/src/lib/api.ts` — tambah `removeFactor`, update `TheoryFactor` type (+ timeframe field)
- `frontend/src/pages/TheoryDetail.tsx` — tambah Add Factor form + delete button per row
- `frontend/src/pages/Patterns.tsx` — tambah Create Pattern form dengan state sequence pill selector

**API endpoint status (all tested):**
- Auth: POST /api/auth/login ✅
- Patterns: GET/POST /api/patterns ✅ (stateSequence harus string JSON, bukan array)
- Theories: GET/POST /api/theories + GET /api/theories/{id} + POST factors ✅
- HMM: GET /api/hmm/models + POST /api/hmm/train ✅
- Signals: GET /api/signals/live + /api/signals/history ✅
- TradeLog: GET /api/trades + /api/trades/recap ✅
- Backtest: GET /api/backtest/sessions + POST /api/backtest/run ✅
- Bayesian: GET /api/bayes/probability + /api/bayes/counters ✅
- Python: /python/features/extract ✅, /python/ccode/calculate ✅

**Known blocker:**
- Yahoo Finance 429 rate limit (temporary) — yfinance data fetch gagal sementara
- HMM train/classify tidak bisa berjalan sampai rate limit selesai (~1-2 jam)
- Python sidecar perlu di-restart untuk load 2 endpoint baru (/ccode/evaluate, /pattern/match)

### Blockers
- Python sidecar harus di-restart: `Ctrl+C` lalu `start.bat` ulang dari python-sidecar dir

### Next
- Restart Python sidecar
- Train HMM XAUUSD H1 via UI (setelah Yahoo Finance rate limit selesai)
- Inject pattern BnR_BULL_S0S3S4 via Pattern Manager UI
- Inject Theory Break & Retest Bullish via Theory Builder UI + 8 factors
- Run backtest via UI, validasi WR > 50%
