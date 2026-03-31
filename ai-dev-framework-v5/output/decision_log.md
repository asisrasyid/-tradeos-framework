# DECISION LOG — TradeOS v5.1
## Append Only

---

## DEC-001: HMM state sequence as pattern (not cosine similarity)
**Date:** 2026-03-24
**Decision:** Pattern = HMM state sequence. Matching via Markov transition probability.
**Rejected:** Cosine similarity on raw OHLC matrices
**Rationale:** Scale-invariant (same pattern regardless of price level),
noise-tolerant (states from statistical distributions), time-invariant
(20 candle and 200 candle produce same sequence if conditions match).
**Status:** Final

---

## DEC-002: Bayesian counter with Laplace smoothing (not static weights)
**Date:** 2026-03-24
**Decision:** P(WIN) = (wins+1)/(total+2), updated after every outcome
**Rejected:** Static decision point weights, manual tuning only
**Rationale:** Self-learning without LLM. Laplace prevents P=0 or P=1 on small
samples. System improves automatically from trade history.
**Status:** Final

---

## DEC-003: SIGNAL / WATCH / SKIP (not binary BUY/SKIP)
**Date:** 2026-03-24
**Decision:** Three decision outputs: SIGNAL (act), WATCH (monitor), SKIP (pass)
**Rationale:** WATCH handles cases where setup is valid but P(WIN) not yet
sufficient (low sample count), or P(WIN) is high but current setup score is
below threshold. More nuanced than binary.
**Status:** Final

---

## DEC-004: BIC for HMM K selection (not hardcoded K)
**Date:** 2026-03-24
**Decision:** Try K=4..8, select K with lowest BIC per instrument/TF
**Rejected:** Hardcoded K=6 for all instruments
**Rationale:** Different instruments have different market regime complexity.
XAUUSD may have 6 meaningful states, EURUSD may have 4. BIC finds the natural
number of states in the data.
**Status:** Final

---

## DEC-005: HMM models stored as BYTEA in PostgreSQL
**Date:** 2026-03-24
**Decision:** Serialize model + scaler as pickle → store in hmm_models.model_pickle
**Rejected:** File system storage, external model registry
**Rationale:** Single source of truth, versioned alongside metadata, no file
management complexity. BYTEA can store up to 1GB; models are ~200KB.
**Status:** Final

---

## DEC-006: C# orchestrates / Python computes (unchanged from v5.0)
**Date:** 2026-03-24
**Status:** Final (carried from v5.0)

---

## DEC-007: trade_log extended with state_sequence + p_win_at_signal
**Date:** 2026-03-24
**Decision:** Every signal records full state_sequence JSONB and p_win at time of signal
**Rationale:** Post-mortem analysis requires knowing exactly what the system
"saw" when it made the decision. p_win_at_signal captures the probability
at decision time, even as it changes with future trades.
**Status:** Final

---

## DEC-008: HMM Alert Log stored in localStorage (not database)
**Date:** 2026-03-29
**Decision:** Alert log persisted to `localStorage` key `hmm_alert_log_v1`, max 500 entries FIFO.
**Rejected:** Database persistence (separate alerts table)
**Rationale:** Alert log is an observation tool, not a trading record. It resets per device/browser,
which is acceptable. No backend schema change needed. Max 500 entries caps storage at ~100KB.
**Status:** Final

---

## DEC-009: Smart TF polling (clock-minute aware, not all TFs every tick)
**Date:** 2026-03-29
**Decision:** `getTFsForNow(now)` selects TFs based on current minute:
  M1+M5 always; M15 at ×5 min; M30 at ×15 min; H1 at top-of-hour; H4 at ×4h.
**Rejected:** Fetch all 6 TFs every 30s
**Rationale:** Reduces Python sidecar load by 60–70% on average. Higher TFs don't change
frequently — fetching M30 every minute is wasteful. Clock-aligned polling matches natural
candle close rhythm.
**Status:** Final

---

## DEC-010: Alert group_key deduplication (not exact string match)
**Date:** 2026-03-29
**Decision:** Alerts from different TFs with same `group_key` are merged into one entry.
  TFs shown as comma-separated badges (e.g. "M1,M5,H1"). Confidence = max + agreement bonus.
**Rejected:** Show separate row per TF per alert type
**Rationale:** If M1, M5, and H1 all flag STATE_BULL simultaneously, one merged entry with
three TF badges communicates stronger conviction than three separate rows. Agreement bonus
(up to +20% at 6 TFs) rewards multi-timeframe confluence.
**Status:** Final

---

## DEC-011: Action field as contrarian for extreme momentum
**Date:** 2026-03-29
**Decision:** `MOM_OB` (extreme overbought z > 2.5) → action = SELL (contrarian).
  `MOM_OS` (extreme oversold z < -2.5) → action = BUY (contrarian).
  `MOM_BULL/BEAR` (moderate z > 1.8) → action follows momentum direction.
**Rationale:** Extreme momentum signals are mean-reversion setups ("potensi koreksi kuat"),
not continuation. Moderate momentum signals are trend-following. This mirrors standard SMC logic:
extreme extension = liquidity grab candidate.
**Status:** Final
