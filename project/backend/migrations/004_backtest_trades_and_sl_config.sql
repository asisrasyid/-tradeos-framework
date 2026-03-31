-- Migration 004: Backtest trades table + SL/TP config columns
-- Run once against your PostgreSQL database

-- 1. Add SL/TP config columns to backtest_sessions
ALTER TABLE backtest_sessions
  ADD COLUMN IF NOT EXISTS sl_type       VARCHAR(10)      NOT NULL DEFAULT 'atr',
  ADD COLUMN IF NOT EXISTS sl_value      NUMERIC(10,4)    NOT NULL DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS tp_type       VARCHAR(10)      NOT NULL DEFAULT 'atr',
  ADD COLUMN IF NOT EXISTS tp_value      NUMERIC(10,4)    NOT NULL DEFAULT 2.0,
  ADD COLUMN IF NOT EXISTS max_hold_bars INTEGER          NOT NULL DEFAULT 20;

-- 2. Create backtest_trades table
CREATE TABLE IF NOT EXISTS backtest_trades (
  id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id   UUID         NOT NULL REFERENCES backtest_sessions(id) ON DELETE CASCADE,
  bar_index    INTEGER      NOT NULL,
  time         TEXT,
  direction    VARCHAR(10)  NOT NULL,
  entry        NUMERIC(18,5) NOT NULL,
  sl           NUMERIC(18,5) NOT NULL,
  tp           NUMERIC(18,5) NOT NULL,
  sl_type      VARCHAR(10)  NOT NULL DEFAULT 'atr',
  tp_type      VARCHAR(10)  NOT NULL DEFAULT 'atr',
  atr          NUMERIC(18,5) NOT NULL DEFAULT 0,
  outcome      VARCHAR(20)  NOT NULL DEFAULT 'breakeven',
  exit_bar     INTEGER      NOT NULL DEFAULT 0,
  exit_price   NUMERIC(18,5) NOT NULL DEFAULT 0,
  pnl_pips     NUMERIC(10,2) NOT NULL DEFAULT 0,
  rr_achieved  NUMERIC(10,3) NOT NULL DEFAULT 0,
  seq_repr     TEXT,
  similarity   NUMERIC(6,3) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_session_id ON backtest_trades(session_id);
