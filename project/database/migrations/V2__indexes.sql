-- =============================================================================
-- V2__indexes.sql
-- TradeOS v5.1 — All indexes
-- Idempotent: CREATE INDEX IF NOT EXISTS
-- =============================================================================

-- patterns
CREATE INDEX IF NOT EXISTS idx_patterns_code         ON patterns(code);
CREATE INDEX IF NOT EXISTS idx_patterns_type         ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_active        ON patterns(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_patterns_state_seq     ON patterns USING GIN(state_sequence);

-- theories
CREATE INDEX IF NOT EXISTS idx_theories_instrument   ON theories(instrument);
CREATE INDEX IF NOT EXISTS idx_theories_active        ON theories(is_active) WHERE is_active = TRUE;

-- theory_factors
CREATE INDEX IF NOT EXISTS idx_tf_theory_id          ON theory_factors(theory_id);
CREATE INDEX IF NOT EXISTS idx_tf_pattern_id         ON theory_factors(pattern_id);

-- hmm_models
CREATE INDEX IF NOT EXISTS idx_hmm_instrument_tf     ON hmm_models(instrument, timeframe);
CREATE INDEX IF NOT EXISTS idx_hmm_active             ON hmm_models(is_active) WHERE is_active = TRUE;

-- trade_log
CREATE INDEX IF NOT EXISTS idx_trade_log_theory       ON trade_log(theory_id);
CREATE INDEX IF NOT EXISTS idx_trade_log_instr_time   ON trade_log(instrument, signal_time DESC);
CREATE INDEX IF NOT EXISTS idx_trade_log_state_seq    ON trade_log USING GIN(state_sequence);
CREATE INDEX IF NOT EXISTS idx_trade_log_outcome      ON trade_log(outcome);
CREATE INDEX IF NOT EXISTS idx_trade_log_executed     ON trade_log(executed);

-- bayesian_counters
CREATE INDEX IF NOT EXISTS idx_bayes_lookup
    ON bayesian_counters(theory_id, state_seq_hash, instrument, timeframe);
CREATE INDEX IF NOT EXISTS idx_bayes_theory_id       ON bayesian_counters(theory_id);

-- backtest_sessions
CREATE INDEX IF NOT EXISTS idx_bt_session_theory     ON backtest_sessions(theory_id);
CREATE INDEX IF NOT EXISTS idx_bt_session_status     ON backtest_sessions(status);

-- backtest_results
CREATE INDEX IF NOT EXISTS idx_bt_results_session    ON backtest_results(session_id);

-- pattern_scores
CREATE INDEX IF NOT EXISTS idx_ps_pattern_id         ON pattern_scores(pattern_id);
CREATE INDEX IF NOT EXISTS idx_ps_theory_id          ON pattern_scores(theory_id);

-- theory_versions
CREATE INDEX IF NOT EXISTS idx_tv_theory_id          ON theory_versions(theory_id);
