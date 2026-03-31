-- =============================================================================
-- V4__seed_ccodes.sql
-- TradeOS v5.1 — Seed standard C-Code patterns
-- Idempotent: INSERT ON CONFLICT DO NOTHING
-- =============================================================================

-- Seed standard C-Code patterns (c_code_combo type — no state sequence)
-- These are reference patterns that theory_factors can reference by code.

INSERT INTO patterns (code, name, description, pattern_type, source)
VALUES
    -- Market Structure
    ('BOS_BULLISH',            'Break of Structure — Bullish',      'BOS bullish detected by smartmoneyconcepts',        'c_code_combo', 'manual'),
    ('BOS_BEARISH',            'Break of Structure — Bearish',      'BOS bearish detected by smartmoneyconcepts',        'c_code_combo', 'manual'),
    ('CHOCH_BULLISH',          'Change of Character — Bullish',     'CHoCH bullish detected by smartmoneyconcepts',      'c_code_combo', 'manual'),
    ('CHOCH_BEARISH',          'Change of Character — Bearish',     'CHoCH bearish detected by smartmoneyconcepts',      'c_code_combo', 'manual'),
    ('OB_BULLISH_ACTIVE',      'Order Block Bullish — Active',      'Active bullish OB present',                         'c_code_combo', 'manual'),
    ('OB_BEARISH_ACTIVE',      'Order Block Bearish — Active',      'Active bearish OB present',                         'c_code_combo', 'manual'),
    ('PRICE_IN_OB_BULL',       'Price in Bullish OB',               'Price currently inside bullish OB zone',            'c_code_combo', 'manual'),
    ('PRICE_IN_OB_BEAR',       'Price in Bearish OB',               'Price currently inside bearish OB zone',            'c_code_combo', 'manual'),
    ('FVG_BULLISH',            'Fair Value Gap — Bullish',          'Bullish FVG present',                               'c_code_combo', 'manual'),
    ('FVG_BEARISH',            'Fair Value Gap — Bearish',          'Bearish FVG present',                               'c_code_combo', 'manual'),
    ('EQH_SWEPT',              'Equal Highs Swept',                 'Liquidity from equal highs was swept',              'c_code_combo', 'manual'),
    ('EQL_SWEPT',              'Equal Lows Swept',                  'Liquidity from equal lows was swept',               'c_code_combo', 'manual'),

    -- Trend & Regime
    ('HTF_BIAS_BULLISH',       'HTF Bias — Bullish',                'H4 HMM state = S0 Trending Bull',                   'c_code_combo', 'manual'),
    ('HTF_BIAS_BEARISH',       'HTF Bias — Bearish',                'H4 HMM state = S1 Trending Bear',                   'c_code_combo', 'manual'),
    ('HMM_STATE_IS_RETEST',    'HMM State — Retest Zone (S4)',      'Current HMM state = S4 Retest/Pullback',            'c_code_combo', 'manual'),
    ('HMM_STATE_IS_POST_BOS',  'HMM State — Post-BOS Expansion (S3)','Current HMM state = S3 Post-BOS',                 'c_code_combo', 'manual'),
    ('HMM_STATE_IS_RANGING',   'HMM State — Ranging (S2)',          'Current HMM state = S2 Ranging Low Volatility',     'c_code_combo', 'manual'),
    ('MARKET_TRENDING',        'Market Trending (ADX)',             'ADX indicates trending market',                     'c_code_combo', 'manual'),
    ('ABOVE_200EMA',           'Price Above 200 EMA',               'Close > 200 EMA',                                   'c_code_combo', 'manual'),

    -- Momentum & Candle
    ('CANDLE_MOMENTUM_BULL',   'Candle Momentum — Bullish',         'Bullish candle momentum score from pandas-ta',      'c_code_combo', 'manual'),
    ('CANDLE_MOMENTUM_BEAR',   'Candle Momentum — Bearish',         'Bearish candle momentum score from pandas-ta',      'c_code_combo', 'manual'),
    ('HIGH_VOLUME',            'High Volume',                       'Volume above threshold',                            'c_code_combo', 'manual'),
    ('ATR_NORMAL',             'ATR Normal Range',                  'ATR within normal range (not spiking)',             'c_code_combo', 'manual'),

    -- Session
    ('SESSION_LONDON',         'London Session Active',             'Within London trading session',                     'c_code_combo', 'manual'),
    ('SESSION_NY',             'New York Session Active',           'Within New York trading session',                   'c_code_combo', 'manual'),
    ('SESSION_LONDON_OPEN_KZ', 'London Open Kill Zone',             'London open kill zone active',                      'c_code_combo', 'manual'),
    ('SESSION_NY_KZ',          'New York Kill Zone',                'New York kill zone active',                         'c_code_combo', 'manual')

ON CONFLICT (code) DO NOTHING;
