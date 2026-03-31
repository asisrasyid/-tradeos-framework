"""
bulk_download_ohlc.py — TradeOS
================================
Standalone script untuk download OHLC XAUUSDc dari MT5 ke PostgreSQL.
Jalankan sekali untuk populate initial data tanpa perlu restart sidecar.

Cara pakai:
    cd project/python-sidecar
    python scripts/bulk_download_ohlc.py

Atau dengan custom symbol/dates:
    python scripts/bulk_download_ohlc.py --symbol XAUUSDc --from 2025-01-01 --to 2025-12-31
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

# ── Path setup ────────────────────────────────────────────────────────────────
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# lib_local disabled: use system-installed packages for Python 3.12

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bulk_download")

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_SYMBOL     = "XAUUSDc"
DEFAULT_FROM       = "2025-01-01"
DEFAULT_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1"]

_TF_MAP: dict[str, int] = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}


# ── MT5 fetch (synchronous) ───────────────────────────────────────────────────

def _fetch_mt5(symbol: str, timeframe: str, date_from: datetime, date_to: datetime):
    try:
        import MetaTrader5 as mt5
        import pandas as pd
    except ImportError:
        logger.error("MetaTrader5 atau pandas tidak tersedia. Install: pip install MetaTrader5 pandas")
        return None

    # Init MT5
    if mt5.terminal_info() is None:
        login    = int(os.getenv("MT5_LOGIN", "0") or 0)
        password = os.getenv("MT5_PASSWORD", "")
        server   = os.getenv("MT5_SERVER",   "")
        if login and password and server:
            ok = mt5.initialize(login=login, password=password, server=server)
        else:
            ok = mt5.initialize()
        if not ok:
            logger.error("MT5 initialize gagal: %s", mt5.last_error())
            return None
        logger.info("MT5 terhubung: %s", mt5.terminal_info().name)

    tf_int = _TF_MAP.get(timeframe.upper())
    if tf_int is None:
        logger.error("TF tidak dikenal: %s (pilihan: %s)", timeframe, list(_TF_MAP))
        return None

    logger.info("  Fetching %s/%s dari MT5 (%s → %s)…",
                symbol, timeframe,
                date_from.strftime("%Y-%m-%d"),
                date_to.strftime("%Y-%m-%d"))

    rates = mt5.copy_rates_range(symbol, tf_int, date_from, date_to)
    if rates is None or len(rates) == 0:
        logger.warning("  MT5 tidak return data: %s", mt5.last_error())
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    if "tick_volume" in df.columns and "volume" not in df.columns:
        df = df.rename(columns={"tick_volume": "volume"})
    if "volume" not in df.columns:
        df["volume"] = 0.0

    logger.info("  Fetched %d bars", len(df))
    return df[["time", "open", "high", "low", "close", "volume"]]


# ── PostgreSQL upsert (synchronous via asyncpg) ───────────────────────────────

async def _save_to_db(df, symbol: str, timeframe: str) -> int:
    from services.ohlc_store import save_ohlc, update_sync_log
    saved = await save_ohlc(df, symbol, timeframe)
    if saved > 0:
        new_last = df["time"].max().to_pydatetime()
        await update_sync_log(symbol, timeframe, "ok", new_last)
    return saved


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(symbol: str, timeframes: list[str], date_from_str: str, date_to_str: str):
    from services.ohlc_store import init_schema

    logger.info("=" * 60)
    logger.info("TradeOS OHLC Bulk Download")
    logger.info("Symbol    : %s", symbol)
    logger.info("Timeframes: %s", ", ".join(timeframes))
    logger.info("Date From : %s", date_from_str)
    logger.info("Date To   : %s", date_to_str)
    logger.info("=" * 60)

    # 1. Init DB schema
    logger.info("[1/3] Inisialisasi schema PostgreSQL…")
    await init_schema()

    # 2. Parse dates — MT5 requires naive datetime (no tzinfo)
    date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
    date_to   = datetime.strptime(date_to_str,   "%Y-%m-%d")

    # 3. Fetch & save each TF
    logger.info("[2/3] Fetching data dari MT5…")
    total_saved = 0
    results = []

    for tf in timeframes:
        logger.info("\n── %s/%s ──", symbol, tf)
        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_mt5, symbol, tf, date_from, date_to
            )
            if df is None or df.empty:
                logger.warning("  Tidak ada data untuk %s/%s", symbol, tf)
                results.append((tf, 0, "no_data"))
                continue

            saved = await _save_to_db(df, symbol, tf)
            total_saved += saved
            results.append((tf, saved, "ok"))

        except Exception as e:
            logger.error("  Error %s/%s: %s", symbol, tf, e)
            results.append((tf, 0, f"error: {e}"))

    # 4. Summary
    logger.info("\n[3/3] SELESAI — Summary:")
    logger.info("  %-8s  %10s  %s", "TF", "Bars Saved", "Status")
    logger.info("  " + "-" * 35)
    for tf, count, status in results:
        logger.info("  %-8s  %10d  %s", tf, count, status)
    logger.info("  " + "-" * 35)
    logger.info("  %-8s  %10d  bars total di-save", "TOTAL", total_saved)
    logger.info("\nData siap — restart sidecar agar auto-sync berjalan.")


def main():
    parser = argparse.ArgumentParser(description="Bulk download OHLC dari MT5 ke PostgreSQL")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help=f"Symbol MT5 (default: {DEFAULT_SYMBOL})")
    parser.add_argument("--from",   dest="date_from", default=DEFAULT_FROM,
                        help=f"Tanggal mulai YYYY-MM-DD (default: {DEFAULT_FROM})")
    # Default date_to: last Friday if today is weekend, else today
    _today = datetime.now()
    _days_back = (_today.weekday() - 4) % 7  # 0=Mon..6=Sun → days since last Fri
    _last_trading_day = (_today - __import__('datetime').timedelta(days=_days_back)).strftime("%Y-%m-%d")
    parser.add_argument("--to",     dest="date_to",
                        default=_last_trading_day,
                        help="Tanggal akhir YYYY-MM-DD (default: hari trading terakhir)")
    parser.add_argument("--tf",     nargs="+", default=DEFAULT_TIMEFRAMES,
                        help=f"Timeframe(s) (default: {' '.join(DEFAULT_TIMEFRAMES)})")
    args = parser.parse_args()

    asyncio.run(run(
        symbol       = args.symbol,
        timeframes   = [tf.upper() for tf in args.tf],
        date_from_str= args.date_from,
        date_to_str  = args.date_to,
    ))


if __name__ == "__main__":
    main()
