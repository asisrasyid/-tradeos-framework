-- =============================================================================
-- V1__create_tables.sql
-- TradeOS v5.1 — All 10 tables
-- Idempotent: CREATE TABLE IF NOT EXISTS
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. patterns
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patterns (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                 VARCHAR(100) UNIQUE NOT NULL,
    name                 VARCHAR(200) NOT NULL,
    description          TEXT,
    pattern_type         VARCHAR(50) NOT NULL,
    -- 'state_sequence' | 'c_code_combo' | 'composite'
    timeframe            VARCHAR(10),
    state_sequence       JSONB,
    -- {"seq": [0,0,3,2,4], "min_log_prob": -8.5, "label": "S0S0S3S2S4"}
    state_seq_repr       VARCHAR(50),
    hmm_model_version    VARCHAR(50),
    source               VARCHAR(20) DEFAULT 'manual',
    -- 'manual' | 'mined_from_wins' | 'hmm_discovered'
    version              INTEGER DEFAULT 1,
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    deleted_at           TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- 2. theories
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS theories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    instrument      VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,   -- 'LONG' | 'SHORT' | 'BOTH'
    threshold       INTEGER NOT NULL DEFAULT 10,
    min_confidence  DECIMAL(5,2) DEFAULT 60.0,
    version         INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- 3. theory_factors
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS theory_factors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    pattern_id      UUID REFERENCES patterns(id),
    factor_code     VARCHAR(100) NOT NULL,
    factor_type     VARCHAR(30) NOT NULL,
    -- 'state_sequence_match' | 'c_code_condition' | 'hmm_state_current'
    decision_point  INTEGER NOT NULL,
    is_required     BOOLEAN DEFAULT FALSE,
    condition_logic TEXT,
    operator        VARCHAR(20),
    threshold_value DECIMAL(12,6),
    timeframe       VARCHAR(10),
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 4. hmm_models
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hmm_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    n_states        INTEGER NOT NULL,
    bic_score       DECIMAL(12,4),
    training_from   TIMESTAMPTZ NOT NULL,
    training_to     TIMESTAMPTZ NOT NULL,
    n_samples       INTEGER NOT NULL,
    model_pickle    BYTEA NOT NULL,
    scaler_pickle   BYTEA NOT NULL,
    state_labels    JSONB,
    -- {"0": "Trending Bull", "1": "Trending Bear", ...}
    feature_names   JSONB,
    -- ["ATR_pct", "momentum_z", "swing_prox", "body_dom", "htf_slope", "liq_prox"]
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 5. trade_log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id           UUID NOT NULL REFERENCES theories(id),
    instrument          VARCHAR(20) NOT NULL,
    timeframe           VARCHAR(10) NOT NULL,
    signal_time         TIMESTAMPTZ NOT NULL,
    direction           VARCHAR(10) NOT NULL,   -- 'LONG' | 'SHORT'
    entry_price         DECIMAL(12,5),
    sl_price            DECIMAL(12,5),
    tp_price            DECIMAL(12,5),
    composite_score     INTEGER NOT NULL,
    confidence_pct      DECIMAL(5,2),
    p_win_at_signal     DECIMAL(5,4),
    bayesian_sample_n   INTEGER,
    state_sequence      JSONB NOT NULL,
    -- {"seq": [0,0,3,2,4], "repr": "S0S0S3S2S4", "log_prob": -8.5}
    factor_snapshot     JSONB NOT NULL,
    -- {"HTF_BIAS_BULLISH": {"met": true, "score": 1.0, "dp": 3}, ...}
    hmm_model_version   VARCHAR(50),
    outcome             VARCHAR(15),    -- 'WIN' | 'LOSS' | 'BREAK_EVEN' | NULL
    pnl_pips            DECIMAL(8,2),
    rr_actual           DECIMAL(6,3),
    signal_expired      BOOLEAN DEFAULT FALSE,
    executed            BOOLEAN DEFAULT FALSE,
    closed_at           TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 6. bayesian_counters
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bayesian_counters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    state_seq_hash  VARCHAR(16) NOT NULL,
    state_seq_repr  VARCHAR(50) NOT NULL,
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    breakeven       INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    p_win_current   DECIMAL(5,4) DEFAULT 0.5000,
    confidence_tier VARCHAR(20) DEFAULT 'insufficient',
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_bayesian_counter
        UNIQUE(theory_id, state_seq_hash, instrument, timeframe)
);

-- -----------------------------------------------------------------------------
-- 7. backtest_sessions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id       UUID NOT NULL REFERENCES theories(id),
    theory_version  INTEGER NOT NULL,
    hmm_model_id    UUID REFERENCES hmm_models(id),
    instrument      VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    date_from       TIMESTAMPTZ NOT NULL,
    date_to         TIMESTAMPTZ NOT NULL,
    params          JSONB DEFAULT '{}',
    status          VARCHAR(20) DEFAULT 'pending',
    -- 'pending' | 'running' | 'completed' | 'failed'
    triggered_by    VARCHAR(30) DEFAULT 'manual',
    ran_at          TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 8. backtest_results
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES backtest_sessions(id),
    total_signals       INTEGER DEFAULT 0,
    wins                INTEGER DEFAULT 0,
    losses              INTEGER DEFAULT 0,
    breakeven           INTEGER DEFAULT 0,
    win_rate            DECIMAL(5,2),
    profit_factor       DECIMAL(8,3),
    sharpe_ratio        DECIMAL(8,4),
    sortino_ratio       DECIMAL(8,4),
    max_drawdown        DECIMAL(5,2),
    avg_rr              DECIMAL(6,3),
    total_pips          DECIMAL(10,2),
    equity_curve        JSONB,
    state_distribution  JSONB,
    -- {"S0": 0.35, "S1": 0.10, "S2": 0.25, "S3": 0.15, "S4": 0.12, "S5": 0.03}
    best_seq_repr       VARCHAR(50),
    worst_seq_repr      VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 9. pattern_scores
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pattern_scores (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id           UUID NOT NULL REFERENCES patterns(id),
    theory_id            UUID NOT NULL REFERENCES theories(id),
    instrument           VARCHAR(20) NOT NULL,
    timeframe            VARCHAR(10),
    total_appearances    INTEGER DEFAULT 0,
    confirmed_wins       INTEGER DEFAULT 0,
    confirmed_losses     INTEGER DEFAULT 0,
    win_rate             DECIMAL(5,2),
    avg_log_prob         DECIMAL(8,4),
    last_updated         TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_pattern_score
        UNIQUE(pattern_id, theory_id, instrument, timeframe)
);

-- -----------------------------------------------------------------------------
-- 10. theory_versions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS theory_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id           UUID NOT NULL REFERENCES theories(id),
    version_number      INTEGER NOT NULL,
    snapshot            JSONB NOT NULL,
    change_notes        TEXT,
    win_rate_at_save    DECIMAL(5,2),
    backtest_session_id UUID REFERENCES backtest_sessions(id),
    saved_at            TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_theory_version
        UNIQUE(theory_id, version_number)
);
