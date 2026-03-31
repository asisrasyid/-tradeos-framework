-- V8: Add mt5_ticket to trade_log for auto-executed positions
-- Stores the MT5 position ticket when a signal is auto-executed

ALTER TABLE trade_log
    ADD COLUMN IF NOT EXISTS mt5_ticket BIGINT;

COMMENT ON COLUMN trade_log.mt5_ticket IS 'MT5 position ticket number when auto-executed by signal engine. NULL = not yet executed.';
