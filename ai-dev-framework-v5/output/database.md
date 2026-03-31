# DATABASE DESIGN — TradeOS v5.1
## Output Artifact | DB Expert Lead

---

## 10 Tables Overview

```
patterns          — pattern library (state sequences + C-Code combos)
theories          — theory registry
theory_factors    — factors per theory (decision points)
trade_log         — all signals + outcomes (with state_sequence JSONB)
bayesian_counters — P(WIN) counters per (theory, state_seq, instrument, tf)
hmm_models        — trained HMM models (serialized pickle in BYTEA)
backtest_sessions — backtest job registry
backtest_results  — backtest outcome store
pattern_scores    — living win-rate per pattern per instrument
theory_versions   — version history + rollback snapshots
```

## Key JSONB Schemas

### trade_log.state_sequence
```json
{
  "seq": [0, 0, 3, 2, 4],
  "repr": "S0S0S3S2S4",
  "hash": "a3f8b2c1d4e5f6a7",
  "log_prob": -8.542,
  "length": 5,
  "hmm_version": "XAUUSD_H1_v1_20260324"
}
```

### trade_log.factor_snapshot
```json
{
  "HMM_STATE_SEQ_MATCH":   {"met": true,  "score": 0.87, "dp": 5, "contribution": 4.35},
  "HTF_BIAS_BULLISH":      {"met": true,  "score": 1.0,  "dp": 3, "contribution": 3.0},
  "EQL_SWEPT":             {"met": true,  "score": 1.0,  "dp": 2, "contribution": 2.0},
  "PRICE_IN_OB_BULL":      {"met": true,  "score": 0.88, "dp": 2, "contribution": 1.76},
  "HMM_STATE_IS_RETEST":   {"met": true,  "score": 1.0,  "dp": 2, "contribution": 2.0},
  "HMM_STATE_IS_RANGING":  {"met": false, "score": 0.0,  "dp": -4,"contribution": 0.0},
  "CANDLE_MOMENTUM_BULL":  {"met": true,  "score": 0.91, "dp": 1, "contribution": 0.91},
  "SESSION_LONDON_OPEN_KZ":{"met": true,  "score": 1.0,  "dp": 1, "contribution": 1.0}
}
```

### hmm_models.state_labels
```json
{
  "0": "S0_TRENDING_BULL",
  "1": "S1_TRENDING_BEAR",
  "2": "S2_RANGING",
  "3": "S3_POST_BOS",
  "4": "S4_RETEST_ZONE",
  "5": "S5_HIGH_VOLATILITY"
}
```

### backtest_results.state_distribution
```json
{
  "signal_state_dist": {"S0": 0.35, "S1": 0.08, "S2": 0.12, "S3": 0.20, "S4": 0.22, "S5": 0.03},
  "win_by_state":      {"S0": 0.68, "S3": 0.71, "S4": 0.74},
  "best_sequence":     "S0S0S3S2S4",
  "worst_sequence":    "S2S2S2S5S1"
}
```

## Critical Stored Procedure

```sql
CREATE OR REPLACE FUNCTION sp_evaluate_theory(
    p_theory_id      UUID,
    p_ccode_scores   JSONB,   -- {"HTF_BIAS_BULLISH": 1.0, "BOS_BULLISH": 0.88, ...}
    p_seq_match_score DECIMAL  -- pattern match score 0.0-1.0 from Python
) RETURNS TABLE(
    signal_valid     BOOLEAN,
    composite_score  DECIMAL,
    confidence_pct   DECIMAL,
    factor_breakdown JSONB
) AS $$
DECLARE
    v_threshold      INTEGER;
    v_total          DECIMAL := 0;
    v_max_positive   DECIMAL := 0;
    v_breakdown      JSONB   := '{}';
    v_factor         RECORD;
    v_score          DECIMAL;
    v_contribution   DECIMAL;
BEGIN
    SELECT threshold INTO v_threshold FROM theories WHERE id = p_theory_id;

    FOR v_factor IN
        SELECT factor_code, decision_point, factor_type, threshold_value
        FROM theory_factors WHERE theory_id = p_theory_id
        ORDER BY sort_order
    LOOP
        -- State sequence match uses Python-computed score
        IF v_factor.factor_type = 'state_sequence_match' THEN
            v_score := p_seq_match_score;
        ELSE
            v_score := COALESCE((p_ccode_scores ->> v_factor.factor_code)::DECIMAL, 0);
        END IF;

        v_contribution := v_factor.decision_point * v_score;
        v_total        := v_total + v_contribution;
        IF v_factor.decision_point > 0 THEN
            v_max_positive := v_max_positive + v_factor.decision_point;
        END IF;

        v_breakdown := v_breakdown || jsonb_build_object(
            v_factor.factor_code, jsonb_build_object(
                'score',        ROUND(v_score::numeric, 4),
                'dp',           v_factor.decision_point,
                'contribution', ROUND(v_contribution::numeric, 3)
            )
        );
    END LOOP;

    RETURN QUERY SELECT
        v_total >= v_threshold,
        ROUND(v_total::numeric, 2),
        CASE WHEN v_max_positive > 0
             THEN ROUND((v_total / v_max_positive * 100)::numeric, 1)
             ELSE 0.0 END,
        v_breakdown;
END;
$$ LANGUAGE plpgsql;
```

## Index Strategy

```sql
-- Live signal evaluation (hot path)
CREATE INDEX idx_theories_active ON theories(instrument, is_active)
    WHERE deleted_at IS NULL AND is_active = TRUE;

CREATE INDEX idx_theory_factors_theory ON theory_factors(theory_id);

-- Bayesian lookup (hot path — called every signal)
CREATE INDEX idx_bayes_lookup ON bayesian_counters(theory_id, state_seq_hash, instrument, timeframe);

-- Trade analysis
CREATE INDEX idx_trade_log_time ON trade_log(instrument, signal_time DESC);
CREATE INDEX idx_trade_log_outcome ON trade_log(theory_id, outcome) WHERE outcome IS NOT NULL;
CREATE INDEX idx_trade_log_state ON trade_log USING GIN(state_sequence);

-- HMM model lookup
CREATE INDEX idx_hmm_active ON hmm_models(instrument, timeframe, is_active);
```
