"""
OHLC Store — TradeOS v3.0
Persistent OHLC storage di PostgreSQL (tabel ohlc_cache + ohlc_sync_log).

Tabel ohlc_cache  : data bar OHLC, di-upsert dari MT5
Tabel ohlc_sync_log : status & progress sync per (instrument, timeframe)

Dipakai oleh:
  - backtest_runner  : load data historis dari DB
  - hmm trainer      : load data training dari DB
  - ohlc_syncer      : tulis hasil fetch + update sync log
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_CONN_STR = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:P%40ss1234@localhost:5432/tradeos"
)

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL_OHLC_CACHE = """
CREATE TABLE IF NOT EXISTS ohlc_cache (
    id          BIGSERIAL PRIMARY KEY,
    instrument  VARCHAR(30)       NOT NULL,
    timeframe   VARCHAR(5)        NOT NULL,
    bar_time    TIMESTAMPTZ       NOT NULL,
    open        DOUBLE PRECISION  NOT NULL,
    high        DOUBLE PRECISION  NOT NULL,
    low         DOUBLE PRECISION  NOT NULL,
    close       DOUBLE PRECISION  NOT NULL,
    volume      DOUBLE PRECISION  NOT NULL DEFAULT 0,
    fetched_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ohlc_cache UNIQUE (instrument, timeframe, bar_time)
);
CREATE INDEX IF NOT EXISTS idx_ohlc_cache_lookup
    ON ohlc_cache (instrument, timeframe, bar_time DESC);
