-- OHLC cache table — stores fetched bars per instrument/timeframe
-- Backtest reads from here instead of fetching MT5 every time
CREATE TABLE IF NOT EXISTS ohlc_cache (
    instrument  VARCHAR(20)       NOT NULL,
    timeframe   VARCHAR(10)       NOT NULL,
    bar_time    TIMESTAMP         NOT NULL,
    open        DOUBLE PRECISION  NOT NULL,
    high        DOUBLE PRECISION  NOT NULL,
    low         DOUBLE PRECISION  NOT NULL,
    close       DOUBLE PRECISION  NOT NULL,
    volume      DOUBLE PRECISION  NOT NULL DEFAULT 0,
    fetched_at  TIMESTAMP         NOT NULL DEFAULT NOW(),
    PRIMARY KEY (instrument, timeframe, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_ohlc_cache_lookup
    ON ohlc_cache (instrument, timeframe, bar_time);
