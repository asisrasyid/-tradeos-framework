# MEMORY — TradeOS v5.1
## Milestone Tracker | Append Only

---

## Milestone: Framework v5.1 Complete
**Date:** 2026-03-24 | **Phase:** Pre-development | **Status:** ✅ Complete

### What was built
- Full AI dev framework v5.1 for TradeOS
- idea_framework.md: complete spec with HMM + Bayesian architecture
  - 10-table PostgreSQL schema (added hmm_models, bayesian_counters)
  - Feature extraction spec (6 scale-invariant features with Python code)
  - HMM training protocol (BIC selection, K=4–8, GaussianHMM)
  - Viterbi state decoding spec
  - Pattern match via Markov transition probability
  - Bayesian P(WIN) with Laplace smoothing
  - 12-step intelligence pipeline (Raw OHLC → self-learning update)
  - Full C-Code catalogue (HMM state C-Codes added)
  - Extended API catalogue (HMM + Bayesian modules)
  - Theory example with full evaluation walkthrough
- tech_preference.md: stack finalized with hmmlearn mandatory
- guide_line.md: HMM-specific and Bayesian-specific rules added
- project/docs/CLAUDE.md: updated with HMM state colors, Bayesian formula
- project/docs/hmm_bayesian_spec.md: full Python pseudocode for all components
- output/ artifacts: database, feature_list, system_design, frontend_design,
  tech_stack, decision_log, improvement_log, templates

### Key decisions
- Pattern = HMM state sequence (not cosine similarity on candle shape)
- Probability = Bayesian counter with Laplace smoothing (not static weight)
- No LLM anywhere in the pipeline
- K states selected per instrument via BIC (not hardcoded)
- Transition matrix similarity replaces cosine similarity for pattern matching
- Added hmm_models table (stores serialized model pickles in BYTEA)
- Added bayesian_counters table (replaces manual weight tuning)
- trade_log extended with state_sequence JSONB + p_win_at_signal
- Both WATCH and SIGNAL decisions (not just binary BUY/SKIP)

### Tech debt
- None — framework phase only, no code written yet

---

## Milestone: Phase 1 — Foundation Complete
**Date:** 2026-03-24 | **Phase:** Foundation | **Status:** ✅ Complete

### What was built
- **PostgreSQL database `tradeos`** — live on localhost:5432
  - V1: All 10 tables (patterns, theories, theory_factors, trade_log, bayesian_counters,
    hmm_models, backtest_sessions, backtest_results, pattern_scores, theory_versions)
  - V2: 23 indexes (GIN on JSONB state_sequence, composite bayesian lookup, etc.)
  - V3: fn_set_updated_at trigger, sp_evaluate_theory(), fn_update_bayesian_counter()
  - V4: 27 C-Code seed patterns seeded (all market structure + session + momentum codes)
- **ASP.NET Core 8 API** (project/backend/TradeOS.Api)
  - 7 modules: Pattern, Theory, Backtest, Signal, TradeLog, HMM, Bayesian
  - ApiResponse<T> standard wrapper, JWT auth, Hangfire, SignalR hub
  - PythonClient (HttpClient wrapper → sidecar)
  - Builds: 0 errors, 0 warnings
- **Python FastAPI sidecar** (project/python-sidecar)
  - 6 routers: ohlc (MT5+yfinance), features (6 features), hmm (train+classify+sequence),
    ccode (SMC+pandas-ta), backtest (vectorbt simulation), pattern (mine-from-wins)
  - requirements.txt with all mandatory libraries
- **React 18 + Vite frontend** (project/frontend)
  - 7 pages: Live, Theories, TheoryBuilder, Patterns, Backtest, TradeLog, HMMModels
  - Design tokens (tokens.css) with HMM state colors, navy/emerald/red palette
  - TanStack Query v5, Zustand, SignalR client, React Router v6
  - Builds: 0 errors
- **Docker Compose** (project/docker-compose.yml)
  - 5 services: tradeos-db, tradeos-redis, tradeos-api, tradeos-python, tradeos-frontend
  - Health checks, volume persistence, internal network isolation for Python sidecar

### Key decisions
- PostgreSQL executed directly on local dev DB (password P@ss1234)
- C# service interfaces separate from implementations (testable)
- Bayesian counter update triggered synchronously after RecordOutcome (per guide_line rule)
- React build uses @tailwindcss/vite plugin (v4) instead of PostCSS
- Python sidecar NOT exposed via ports in docker-compose (internal only)

### Tech debt
- C# HMM training job (IHmmTrainingJob) and IPatternMiningJob are interfaces —
  concrete job classes to be implemented in Phase 2
