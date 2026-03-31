# IMPROVEMENT LOG — TradeOS v5.1

## Applied
- v5.0 → v5.1: Replaced cosine similarity with HMM state sequence matching
- v5.0 → v5.1: Replaced static weights with Bayesian self-updating counters
- v5.0 → v5.1: Added hmm_models table (BYTEA storage)
- v5.0 → v5.1: Added bayesian_counters table
- v5.0 → v5.1: Extended trade_log with state_sequence + p_win_at_signal
- v5.0 → v5.1: Added HMM module + Bayesian module to API catalogue
- v5.0 → v5.1: Added WATCH decision (between SIGNAL and SKIP)
- v5.0 → v5.1: Added HMM C-Codes (HMM_STATE_CURRENT, HMM_STATE_IS_RETEST, etc)

## Backlog
| # | Improvement | Impact | Phase |
|---|-------------|--------|-------|
| B1 | Pattern mining from WIN trades (cluster centroids) | High | Post-Phase 3 |
| B2 | Walk-forward HMM retraining | High | Phase 5 |
| B3 | Multi-theory conflict resolver | Medium | Post-MVP |
| B4 | Regime change detection (transition matrix shift) | High | Post-MVP |
| B5 | Topological Data Analysis (persistence homology) | High | Future |
| B6 | MT5 EA auto-execution integration | High | Post-MVP |
