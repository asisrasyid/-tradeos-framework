"""OHLC data fetching router."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.schemas import OhlcFetchRequest, OhlcFetchResponse, OhlcBar

logger = logging.getLogger(__name__)
router = APIRouter()


class OhlcCacheRequest(BaseModel):
    instrument: str
    timeframe:  str
    date_from:  str
    date_to:    str


@router.post("/cache")
async def cache_ohlc(req: OhlcCacheRequest) -> dict:
    """
    Fetch OHLC from MT5 and store in ohlc_cache DB table.
    Subsequent backtest/training calls will use cached data (no MT5 fetch).
    Call once per TF at session start.
    """
    from routers.hmm import _fetch_historical_mt5
    from services.ohlc_store import save_ohlc, cache_count
    import pandas as pd

    try:
        df = _fetch_historical_mt5(req.instrument, req.timeframe, req.date_from, req.date_to)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MT5 fetch failed: {e}")

    if df is None or len(df) < 10:
        raise HTTPException(status_code=502, detail="MT5 returned no data")

    saved = await save_ohlc(df, req.instrument, req.timeframe)
    total = await cache_count(req.instrument, req.timeframe)

    return {
        "instrument": req.instrument,
        "timeframe":  req.timeframe,
        "bars_saved": saved,
        "total_cached": total,
        "date_from":  req.date_from,
        "date_to":    req.date_to,
    }


@router.post("/fetch", response_model=OhlcFetchResponse)
async def fetch_ohlc(req: OhlcFetchRequest) -> OhlcFetchResponse:
    """
    Fetch OHLC data from MT5 (primary) or yfinance (fallback).
    Returns normalized list of OHLC bars.
    """
    try:
        bars = await _fetch_from_mt5(req.instrument, req.timeframe, req.bars)
        source = "mt5"
    except Exception as e:
        logger.warning(f"MT5 unavailable ({e}), falling back to yfinance")
        bars = await _fetch_from_yfinance(req.instrument, req.timeframe, req.bars)
        source = "yfinance"

    return OhlcFetchResponse(
        instrument=req.instrument,
        timeframe=req.timeframe,
        bars=bars,
        source=source,
    )


async def _fetch_from_mt5(instrument: str, timeframe: str, bars: int) -> list[OhlcBar]:
    """Fetch recent N bars from MetaTrader5. Does NOT shutdown MT5 — preserves active session."""
    try:
        import MetaTrader5 as mt5  # type: ignore
        import os
        import pandas as pd

        # Connect only if not already connected
        if mt5.terminal_info() is None:
            login    = int(os.getenv("MT5_LOGIN", "0"))
            password = os.getenv("MT5_PASSWORD", "")
            server   = os.getenv("MT5_SERVER", "")
            ok = mt5.initialize(login=login, password=password, server=server) \
                 if (login and password and server) else mt5.initialize()
            if not ok:
                raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

        TF_MAP = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 16385, "H4": 16388, "H8": 16392,
            "D1": 16408, "W1": 32769, "MN1": 49153, "MN": 49153,
        }
        tf = TF_MAP.get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        rates = mt5.copy_rates_from_pos(instrument, tf, 0, bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No data returned for {instrument} {timeframe}: {mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s").dt.strftime("%Y-%m-%dT%H:%M:%S")

        return [
            OhlcBar(
                time=str(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("real_volume", row.get("tick_volume", 0))),
            )
            for _, row in df.iterrows()
        ]
    except ImportError:
        raise RuntimeError("MetaTrader5 package not available on this platform")


async def _fetch_from_yfinance(instrument: str, timeframe: str, bars: int) -> list[OhlcBar]:
    """Fetch from yfinance (fallback for daily data / NAS100)."""
    import yfinance as yf  # type: ignore
    import pandas as pd

    yf_symbol_map = {
        "XAUUSD": "GC=F",
        "NAS100": "^IXIC",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X",
    }
    symbol = yf_symbol_map.get(instrument.upper(), instrument)

    tf_map = {
        "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
        "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1wk",
    }
    interval = tf_map.get(timeframe.upper(), "1d")

    # Use Ticker.history() — always returns flat columns, no MultiIndex issues
    # yf.download() in yfinance >= 0.2.38 returns MultiIndex(price, ticker) by default
    period = "60d" if interval in ("1m", "5m", "15m", "30m") else "2y"
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        raise HTTPException(status_code=502, detail=f"No yfinance data for {instrument}")

    # Ticker.history() index is DatetimeIndex — reset to column
    df = df.tail(bars).reset_index()

    # Normalize column names to handle any casing
    df.columns = [str(c).strip() for c in df.columns]
    time_col = "Datetime" if "Datetime" in df.columns else "Date"
    df[time_col] = pd.to_datetime(df[time_col]).dt.strftime("%Y-%m-%dT%H:%M:%S")

    return [
        OhlcBar(
            time=str(row[time_col]),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row.get("Volume", 0) or 0),
        )
        for _, row in df.iterrows()
    ]
