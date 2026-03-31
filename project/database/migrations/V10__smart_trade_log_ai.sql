-- Add AI decision columns to smart_trade_log
ALTER TABLE smart_trade_log
    ADD COLUMN IF NOT EXISTS ai_enabled       BOOLEAN      DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS llm_model        VARCHAR(60),
    ADD COLUMN IF NOT EXISTS llm_reasoning    TEXT,
    ADD COLUMN IF NOT EXISTS llm_confidence   DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS llm_prompt_ver   VARCHAR(10),
    ADD COLUMN IF NOT EXISTS llm_latency_ms   INTEGER,
    ADD COLUMN IF NOT EXISTS llm_skip_reason  TEXT,
    ADD COLUMN IF NOT EXISTS entries_per_decision INTEGER;
