"""
OHLC Syncer — TradeOS v1.0
Background service: load full history sekali saat startup,
lalu auto-update incremental setiap interval per timeframe.

Target default:
  Symbol    : XAUUSDc
  Timeframes: M1, M5, M15, M30, H1
  Start date: 2025-01-01

Flow per TF:
  1. Saat startup → cek last_bar_time di DB
     - Kosong  → full load dari INITIAL_FROM sampai sekarang
     - Ada data → incremental dari last_bar_time + 1 detik
  2. Loop background → tidur sesuai interval, lalu incremental lagi
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Konfigurasi target sync ───────────────────────────────────────────────────

INITIAL_FROM = "2025-01-01"   # Mulai load dari tanggal ini

TARGET_SYMBOL = os.getenv("OHLC_SYNC_SYMBOL", "XAUUSDm")

TARGET_TIMEFRAMES: list[str] = ["M1", "M5", "M15", "M30", "H1"]

# Interval (detik) antar-sync per timeframe
_SYNC_INTERVAL: dict[str, int] = {
    "M1":  60,
    "M5":  300,
    "M15": 900,
    "M30": 1800,
    "H1":  3600,
}

# MT5 timeframe mapping
_TF_MAP: dict[str, int] = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "H8": 16392,
    "D1": 16408,
}

# Flag global: apakah syncer sudah berjalan
_running = False


# ── MT5 fetch helper ──────────────────────────────────────────────────────────

def _mt5_fetch_range(
    instrument: str,
    timeframe:  str,
    date_from:  datetime,
    date_to:    datetime,
) -> Optional["pd.DataFrame"]:  # noqa: F821
    """
    Fetch OHLC bar dari MT5 untuk rentang datetime.
    Returns DataFrame atau None jika gagal.
    """
    try:
        import MetaTrader5 as mt5  # type: ignore
        import pandas as pd
    except ImportError:
        logger.error("[ohlc_syncer] MetaTrader5 / pandas tidak tersedia")
        return None

    # Inisialisasi MT5 jika belum terhubung
    if mt5.terminal_info() is None:
        login    = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server   = os.getenv("MT5_SERVER", "")
        ok = (
            mt5.initialize(login=login, password=password, server=server)
            if (login and password and server)
            else mt5.initialize()
        )
        if not ok:
            logger.error("[ohlc_syncer] MT5 initialize gagal: %s", mt5.last_error())
            return None

    tf_int = _TF_MAP.get(timeframe.upper())
    if tf_int is None:
        logger.error("[ohlc_syncer] TF tidak dikenal: %s", timeframe)
        return None

    # Coba symbol_select — non-fatal, beberapa broker gagal di weekend
    if not mt5.symbol_select(instrument, True):
        logger.warning(
            "[ohlc_syncer] symbol_select(%s) gagal: %s — tetap coba fetch",
            instrument, mt5.last_error(),
        )
        # Log available XAU symbols untuk diagnosa nama yang benar
        all_syms = mt5.symbols_get()
        if all_syms:
            xau_syms = [s.name for s in all_syms if "XAU" in s.name.upper()]
            if xau_syms:
                logger.info("[ohlc_syncer] XAU symbols tersedia: %s", xau_syms)
            else:
                logger.warning("[ohlc_syncer] Tidak ada symbol XAU ditemukan di terminal")

    rates = mt5.copy_rates_range(instrument, tf_int, date_from, date_to)
    if rates is None or len(rates) == 0:
        logger.warning(
            "[ohlc_syncer] MT5 tidak return data %s/%s %s→%s: %s",
            instrument, timeframe, date_from, date_to, mt5.last_error(),
        )
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # Buat kolom volume tunggal — hindari rename ganda yang bisa duplikat kolom
    if "volume" not in df.columns:
        if "tick_volume" in df.columns:
            df["volume"] = df["tick_volume"].astype(float)
        elif "real_volume" in df.columns:
            df["volume"] = df["real_volume"].astype(float)
        else:
            df["volume"] = 0.0

    # Pastikan kolom yang diperlukan ada
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            logger.warning("[ohlc_syncer] Kolom '%s' tidak ada di data MT5", col)
            return None

    return df[["time", "open", "high", "low", "close", "volume"]]


# ── Core sync per satu TF ─────────────────────────────────────────────────────

async def sync_one(instrument: str, timeframe: str) -> int:
    """
    Sync incremental satu instrument/timeframe.
    Returns jumlah bar baru yang disimpan.
    """
    from services.ohlc_store import (
        get_last_bar_time, save_ohlc, update_sync_log,
    )

    now_utc = datetime.now(timezone.utc)
    # MT5 copy_rates_range requires naive datetime (no tzinfo) — UTC internally
    # Cap at last Friday if today is weekend (Sat=5, Sun=6)
    _now = datetime.utcnow()
    _weekday = _now.weekday()
    if _weekday == 5:   # Saturday → go back 1 day to Friday
        _now = _now - timedelta(days=1)
    elif _weekday == 6: # Sunday → go back 2 days to Friday
        _now = _now - timedelta(days=2)
    now_naive = _now.replace(hour=23, minute=59, second=59, microsecond=0)

    # Tentukan titik mulai fetch
    last_bar = await get_last_bar_time(instrument, timeframe)
    if last_bar is None:
        # Full load dari INITIAL_FROM — naive UTC
        date_from = datetime.strptime(INITIAL_FROM, "%Y-%m-%d")
        logger.info(
            "[ohlc_syncer] Full load %s/%s dari %s",
            instrument, timeframe, INITIAL_FROM,
        )
    else:
        # Incremental: mulai 1 detik setelah bar terakhir — strip tzinfo untuk MT5
        last_bar_naive = last_bar.replace(tzinfo=None) if last_bar.tzinfo else last_bar
        date_from = last_bar_naive + timedelta(seconds=1)
        if date_from >= now_naive:
            logger.debug("[ohlc_syncer] %s/%s sudah up-to-date", instrument, timeframe)
            await update_sync_log(instrument, timeframe, "ok", last_bar)
            return 0

    await update_sync_log(instrument, timeframe, "syncing", last_bar)

    # Fetch dari MT5 (sync call di thread pool agar tidak block event loop)
    try:
        df = await asyncio.get_event_loop().run_in_executor(
            None,
            _mt5_fetch_range,
            instrument, timeframe, date_from, now_naive,
        )
    except Exception as e:
        logger.error("[ohlc_syncer] MT5 fetch error %s/%s: %s", instrument, timeframe, e)
        await update_sync_log(instrument, timeframe, "error", last_bar, str(e))
        return 0

    if df is None or df.empty:
        await update_sync_log(instrument, timeframe, "ok", last_bar)
        return 0

    saved = await save_ohlc(df, instrument, timeframe)
    new_last_bar = df["time"].max().to_pydatetime()
    await update_sync_log(instrument, timeframe, "ok", new_last_bar)

    logger.info(
        "[ohlc_syncer] %s/%s → +%d bars (last: %s)",
        instrument, timeframe, saved, new_last_bar.strftime("%Y-%m-%d %H:%M"),
    )
    return saved


# ── Background loop per TF ────────────────────────────────────────────────────

async def _sync_loop(instrument: str, timeframe: str) -> None:
    """Loop background: sync lalu tidur sesuai interval."""
    interval = _SYNC_INTERVAL.get(timeframe.upper(), 300)

    # Sync awal (full load jika DB kosong)
    try:
        await sync_one(instrument, timeframe)
    except Exception as e:
        logger.error("[ohlc_syncer] Sync awal %s/%s error: %s", instrument, timeframe, e)

    # Loop incremental
    while True:
        try:
            await asyncio.sleep(interval)
            await sync_one(instrument, timeframe)
        except asyncio.CancelledError:
            logger.info("[ohlc_syncer] Loop %s/%s dibatalkan", instrument, timeframe)
            return
        except Exception as e:
            logger.error("[ohlc_syncer] Loop error %s/%s: %s", instrument, timeframe, e)
            await asyncio.sleep(30)   # backoff sebelum retry


# ── Public API ────────────────────────────────────────────────────────────────

_tasks: list[asyncio.Task] = []


def start_background_sync() -> None:
    """
    Daftarkan asyncio task untuk setiap (symbol × timeframe).
    Dipanggil dari FastAPI lifespan startup.
    """
    global _running
    if _running:
        logger.warning("[ohlc_syncer] Sudah berjalan — skip")
        return

    _running = True
    for tf in TARGET_TIMEFRAMES:
        task = asyncio.create_task(
            _sync_loop(TARGET_SYMBOL, tf),
            name=f"ohlc-sync-{TARGET_SYMBOL}-{tf}",
        )
        _tasks.append(task)
        logger.info("[ohlc_syncer] Task dimulai: %s/%s (interval %ds)", TARGET_SYMBOL, tf, _SYNC_INTERVAL[tf])

    logger.info("[ohlc_syncer] %d sync tasks aktif", len(_tasks))


async def trigger_manual_sync(instrument: Optional[str] = None, timeframe: Optional[str] = None) -> list[dict]:
    """
    Trigger sync manual. Jika instrument/timeframe None → sync semua.
    Returns list ringkasan hasil sync.
    """
    targets = []
    if instrument and timeframe:
        targets = [(instrument.upper(), timeframe.upper())]
    elif instrument:
        targets = [(instrument.upper(), tf) for tf in TARGET_TIMEFRAMES]
    else:
        targets = [(TARGET_SYMBOL, tf) for tf in TARGET_TIMEFRAMES]

    results = []
    for inst, tf in targets:
        try:
            saved = await sync_one(inst, tf)
            results.append({"instrument": inst, "timeframe": tf, "bars_added": saved, "status": "ok"})
        except Exception as e:
            results.append({"instrument": inst, "timeframe": tf, "bars_added": 0, "status": "error", "error": str(e)})

    return results
