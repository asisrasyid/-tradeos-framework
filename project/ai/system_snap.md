# SYSTEM SNAPSHOT — TradeOS v5.1
## Current Build State

**Last Updated:** 2026-03-29
**Version:** v5.1 — HMM + Bayesian Edition
**Phase:** Phase 4 Complete — UI Enhancements + HMM Live Alert Log

---

## Services
| Service | Status | Notes |
|---------|--------|-------|
| PostgreSQL | ✅ Built + Running | Database `tradeos` created, all migrations executed |
| Redis | ⏳ Pending | Defined in Docker Compose, not yet started |
| ASP.NET Core API | ✅ Built + Running | 8 modules (termasuk MT5), builds 0 errors |
| Python FastAPI sidecar | ✅ Built + Running | 7 routers (termasuk mt5.py), port 8001 |
| React Frontend | ✅ Built + Running | 8 pages (termasuk MT5Terminal), builds 0 errors |
| Docker Compose | ✅ Written | 5 services, health checks, volume mounts |
| MetaTrader 5 | ✅ Connected | Akun 413564586 Exness-MT5Trial6, order execution verified |

## Database Tables
| Table | Status |
|-------|--------|
| patterns | ✅ Created + 27 C-Code rows seeded |
| theories | ✅ Created |
| theory_factors | ✅ Created |
| trade_log | ✅ Created |
| bayesian_counters | ✅ Created |
| hmm_models | ✅ Created |
| backtest_sessions | ✅ Created |
| backtest_results | ✅ Created |
| pattern_scores | ✅ Created |
| theory_versions | ✅ Created |

## Database Functions
| Object | Status |
|--------|--------|
| fn_set_updated_at() trigger | ✅ Created |
| trg_patterns_updated_at | ✅ Created |
| trg_theories_updated_at | ✅ Created |
| sp_evaluate_theory() | ✅ Created |
| fn_update_bayesian_counter() | ✅ Created |

## HMM Engine
| Component | Status |
|-----------|--------|
| Feature extractor (6 features) | ✅ Built (services/feature_extractor.py — 15 tests passed) |
| HMM trainer (BIC K=4..8) | ✅ Built (services/hmm_trainer.py) |
| State classifier (in-memory cache) | ✅ Built (services/hmm_classifier.py) |
| Sequence decoder (Viterbi) | ✅ Built |
| Pattern match scorer (Markov) | ✅ Built (compute_pattern_match_score) |
| C-Code calculator (27 codes) | ✅ Built (services/ccode_calculator.py) |
| Hangfire training job | ✅ Built (Infrastructure/Jobs/HmmTrainingJob.cs) |
| Signal eval pipeline (9 steps) | ✅ Built (SignalService.EvaluateTheoryAsync) |
| Auth endpoint (JWT login) | ✅ Built (Modules/Auth/Controllers/AuthController.cs) |

## Bayesian Engine
| Component | Status |
|-----------|--------|
| Counter CRUD | ✅ Built (BayesianService.cs) |
| P(WIN) calculator (Laplace) | ✅ Built |
| Decision gate | ✅ Built (sp_evaluate_theory) |
| Post-outcome updater | ✅ Built (fn_update_bayesian_counter) |

## API Endpoints
| Module | Endpoints | Status |
|--------|-----------|--------|
| PatternModule | 7 | ✅ Built |
| TheoryModule | 11 | ✅ Built |
| BacktestModule | 5 | ✅ Built + DELETE /sessions/{id} |
| SignalModule | 3+WS | ✅ Built |
| TradeLogModule | 5 | ✅ Built |
| HMMModule | 5 | ✅ Built |
| BayesianModule | 3 | ✅ Built |
| MT5Module | 7 | ✅ Built + Verified |
| AnalysisModule | 1 | ✅ Built — POST /api/analysis/multi-tf |