- Python backtest uses simplified simulation — real vectorbt integration in Phase 3
- Auth module (JWT token issuance endpoint) not yet built — Phase 4 UI polish

---

## Milestone: Phase 2 — HMM Engine Complete
**Date:** 2026-03-24 | **Phase:** HMM Engine | **Status:** ✅ Complete

### What was built
- **Python services** (`project/python-sidecar/services/`)
  - `feature_extractor.py` — 6 scale-invariant features (ATR pct, momentum z-score,
    swing proximity, body dominance, HTF slope, liquidity proximity).
    15/15 unit tests passed. Scale-invariant proof: 10x price → identical f0, f3 values.
  - `hmm_trainer.py` — GaussianHMM BIC K=4..8 selection. `train_hmm()` returns
    `HmmTrainResult` with model_pickle, scaler_pickle, state_labels, version string.
  - `hmm_classifier.py` — In-memory `HmmClassifier` singleton. `classify_current_state()`,
    `get_state_sequence()` (Viterbi), `compute_pattern_match_score()` (Markov transition
    probability, NOT cosine similarity). Score = 0.7*exp(log_ratio/n) + 0.3*exact_match.
  - `ccode_calculator.py` — All 27 C-Codes: BOS/CHoCH/OB/FVG/Liquidity/Sessions
    via smartmoneyconcepts, ADX/EMA200/RSI/ATR/Volume via pandas-ta, HMM state codes
    injected from classifier output.
- **Routers updated** to delegate to services:
  - `routers/features.py` → delegates to `services/feature_extractor.py`
  - `routers/hmm.py` → uses `services/hmm_trainer.py` + `services/hmm_classifier.py`
    Loads model from asyncpg DB if not in cache; populates cache immediately after train.
- **C# backend** (`project/backend/TradeOS.Api/`)
  - `Infrastructure/Jobs/HmmTrainingJob.cs` — Hangfire job implementing IHmmTrainingJob.
    Calls `/python/hmm/train` → decodes base64 pickles → deactivates old models →
    persists new `HmmModelEntity` with BYTEA columns.
  - `Modules/Signal/Services/SignalService.cs` — Full 9-step `EvaluateTheoryAsync`:
    OHLC fetch → features → HMM classify+sequence → H4 HMM (optional) → C-codes →
    pattern match → sp_evaluate_theory fallback → Bayesian P(WIN) → insert trade_log →
    SignalR push to `instrument:{X}` group.
  - `Modules/Auth/Controllers/AuthController.cs` — `POST /api/auth/login` → JWT HS256.
    Credentials: username+SHA256(password) stored in `appsettings.json Auth:*`.
    Default: admin / admin (SHA256: `8c6976e5b5410415...`).
  - `ISignalService` updated with `EvaluateTheoryAsync` + `EvaluateResult` record.
  - `appsettings.json` updated: `Auth:Username`, `Auth:PasswordHash`, `Jwt:ExpiryHours`.
  - `Program.cs` updated: `IHmmTrainingJob` → `HmmTrainingJob` registered as scoped.

### Key decisions
- HmmClassifier singleton shared across all FastAPI requests (thread-safe read-only cache)
- C# `EvaluateTheoryAsync` uses `file record` DTOs (file-scoped) to avoid naming conflicts
- Pattern match uses Viterbi sequence (NOT forward algorithm) per guide_line.md rule
- AuthController validates password via SHA256 hash comparison — no plain text stored
- HmmTrainingJob uses `ExecuteUpdateAsync` with `IgnoreQueryFilters()` to deactivate old
  active models even though HmmModelEntity has a query filter on `IsActive`

