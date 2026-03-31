-- Smart Aggressive Engine trade decision log
-- Every position opened by the smart engine is logged here with all decision parameters and outcome

CREATE TABLE IF NOT EXISTS smart_trade_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        VARCHAR(36) NOT NULL,
    symbol            VARCHAR(20) NOT NULL,

    -- Decision
    direction         VARCHAR(4)  NOT NULL,          -- BUY | SELL
    direction_score   SMALLINT    NOT NULL,           -- -3 to +3 (voting result)

    -- Market parameters at entry time
    atr_value         DECIMAL(12,5),
    ema20_value       DECIMAL(12,5),
    hmm_state         SMALLINT,
    hmm_state_label   VARCHAR(50),
    hmm_confidence    DECIMAL(6,4),                  -- 0.0 - 1.0
    close_price       DECIMAL(12,5),
    spread_pips       DECIMAL(8,3),

    -- Voting detail
    vote_hmm          SMALLINT,                      -- +1 / 0 / -1
    vote_ema          SMALLINT,
    vote_momentum     SMALLINT,

    -- Entry & targets
    entry_price       DECIMAL(12,5),
    tp_price          DECIMAL(12,5),
    sl_price          DECIMAL(12,5),
    tp_atr_mult       DECIMAL(5,2),
    sl_atr_mult       DECIMAL(5,2),
    volume            DECIMAL(10,4),
    mt5_ticket        BIGINT,

    -- Outcome (filled when position closes)
    exit_price        DECIMAL(12,5),
    profit_usd        DECIMAL(12,2),
    outcome           VARCHAR(10),                   -- WIN | LOSS | BE
    close_reason      VARCHAR(20),                   -- TP_HIT | SL_HIT | MANUAL | ENGINE
    duration_s        INTEGER,

    -- Timestamps
    opened_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_smart_trade_log_session ON smart_trade_log(session_id);
CREATE INDEX IF NOT EXISTS idx_smart_trade_log_symbol  ON smart_trade_log(symbol, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_smart_trade_log_outcome ON smart_trade_log(outcome) WHERE outcome IS NOT NULL;