"""

_DDL_SYNC_LOG = """
CREATE TABLE IF NOT EXISTS ohlc_sync_log (
    instrument  VARCHAR(30) NOT NULL,
    timeframe   VARCHAR(5)  NOT NULL,
    last_bar    TIMESTAMPTZ,
    total_bars  INTEGER     NOT NULL DEFAULT 0,
    last_sync   TIMESTAMPTZ,
    status      VARCHAR(20) NOT NULL DEFAULT 'idle',
    error_msg   TEXT,
    PRIMARY KEY (instrument, timeframe)
);
"""


# ── Schema init (dipanggil saat startup) ──────────────────────────────────────

async def init_schema() -> None:
    """Buat tabel ohlc_cache dan ohlc_sync_log jika belum ada."""
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_CONN_STR)
        await conn.execute(_DDL_OHLC_CACHE)
        await conn.execute(_DDL_SYNC_LOG)
        await conn.close()
        logger.info("[ohlc_store] Schema OK (ohlc_cache + ohlc_sync_log)")
    except Exception as e:
        logger.error("[ohlc_store] Schema init failed: %s", e)


# ── Write helpers ─────────────────────────────────────────────────────────────

async def save_ohlc(df: pd.DataFrame, instrument: str, timeframe: str) -> int:
    """
    Upsert OHLC bars ke ohlc_cache.
    Returns jumlah baris yang di-upsert.
    """
    try:
        import asyncpg  # type: ignore
    except ImportError:
        logger.warning("[ohlc_store] asyncpg not available — skip save")
        return 0

    if df is None or df.empty:
        return 0

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # Normalize kolom waktu — konversi ke naive UTC agar asyncpg tidak campur aware/naive
    time_col = "bar_time" if "bar_time" in df.columns else "time"
    df[time_col] = pd.to_datetime(df[time_col], utc=True).dt.tz_convert(None)

    rows = [
        (
            instrument.upper(),
            timeframe.upper(),
            row[time_col].to_pydatetime(),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row.get("volume", 0) or 0),
        )
        for _, row in df.iterrows()
    ]

    try:
        conn = await asyncpg.connect(_CONN_STR)
        await conn.executemany(
            """
            INSERT INTO ohlc_cache
                (instrument, timeframe, bar_time, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (instrument, timeframe, bar_time)
            DO UPDATE SET
                open       = EXCLUDED.open,
                high       = EXCLUDED.high,
                low        = EXCLUDED.low,
                close      = EXCLUDED.close,
                volume     = EXCLUDED.volume,
                fetched_at = NOW()
            """,
            rows,
        )
        await conn.close()
        logger.info("[ohlc_store] Saved %d bars → %s/%s", len(rows), instrument, timeframe)
        return len(rows)
    except Exception as e:
        logger.warning("[ohlc_store] save_ohlc failed: %s", e)
        return 0


# ── Read helpers ──────────────────────────────────────────────────────────────

async def load_ohlc(
    instrument: str,
    timeframe:  str,
    date_from:  str,
    date_to:    str,
) -> Optional[pd.DataFrame]:
    """
    Load bar OHLC dari DB untuk rentang tanggal.
    Returns None jika data tidak cukup (< 10 bar).
    """
    try:
        import asyncpg  # type: ignore
    except ImportError:
        return None

    try:
        conn = await asyncpg.connect(_CONN_STR)
        # asyncpg requires datetime objects, not strings
        from datetime import datetime as _dt
        dt_from = _dt.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        dt_to   = _dt.fromisoformat(date_to)   if isinstance(date_to,   str) else date_to

        rows = await conn.fetch(
            """
            SELECT bar_time AS time, open, high, low, close, volume
            FROM   ohlc_cache
            WHERE  instrument = $1
              AND  timeframe  = $2
              AND  bar_time  >= $3
              AND  bar_time  <= $4
            ORDER  BY bar_time ASC
            """,
            instrument.upper(),
            timeframe.upper(),
            dt_from,
            dt_to,
        )
        await conn.close()

        if not rows or len(rows) < 10:
            return None

        df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
        logger.info("[ohlc_store] Loaded %d bars from DB %s/%s", len(df), instrument, timeframe)
        return df.reset_index(drop=True)

    except Exception as e:
        logger.warning("[ohlc_store] load_ohlc failed: %s", e)
        return None


async def get_last_bar_time(instrument: str, timeframe: str) -> Optional[datetime]:
    """
    Return timestamp bar terakhir yang tersimpan di DB.
    None jika belum ada data.
    """
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_CONN_STR)
        val = await conn.fetchval(
            """
            SELECT MAX(bar_time)
            FROM   ohlc_cache
            WHERE  instrument = $1 AND timeframe = $2
            """,
            instrument.upper(),
            timeframe.upper(),
        )
        await conn.close()
        return val  # datetime dengan timezone, atau None
    except Exception as e:
        logger.warning("[ohlc_store] get_last_bar_time failed: %s", e)
        return None


async def cache_count(instrument: str, timeframe: str) -> int:
    """Jumlah bar tersimpan untuk instrument/timeframe."""
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_CONN_STR)
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM ohlc_cache WHERE instrument=$1 AND timeframe=$2",
            instrument.upper(), timeframe.upper(),
        )
        await conn.close()
        return int(count or 0)
    except Exception:
        return 0


# ── Sync log helpers ──────────────────────────────────────────────────────────

async def update_sync_log(
    instrument: str,
    timeframe:  str,
    status:     str,
    last_bar:   Optional[datetime] = None,
    error_msg:  Optional[str]      = None,
) -> None:
    """Upsert status sync ke ohlc_sync_log."""
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_CONN_STR)
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM ohlc_cache WHERE instrument=$1 AND timeframe=$2",
            instrument.upper(), timeframe.upper(),
        )
        await conn.execute(
            """
            INSERT INTO ohlc_sync_log
                (instrument, timeframe, last_bar, total_bars, last_sync, status, error_msg)
            VALUES ($1, $2, $3, $4, NOW(), $5, $6)
            ON CONFLICT (instrument, timeframe) DO UPDATE SET
                last_bar  = COALESCE($3, ohlc_sync_log.last_bar),
                total_bars = $4,
                last_sync  = NOW(),
                status     = $5,
                error_msg  = $6
            """,
            instrument.upper(), timeframe.upper(),
            last_bar, int(total or 0), status, error_msg,
        )
        await conn.close()
    except Exception as e:
        logger.warning("[ohlc_store] update_sync_log failed: %s", e)


async def get_all_sync_status() -> list[dict]:
    """Return status sync semua instrument/timeframe dari ohlc_sync_log."""
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_CONN_STR)
        rows = await conn.fetch(
            """
            SELECT instrument, timeframe, last_bar, total_bars,
                   last_sync, status, error_msg
            FROM   ohlc_sync_log
            ORDER  BY instrument, timeframe
            """
        )
        await conn.close()
        return [
            {
                "instrument": r["instrument"],
                "timeframe":  r["timeframe"],
                "last_bar":   r["last_bar"].isoformat()  if r["last_bar"]  else None,
                "total_bars": r["total_bars"],
                "last_sync":  r["last_sync"].isoformat() if r["last_sync"] else None,
                "status":     r["status"],
                "error_msg":  r["error_msg"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("[ohlc_store] get_all_sync_status failed: %s", e)
        return []