### Tech debt
- `EvaluateTheoryAsync` calls `/python/ccode/evaluate` which proxies sp_evaluate_theory —
  actual stored proc call in Python not yet implemented (uses C# fallback local scorer)
- MT5 live feed not yet connected — OHLC fetch falls back to yfinance in dev
- Pattern mining job (IPatternMiningJob) interface exists but no concrete implementation

---

## Milestone: Phase 3 — Theory + Bayesian + Backtest Engine Complete
**Date:** 2026-03-24 | **Phase:** Bayesian Engine | **Status:** ✅ Complete

### What was built / fixed

**C# — Enhanced services:**
- `TradeLogService.cs`: Added `theoryId` filter to `ListAsync`. `RecordOutcomeAsync` now
  wrapped in `db.Database.BeginTransactionAsync()`. After outcome: (1) Bayesian counter update,
  (2) pattern_scores bulk update (TotalAppearances++, ConfirmedWins/Losses++, WinRate recomputed).
  Full rollback on any exception. This is the self-learning trigger point.
- `TheoryService.RollbackAsync`: Now saves current state as a new `TheoryVersionEntity`
  before restoring the target snapshot (prevents accidental loss of current version).
- `SignalService.GetLiveSignalsAsync`: Expiry sweep — loads non-expired open signals, filters
  by timeframe window (M1=5min, M5=25min, M15=1h, H1=5h, H4=20h, D1=5days), marks expired
  via `ExecuteUpdateAsync`, then returns filtered live signals.
- `Infrastructure/Jobs/BacktestJob.cs`: Hangfire `IBacktestJob` implementation.
  Fetches theory config → calls `/python/backtest/run` → stores `BacktestResultEntity` →
  marks session status completed/failed.
- `Program.cs`: `IBacktestJob → BacktestJob` registered as scoped.

**Python — New service:**
- `services/backtest_runner.py`: Full candle-by-candle replay loop.
  Per bar: extract_features → HMM classify (if model loaded) → calculate_all_ccodes →
  theory factor scoring → TP/SL simulation (ATR×2/ATR×1) → equity curve.
  Metrics: win_rate, profit_factor, Sharpe, Sortino, max_drawdown, state_distribution,
  best/worst seq_repr by win rate (min 3 occurrences).
- `routers/backtest.py`: Refactored to delegate fully to `services/backtest_runner.py`.

**Database:**
- `V5__sp_save_theory_version.sql` — executed on live DB:
  - `sp_save_theory_version(theory_id, snapshot, change_notes, win_rate)` → auto-increments
    version_number per theory, inserts into theory_versions. Returns new version number.
  - `fn_expire_signals()` → bulk UPDATE trade_log setting signal_expired=TRUE based on
    timeframe-specific windows.

### Key decisions
- RecordOutcomeAsync self-learning is atomic — any step failing rolls back everything
- TheoryService rollback always preserves current state (no version data loss)
- backtest_runner uses real feature/HMM/C-code stack (not mocked) — if HMM not loaded,
  falls back to C-codes only (graceful degradation)
- BacktestJob sets session status=running before starting, failed on exception

### Tech debt
- backtest_runner equity curve uses pip × 0.01% approximation (not real pip value per instrument)
- Pattern mining job (IPatternMiningJob) still a stub — implement in Phase 4
- Frontend pages not yet wired to real API endpoints

---

---

## Milestone: MT5 Live Execution — Connected & Working
**Date:** 2026-03-25 | **Phase:** Phase 4 Bagian B | **Status:** ✅ Complete

### What was built
- **run_all.bat** — master launcher 1 klik: kills all ports, starts Python+C#+React
- **python-sidecar/routers/mt5.py** — 7 MT5 endpoints: connect, account, ohlc, order, close, positions, disconnect
- **main.py** updated — MT5 router included under /python/mt5
- **MT5Models.cs, MT5Service.cs, MT5Controller.cs** — full MT5 module di C# backend
- **MT5Terminal.tsx** — full trading terminal di frontend (account panel + positions table + new order)
- **api.ts** — 6 MT5 methods + 9 types
- **App.tsx + AppLayout.tsx** — /mt5 route + nav item

### Key decisions
- MetaTrader5 Python package v5.0.5640 via `lib_local/` directory (Windows-only DLL)
- Symbol naming: Exness pakai suffix `m` (XAUUSDm, EURUSDm, GBPUSDm) — JANGAN uppercase
- Python sidecar runs WITHOUT --reload (Windows Store AppContainer spawn bug)
- OrderRequest: Pydantic aliases (slPips, tpPips) + `populate_by_name=True` agar C# camelCase diterima
- PythonClient.cs: serialize dengan JsonOpts (SnakeCaseLower) agar Python Pydantic bisa parse

### Verified working
- MT5 akun 413564586 (Exness-MT5Trial6) connected via UI
- BUY order XAUUSDm 0.01 lot → retcode 10009 (done) ✅
- SELL order XAUUSDm 0.01 lot → masuk MT5 ✅
- Positions muncul di MT5Terminal table ✅
- Close position dari UI → berhasil ✅

### Tech debt
- MT5Terminal belum auto-close semua posisi (tombol "Close All")
- Tidak ada SL/TP visual editor di chart
- Live candle feed belum terhubung ke MT5Terminal

---

## Milestone: UI Enhancements + HMM Live Alert Log System
**Date:** 2026-03-29 | **Phase:** Phase 4 Post-MT5 | **Status:** ✅ Complete

### What was built

**Bug Fixes:**
- `Backtest.tsx` — `EquitySpark` crash fix: `equityCurve` dari C# tersimpan sebagai JSON string
  (hasil `JsonSerializer.Serialize(list)`). Frontend sekarang runtime-parse via `JSON.parse(rawCurve)`.
  Guard `!Array.isArray(curve)` ditambahkan ke komponen.

**UX Improvements — Delete & Sort:**
- `Theories.tsx` — Delete per theory (soft-delete via `api.deleteTheory`) + sort (Terbaru/Terlama/A→Z).
- `Patterns.tsx` — Delete per pattern + sort + TypeBadge (HMM badge biru vs abu) + toggle filter
  type (Semua / HMM) + placeholder "no sequence" jika `stateSeqRepr` null.
- `Backtest.tsx` — Delete per session + sort (Terbaru/Terlama/Tertinggi WR) + equityCurve fix.
- `tokens.css` — Class `.btn-icon-danger` (transparent, red on hover).
- `IBacktestService.cs` + `BacktestService.cs` — `DeleteAsync(sessionId)`: hapus trades + results + session.
- `BacktestController.cs` — `DELETE /api/backtest/sessions/{id}`.
- `PatternService.cs` — Bugfix `ListAsync`: tambah `.Where(p => p.DeletedAt == null)`.

**Instrument Field Toggle:**
- `HMMModels.tsx` + `Backtest.tsx` — freetext input jika `dataSource/trainDataSource === 'mt5'`,
  dropdown jika DB. Menghindari kebingungan symbol suffix (XAUUSDm vs XAUUSD).

**HMM Live Alert Log System (fitur baru):**
- `python-sidecar/routers/analysis.py` (baru) — Router multi-TF analysis:
  - `_Raw` dataclass: tf, tag, msg, severity, confidence, group_key, action
  - 5 analisa per TF: STATE (HMM state), S/R proximity, LIQ proximity, VOL (ATR), MOM (momentum z-score)
  - Cross-TF divergence check: LTF vs HTF momentum bias
  - Group by `group_key` → `_merge()`: TF badges majemuk, max confidence + agreement bonus (+4%/TF)
  - Action field: BUY/SELL/NEUTRAL per logika kondisi (contrarian pada extreme momentum)
  - Confidence helpers: `_conf_state`, `_conf_proximity`, `_conf_vol_high`, `_conf_mom`, `_conf_divergence`
- `python-sidecar/main.py` — register `/python/analysis`.
- `AnalysisController.cs` (baru di C#) — proxy `POST /api/analysis/multi-tf` → Python sidecar.
- `api.ts` — tambah `getMultiTfAnalysis()` + `AlertItem` interface (dengan field `action`).
- `useHmmAlertLog.ts` (hook baru) — 30s polling, smart TF selection by clock minute:
  - M1+M5 setiap tick; M15 di ×5 min; M30 di ×15 min; H1 di top-of-hour; H4 di ×4h
  - localStorage key `hmm_alert_log_v1`, max 500 entri FIFO
  - `latestRef` untuk avoid stale closure
- `HmmAlertLog.tsx` (komponen baru):
  - `TfBadges` — split `log.tf` by comma → beberapa badge TF
  - `ConfBadge` — % dengan warna (hijau ≥70%, amber 45-69%, merah <45%)
  - `ActionBadge` — `▲ BUY` hijau / `▼ SELL` merah / `● NEUTRAL` abu, right-aligned
  - Header: live dot pulse + instrument picker + Pause/Play/Clear/Collapse
  - Confidence legend + status bar (entries count + live/paused)
  - Collapsible ke tab 36px vertikal
- `Live.tsx` — layout 3-kolom: `3fr | 4fr | 3fr` (log open) / `3fr | 4fr | 36px` (collapsed)

### Key decisions
- Alert log tidak disimpan ke database — localStorage saja (max 500, FIFO). Cukup untuk UX observasi.
- Smart TF polling: tidak semua TF diambil setiap 30 detik — hemat resource, data lebih relevan.
- `_merge()` deduplication: grup berdasarkan `group_key`, bukan exact string match.
  Satu entri bisa mewakili M1+M5+M15 sekaligus.
- Action contrarian untuk extreme momentum: overbought → SELL (potensi koreksi kuat), bukan BUY.
- Instrument picker di log panel independen dari engine aktif — bisa monitor instrumen berbeda.

### Tech debt
- Alert log tidak ada notifikasi browser/suara (hanya visual).
- Analisa action BUY/SELL bersifat rule-based sederhana — belum terintegrasi dengan Bayesian P(WIN).

---

*Add new milestones here as phases complete.*
