-- ─── V5: sp_save_theory_version ──────────────────────────────────────────────
-- Stored procedure to safely save a theory snapshot as a new version.
-- Called by TheoryService.UpdateAsync before overwriting theory fields.
--
-- Args:
--   p_theory_id   UUID  — theory to version
--   p_snapshot    JSONB — full snapshot (theory fields + factors array)
--   p_change_notes TEXT — why the version was saved
--   p_win_rate    NUMERIC — optional win_rate at this point in time
--
-- Returns: the new version_number that was inserted.

CREATE OR REPLACE FUNCTION sp_save_theory_version(
    p_theory_id    UUID,
    p_snapshot     JSONB,
    p_change_notes TEXT    DEFAULT NULL,
    p_win_rate     NUMERIC DEFAULT NULL
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_next_version INT;
BEGIN
    -- Get the next version number (MAX + 1, or 1 if no versions yet)
    SELECT COALESCE(MAX(version_number), 0) + 1
    INTO   v_next_version
    FROM   theory_versions
    WHERE  theory_id = p_theory_id;

    INSERT INTO theory_versions (
        id,
        theory_id,
        version_number,
        snapshot,
        change_notes,
        win_rate_at_save,
        saved_at
    )
    VALUES (
        gen_random_uuid(),
        p_theory_id,
        v_next_version,
        p_snapshot,
        p_change_notes,
        p_win_rate,
        NOW()
    );

    RETURN v_next_version;
END;
$$;

-- ─── Signal expiry helper ─────────────────────────────────────────────────────
-- Mark signals as expired based on timeframe window.
-- Called periodically (or on-demand) to clean up open signals.
--
-- Expiry windows:
--   M1   →  5 minutes
--   M5   → 25 minutes
--   M15  →  1 hour
--   H1   →  5 hours
--   H4   → 20 hours
--   D1   →  5 days
--   default → 24 hours

CREATE OR REPLACE FUNCTION fn_expire_signals()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_expired INT;
BEGIN
    UPDATE trade_log
    SET signal_expired = TRUE
    WHERE outcome IS NULL
      AND signal_expired = FALSE
      AND (
          (timeframe = 'M1'  AND signal_time < NOW() - INTERVAL  '5 minutes')  OR
          (timeframe = 'M5'  AND signal_time < NOW() - INTERVAL '25 minutes')  OR
          (timeframe = 'M15' AND signal_time < NOW() - INTERVAL  '1 hour')     OR
          (timeframe = 'H1'  AND signal_time < NOW() - INTERVAL  '5 hours')    OR
          (timeframe = 'H4'  AND signal_time < NOW() - INTERVAL '20 hours')    OR
          (timeframe = 'D1'  AND signal_time < NOW() - INTERVAL  '5 days')     OR
          (timeframe NOT IN ('M1','M5','M15','H1','H4','D1')
           AND signal_time < NOW() - INTERVAL '24 hours')
      );

    GET DIAGNOSTICS v_expired = ROW_COUNT;
    RETURN v_expired;
END;
$$;
