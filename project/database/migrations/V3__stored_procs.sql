-- =============================================================================
-- V3__stored_procs.sql
-- TradeOS v5.1 — Triggers + Stored Procedures
-- Idempotent: CREATE OR REPLACE
-- =============================================================================

-- -----------------------------------------------------------------------------
-- updated_at trigger function (reused by all tables)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach updated_at trigger to patterns
DROP TRIGGER IF EXISTS trg_patterns_updated_at ON patterns;
CREATE TRIGGER trg_patterns_updated_at
    BEFORE UPDATE ON patterns
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- Attach updated_at trigger to theories
DROP TRIGGER IF EXISTS trg_theories_updated_at ON theories;
CREATE TRIGGER trg_theories_updated_at
    BEFORE UPDATE ON theories
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- -----------------------------------------------------------------------------
-- sp_evaluate_theory
-- Evaluates all factors for a given theory + live feature data
-- Returns: composite_score, p_win, confidence_tier, signal_decision
--
-- Parameters:
--   p_theory_id   : UUID of theory to evaluate
--   p_instrument  : e.g. 'XAUUSD'
--   p_timeframe   : e.g. 'H1'
--   p_state_seq   : JSON state sequence, e.g. '[0,0,3,2,4]'
--   p_c_codes     : JSON of evaluated C-Codes, e.g. {"BOS_BULLISH":1, "HTF_BIAS_BULLISH":1}
--   p_seq_repr    : human-readable sequence e.g. 'S0S0S3S2S4'
--   p_seq_hash    : SHA256 first 16 chars of seq_repr
--
-- Returns single row:
--   composite_score  INTEGER
--   threshold        INTEGER
--   threshold_met    BOOLEAN
--   p_win            DECIMAL
--   bayes_total      INTEGER
--   confidence_tier  VARCHAR
--   signal_decision  VARCHAR  -- 'SIGNAL' | 'WATCH' | 'SKIP'
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_evaluate_theory(
    p_theory_id   UUID,
    p_instrument  VARCHAR(20),
    p_timeframe   VARCHAR(10),
    p_state_seq   JSONB,
    p_c_codes     JSONB,
    p_seq_repr    VARCHAR(50),
    p_seq_hash    VARCHAR(16)
)
RETURNS TABLE (
    composite_score  INTEGER,
    threshold        INTEGER,
    threshold_met    BOOLEAN,
    p_win            DECIMAL(5,4),
    bayes_total      INTEGER,
    confidence_tier  VARCHAR(20),
    signal_decision  VARCHAR(10)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_theory        RECORD;
    v_factor        RECORD;
    v_score         DECIMAL := 0;
    v_c_code_val    DECIMAL;
    v_bayes         RECORD;
    v_p_win         DECIMAL(5,4) := 0.5000;
    v_bayes_total   INTEGER := 0;
    v_conf_tier     VARCHAR(20) := 'insufficient';
    v_decision      VARCHAR(10) := 'SKIP';
BEGIN
    -- Load theory
    SELECT t.threshold, t.min_confidence, t.direction
    INTO v_theory
    FROM theories t
    WHERE t.id = p_theory_id AND t.is_active = TRUE AND t.deleted_at IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Theory % not found or inactive', p_theory_id;
    END IF;

    -- Evaluate each factor
    FOR v_factor IN
        SELECT tf.*
        FROM theory_factors tf
        WHERE tf.theory_id = p_theory_id
        ORDER BY tf.sort_order ASC
    LOOP
        IF v_factor.factor_type = 'state_sequence_match' THEN
            -- Placeholder: C# / Python passes match_score via p_c_codes
            -- Key convention: 'HMM_STATE_SEQ_MATCH'
            v_c_code_val := COALESCE(
                (p_c_codes->>'HMM_STATE_SEQ_MATCH')::DECIMAL, 0
            );
            v_score := v_score + (v_factor.decision_point * v_c_code_val);

        ELSIF v_factor.factor_type IN ('c_code_condition', 'hmm_state_current') THEN
            v_c_code_val := COALESCE(
                (p_c_codes->>v_factor.factor_code)::DECIMAL, 0
            );

            -- Handle threshold operator if set
            IF v_factor.operator IS NOT NULL AND v_factor.threshold_value IS NOT NULL THEN
                CASE v_factor.operator
                    WHEN '>='  THEN v_c_code_val := CASE WHEN v_c_code_val >= v_factor.threshold_value THEN 1 ELSE 0 END;
                    WHEN '>'   THEN v_c_code_val := CASE WHEN v_c_code_val >  v_factor.threshold_value THEN 1 ELSE 0 END;
                    WHEN '<='  THEN v_c_code_val := CASE WHEN v_c_code_val <= v_factor.threshold_value THEN 1 ELSE 0 END;
                    WHEN '<'   THEN v_c_code_val := CASE WHEN v_c_code_val <  v_factor.threshold_value THEN 1 ELSE 0 END;
                    WHEN '='   THEN v_c_code_val := CASE WHEN v_c_code_val =  v_factor.threshold_value THEN 1 ELSE 0 END;
                    ELSE v_c_code_val := v_c_code_val;
                END CASE;
            END IF;

            v_score := v_score + (v_factor.decision_point * v_c_code_val);
        END IF;

        -- Required factor veto
        IF v_factor.is_required AND v_c_code_val = 0 THEN
            composite_score  := ROUND(v_score)::INTEGER;
            threshold        := v_theory.threshold;
            threshold_met    := FALSE;
            p_win            := v_p_win;
            bayes_total      := v_bayes_total;
            confidence_tier  := v_conf_tier;
            signal_decision  := 'SKIP';
            RETURN NEXT;
            RETURN;
        END IF;
    END LOOP;

    -- Bayesian probability lookup
    SELECT bc.wins, bc.losses, bc.total, bc.p_win_current, bc.confidence_tier
    INTO v_bayes
    FROM bayesian_counters bc
    WHERE bc.theory_id = p_theory_id
      AND bc.state_seq_hash = p_seq_hash
      AND bc.instrument     = p_instrument
      AND bc.timeframe      = p_timeframe
    LIMIT 1;

    IF FOUND THEN
        -- Laplace smoothing: P(WIN) = (wins + 1) / (total + 2)
        v_p_win       := (v_bayes.wins + 1.0) / (v_bayes.total + 2.0);
        v_bayes_total := v_bayes.total;
        v_conf_tier   := v_bayes.confidence_tier;
    ELSE
        -- No data: neutral prior
        v_p_win       := 0.5000;
        v_bayes_total := 0;
        v_conf_tier   := 'insufficient';
    END IF;

    -- Signal decision
    IF ROUND(v_score)::INTEGER >= v_theory.threshold
       AND v_p_win * 100 >= v_theory.min_confidence THEN
        v_decision := 'SIGNAL';
    ELSIF ROUND(v_score)::INTEGER >= (v_theory.threshold * 0.75)::INTEGER THEN
        v_decision := 'WATCH';
    ELSE
        v_decision := 'SKIP';
    END IF;

    composite_score  := ROUND(v_score)::INTEGER;
    threshold        := v_theory.threshold;
    threshold_met    := (ROUND(v_score)::INTEGER >= v_theory.threshold);
    p_win            := v_p_win;
    bayes_total      := v_bayes_total;
    confidence_tier  := v_conf_tier;
    signal_decision  := v_decision;

    RETURN NEXT;
END;
$$;

-- -----------------------------------------------------------------------------
-- fn_update_bayesian_counter
-- Call after recording a trade outcome.
-- Upserts the counter row and recomputes p_win + confidence_tier.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_bayesian_counter(
    p_theory_id   UUID,
    p_seq_hash    VARCHAR(16),
    p_seq_repr    VARCHAR(50),
    p_instrument  VARCHAR(20),
    p_timeframe   VARCHAR(10),
    p_outcome     VARCHAR(15)  -- 'WIN' | 'LOSS' | 'BREAK_EVEN'
)
RETURNS TABLE (
    p_win           DECIMAL(5,4),
    total_samples   INTEGER,
    wins            INTEGER,
    confidence_tier VARCHAR(20)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_wins   INTEGER := 0;
    v_losses INTEGER := 0;
    v_be     INTEGER := 0;
    v_total  INTEGER := 0;
    v_p_win  DECIMAL(5,4);
    v_tier   VARCHAR(20);
BEGIN
    -- Upsert counter
    INSERT INTO bayesian_counters
        (theory_id, state_seq_hash, state_seq_repr, instrument, timeframe,
         wins, losses, breakeven, total, last_updated)
    VALUES
        (p_theory_id, p_seq_hash, p_seq_repr, p_instrument, p_timeframe,
         CASE WHEN p_outcome = 'WIN'        THEN 1 ELSE 0 END,
         CASE WHEN p_outcome = 'LOSS'       THEN 1 ELSE 0 END,
         CASE WHEN p_outcome = 'BREAK_EVEN' THEN 1 ELSE 0 END,
         1, NOW())
    ON CONFLICT (theory_id, state_seq_hash, instrument, timeframe)
    DO UPDATE SET
        wins       = bayesian_counters.wins      + CASE WHEN p_outcome = 'WIN'        THEN 1 ELSE 0 END,
        losses     = bayesian_counters.losses    + CASE WHEN p_outcome = 'LOSS'       THEN 1 ELSE 0 END,
        breakeven  = bayesian_counters.breakeven + CASE WHEN p_outcome = 'BREAK_EVEN' THEN 1 ELSE 0 END,
        total      = bayesian_counters.total     + 1,
        last_updated = NOW()
    RETURNING bayesian_counters.wins,
              bayesian_counters.losses,
              bayesian_counters.breakeven,
              bayesian_counters.total
    INTO v_wins, v_losses, v_be, v_total;

    -- Laplace smoothed probability
    v_p_win := (v_wins + 1.0) / (v_total + 2.0);

    -- Confidence tier
    v_tier := CASE
        WHEN v_total >= 100 THEN 'strong'
        WHEN v_total >= 30  THEN 'reliable'
        WHEN v_total >= 10  THEN 'developing'
        ELSE 'insufficient'
    END;

    -- Persist computed values
    UPDATE bayesian_counters
    SET p_win_current   = v_p_win,
        confidence_tier = v_tier
    WHERE theory_id      = p_theory_id
      AND state_seq_hash = p_seq_hash
      AND instrument     = p_instrument
      AND timeframe      = p_timeframe;

    p_win           := v_p_win;
    total_samples   := v_total;
    wins            := v_wins;
    confidence_tier := v_tier;

    RETURN NEXT;
END;
$$;