## Frontend Pages
| Page | Status |
|------|--------|
| Live (signal dashboard) | ✅ Built + 3-col layout + HMM Alert Log panel |
| Theories | ✅ Built + Delete + Sort |
| TheoryBuilder | ✅ Built |
| Patterns | ✅ Built + TypeBadge + type filter + delete + sort |
| Backtest | ✅ Built + Delete + Sort + equityCurve fix + freetext instrument |
| TradeLog | ✅ Built |
| HMMModels | ✅ Built + freetext instrument (MT5 mode) |
| MT5Terminal | ✅ Built + Verified (account, positions, order execution) |

## HMM Live Alert Log
| Component | Status |
|-----------|--------|
| `python-sidecar/routers/analysis.py` | ✅ Built — 5 analyses/TF + cross-TF divergence + merge |
| `AnalysisController.cs` (C# module baru) | ✅ Built — proxy POST /api/analysis/multi-tf |
| `useHmmAlertLog.ts` (hook baru) | ✅ Built — 30s polling + localStorage + smart TF |
| `HmmAlertLog.tsx` (komponen baru) | ✅ Built — TfBadges + ConfBadge + ActionBadge |
| Action field BUY/SELL/NEUTRAL | ✅ Built — semua layer: Python → C# → api.ts → hook → UI |

## File Structure
```
project/
├── database/migrations/     ← V1–V5 SQL files (executed on local DB)
├── backend/TradeOS.Api/     ← ASP.NET Core 8, builds OK
│   ├── Modules/MT5/         ← MT5 module (Models, Services, Controllers)
│   └── Modules/Analysis/    ← Analysis module (AnalysisController.cs) — BARU
├── python-sidecar/          ← FastAPI, 8 routers + requirements.txt
│   ├── routers/mt5.py       ← MT5 router (7 endpoints)
│   └── routers/analysis.py  ← Multi-TF HMM alert analysis — BARU
├── frontend/                ← React 18 + Vite + Tailwind, builds OK
│   ├── pages/MT5Terminal.tsx ← Trading terminal UI
│   ├── src/hooks/useHmmAlertLog.ts ← Alert log hook — BARU
│   └── src/components/HmmAlertLog.tsx ← Alert log UI — BARU
├── run_all.bat              ← Master launcher (kill+clear+start all 3)
├── docker-compose.yml       ← All 5 services
└── .env.example
```

## MT5 Integration
| Component | Status | Notes |
|-----------|--------|-------|
| Python mt5.py router | ✅ Working | 7 endpoints, Exness m-suffix aware |
| C# MT5 module | ✅ Working | 3 files: Models/Service/Controller |
| PythonClient.cs serializer fix | ✅ Fixed | JsonOpts (SnakeCaseLower) pada Serialize |
| MT5Terminal.tsx | ✅ Working | Account, positions, BUY/SELL, Close |
| Exness connection | ✅ Verified | Akun 413564586, balance $9,973 |
| Order execution | ✅ Verified | BUY/SELL XAUUSDm 0.01 lot berhasil |

---

## Self-Learning Loop
| Component | Status |
|-----------|--------|
| RecordOutcomeAsync → BayesianService.UpdateCounterAsync | ✅ Wired (transactional) |
| RecordOutcomeAsync → PatternScores update | ✅ Wired |
| TheoryService.UpdateAsync → auto-version snapshot | ✅ Wired |
| TheoryService.RollbackAsync → save-before-rollback | ✅ Fixed |
| backtest_runner.py → full replay loop | ✅ Built |
| BacktestJob.cs → Hangfire executor | ✅ Built |
| V5 migration (sp_save_theory_version, fn_expire_signals) | ✅ Executed |

## Startup — One Command
```
project/run_all.bat   ← jalankan ini untuk start semua service sekaligus
                         (Python :8001 + C# :5206 + React :3000)
```
Catatan: MT5 Terminal harus terbuka di Windows dan AutoTrading (Trading Algo) harus hijau.

---

## Known Issues / Tech Debt
- MT5Terminal belum ada tombol "Close All"
- Live candle feed belum terhubung ke MT5Terminal
- Validasi manual theory (item 16 user.md URUTAN [4]) masih outstanding — harus dilakukan Direktur

---

*Next: Phase 5 — Live Engine (auto candle loop + auto-order dari HMM signal)*
