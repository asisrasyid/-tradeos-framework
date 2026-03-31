"""HMM training, classification, and state-sequence router."""

import base64
import logging
import pickle
import pandas as pd
from fastapi import APIRouter, HTTPException

from models.schemas import (
    HmmClassifyRequest, HmmClassifyResponse,
    HmmSequenceRequest, HmmSequenceResponse,
    HmmTrainRequest, HmmTrainResponse,
)
from services.feature_extractor import extract_features
from services.hmm_trainer import train_hmm, HmmTrainResult
from services.hmm_classifier import get_classifier, _compute_hash

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Train ────────────────────────────────────────────────────────────────────

@router.post("/train", response_model=HmmTrainResponse)
async def train(req: HmmTrainRequest) -> HmmTrainResponse:
    """
    Train Gaussian HMM via BIC K selection (K=4..8).
    Returns serialized model + scaler as base64 for storage in C# / DB.
    """
    if str(req.data_source).lower() == 'mt5':
        import asyncio
        df = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_historical_mt5, req.instrument, req.timeframe, req.date_from, req.date_to
        )
        if df is None or len(df) < 10:
            raise HTTPException(status_code=400, detail="MT5 fetch gagal atau data tidak cukup")
    else:
        df = await _fetch_historical(req.instrument, req.timeframe, req.date_from, req.date_to)
    if len(df) < 200:
        raise HTTPException(status_code=400, detail=f"Insufficient data: {len(df)} bars (need ≥ 200)")

    try:
        result: HmmTrainResult = train_hmm(
            df=df,
            instrument=req.instrument,
            timeframe=req.timeframe,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Load into classifier cache so it's ready immediately
    model, scaler = pickle.loads(result.model_pickle), pickle.loads(result.scaler_pickle)
    get_classifier().load_model(
        req.instrument, req.timeframe,
        model, scaler, result.version, result.state_labels,
    )

    return HmmTrainResponse(
        version=result.version,
        n_states=result.n_states,
        bic_score=result.bic_score,
        n_samples=result.n_samples,
        model_pickle_b64=base64.b64encode(result.model_pickle).decode(),
        scaler_pickle_b64=base64.b64encode(result.scaler_pickle).decode(),
        state_labels=result.state_labels,
    )


# ─── State Profile ────────────────────────────────────────────────────────────

@router.get("/state-profile")
async def state_profile(instrument: str, timeframe: str, recent_bars: int = 60):
    """
    Return per-state feature profile + recent bar sequence.
    Used by HMM Models UI State Inspector panel.
    """
    import pickle, json, os
    import numpy as np

    await _ensure_model_loaded(instrument, timeframe)

    # Load raw model from DB to access means_
    try:
        import asyncpg
        conn_str = os.getenv("DATABASE_URL", "postgresql://postgres:P%40ss1234@localhost:5432/tradeos")
        conn = await asyncpg.connect(conn_str)
        row = await conn.fetchrow(
            """SELECT model_pickle, scaler_pickle, state_labels, version
               FROM hmm_models
               WHERE instrument=$1 AND timeframe=$2 AND is_active=TRUE
               ORDER BY created_at DESC LIMIT 1""",
            instrument.upper(), timeframe.upper()
        )
        await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not row:
        raise HTTPException(status_code=404, detail=f"No model for {instrument}/{timeframe}")

    model  = pickle.loads(bytes(row["model_pickle"]))
    scaler = pickle.loads(bytes(row["scaler_pickle"]))
    labels = json.loads(row["state_labels"] or "{}")

    FEATURE_NAMES = ["ATR_pct", "momentum_z", "swing_prox", "body_dom", "htf_slope", "liq_prox"]
    FEATURE_DESC  = ["Volatility", "Momentum", "Near S/R", "Bar Strength", "HTF Direction", "Near Liquidity"]

    # Inverse-transform means to original scale
    raw_means = scaler.inverse_transform(model.means_)   # shape (K, 6)
    n_states  = model.n_components

    # Compute state frequency from transition matrix stationary distribution
    # Use eigenvector of transmat for stationary probs
    try:
        eigenvals, eigenvecs = np.linalg.eig(model.transmat_.T)
        stationary = eigenvecs[:, np.argmax(np.abs(eigenvals - 1.0) < 1e-6)].real
        stationary = np.abs(stationary) / np.abs(stationary).sum()
    except Exception:
        stationary = np.ones(n_states) / n_states

    states_profile = []
    for s in range(n_states):
        means = raw_means[s]
        states_profile.append({
            "state":      s,
            "label":      labels.get(str(s), f"S{s}"),
            "frequency":  round(float(stationary[s]) * 100, 1),
            "features": [
                {
                    "name":  FEATURE_NAMES[i],
                    "desc":  FEATURE_DESC[i],
                    "value": round(float(means[i]), 3),
                }
                for i in range(len(FEATURE_NAMES))
            ],
        })

    # Recent bar sequence via Viterbi
    try:
        df_recent = await _fetch_recent(instrument, timeframe, recent_bars)
        from services.feature_extractor import extract_features as _extract
        matrix = _extract(df_recent)
        clf    = get_classifier()
        seq_result = clf.get_state_sequence(matrix, instrument, timeframe, min(recent_bars, len(df_recent)))
        recent_sequence = [
            {
                "bar_index": i,
                "time":      df_recent["time"].iloc[-(len(seq_result.sequence) - i)].isoformat()
                             if hasattr(df_recent["time"].iloc[0], "isoformat")
                             else str(df_recent["time"].iloc[-(len(seq_result.sequence) - i)]),
                "state":     int(seq_result.sequence[i]),
                "label":     labels.get(str(seq_result.sequence[i]), f"S{seq_result.sequence[i]}"),
            }
            for i in range(len(seq_result.sequence))
        ]
    except Exception as e:
        logger.warning("[state-profile] recent sequence failed: %s", e)
        recent_sequence = []

    return {
        "instrument":      instrument,
        "timeframe":       timeframe,
        "model_version":   row["version"],
        "n_states":        n_states,
        "states":          states_profile,
        "recent_sequence": recent_sequence,
    }


# ─── Classify ─────────────────────────────────────────────────────────────────

@router.post("/classify", response_model=HmmClassifyResponse)
async def classify(req: HmmClassifyRequest) -> HmmClassifyResponse:
    """Classify the current market state from recent OHLC."""
    await _ensure_model_loaded(req.instrument, req.timeframe)
    df     = await _fetch_recent(req.instrument, req.timeframe, req.lookback)
    matrix = extract_features(df)
    result = get_classifier().classify_current_state(matrix, req.instrument, req.timeframe)
    return HmmClassifyResponse(
        state=result.state,
        state_label=result.state_label,
        model_version=result.model_version,
    )


# ─── Sequence ─────────────────────────────────────────────────────────────────

@router.post("/sequence", response_model=HmmSequenceResponse)
async def sequence(req: HmmSequenceRequest) -> HmmSequenceResponse:
    """Decode state sequence via Viterbi algorithm."""
    await _ensure_model_loaded(req.instrument, req.timeframe)
    lookback = max(req.length * 4, 50)
    df       = await _fetch_recent(req.instrument, req.timeframe, lookback)
    matrix   = extract_features(df)
    result   = get_classifier().get_state_sequence(matrix, req.instrument, req.timeframe, req.length)
    return HmmSequenceResponse(
        sequence=result.sequence,
        repr=result.repr,
        log_prob=result.log_prob,
        model_version=result.model_version,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _ensure_model_loaded(instrument: str, timeframe: str) -> None:
    """Load model from DB into classifier cache if not already loaded."""
    clf = get_classifier()
    if clf.is_loaded(instrument, timeframe):
        return

    try:
        import asyncpg  # type: ignore
        import os, json

        conn_str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:P%40ss1234@localhost:5432/tradeos"
        )
        conn = await asyncpg.connect(conn_str)
        row = await conn.fetchrow(
            """SELECT model_pickle, scaler_pickle, version, state_labels
               FROM hmm_models
               WHERE instrument=$1 AND timeframe=$2 AND is_active=TRUE
               ORDER BY created_at DESC LIMIT 1""",
            instrument.upper(), timeframe.upper()
        )
        await conn.close()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No trained HMM for {instrument}/{timeframe}. Run /python/hmm/train first."
            )

        model  = pickle.loads(bytes(row["model_pickle"]))
        scaler = pickle.loads(bytes(row["scaler_pickle"]))
        labels = json.loads(row["state_labels"] or "{}")
        clf.load_model(instrument, timeframe, model, scaler, row["version"], labels)

    except ImportError:
        raise HTTPException(status_code=500, detail="asyncpg not available")


async def _fetch_historical(instrument: str, timeframe: str, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Fetch historical OHLC bars for a date range.
    Priority: DB cache → MT5 → yfinance (fallback).
    Cache is populated on first MT5 fetch and reused for all subsequent calls.
    """
    from services.ohlc_store import load_ohlc, save_ohlc

    # ── 1. Try DB cache first (fastest — local) ───────────────────────────────
    cached = await load_ohlc(instrument, timeframe, date_from, date_to)
    if cached is not None and len(cached) >= 10:
        return cached

    # ── 2. Try MT5 ────────────────────────────────────────────────────────────
    try:
        df = _fetch_historical_mt5(instrument, timeframe, date_from, date_to)
        if df is not None and len(df) >= 10:
            logger.info(f"[_fetch_historical] MT5: {len(df)} bars {instrument} {timeframe}")
            await save_ohlc(df, instrument, timeframe)   # cache for future calls
            return df
    except Exception as e:
        logger.warning(f"[_fetch_historical] MT5 failed ({e}), falling back to yfinance")

    # ── 2. yfinance fallback ──────────────────────────────────────────────────
    import yfinance as yf  # type: ignore
    from routers.ohlc import _fetch_from_yfinance

    yf_symbol_map = {
        "XAUUSD": "GC=F", "XAUUSDM": "GC=F", "NAS100": "^IXIC",
        "EURUSD": "EURUSD=X", "EURUSDM": "EURUSD=X",
        "GBPUSD": "GBPUSD=X", "GBPUSDM": "GBPUSD=X",
        "USDJPY": "JPY=X",   "USDJPYM": "JPY=X",
    }
    tf_map = {
        "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
        "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1wk",
    }
    symbol   = yf_symbol_map.get(instrument.upper(), instrument)
    interval = tf_map.get(timeframe.upper(), "1d")

    try:
        ticker = yf.Ticker(symbol)
        df_raw = ticker.history(start=date_from, end=date_to, interval=interval)
        if not df_raw.empty:
            df_raw = df_raw.reset_index()
            df_raw.columns = [str(c).strip() for c in df_raw.columns]
            time_col = "Datetime" if "Datetime" in df_raw.columns else "Date"
            df_raw[time_col] = pd.to_datetime(df_raw[time_col]).dt.tz_convert(None)
            df = df_raw.rename(columns={
                time_col: "time", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume"
            })[["time", "open", "high", "low", "close", "volume"]]
            return df.reset_index(drop=True)
    except Exception as e:
        logger.warning(f"[_fetch_historical] yfinance date-range failed ({e}), using tail fallback")

    # Last resort: tail N bars filtered by date
    bars_list = await _fetch_from_yfinance(instrument, timeframe, 5000)
    df = pd.DataFrame([b.model_dump() for b in bars_list])
    df["time"] = pd.to_datetime(df["time"])
    mask = (df["time"] >= pd.Timestamp(date_from)) & (df["time"] <= pd.Timestamp(date_to))
    return df[mask].reset_index(drop=True)


def _fetch_historical_mt5(instrument: str, timeframe: str, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Sync helper — fetch date-range bars from MT5 using copy_rates_range().
    Does NOT shutdown MT5 — preserves any existing connection.
    Raises RuntimeError if MT5 unavailable or returns no data.
    """
    import os
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError:
        raise RuntimeError("MetaTrader5 package not available")

    from datetime import datetime, timezone

    TF_MAP = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 16385, "H4": 16388, "H8": 16392,
        "D1": 16408, "W1": 32769, "MN1": 49153,
    }
    tf_int = TF_MAP.get(timeframe.upper())
    if tf_int is None:
        raise ValueError(f"Unknown timeframe: {timeframe}")

    # Connect only if not already connected
    if mt5.terminal_info() is None:
        login    = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server   = os.getenv("MT5_SERVER", "")
        ok = mt5.initialize(login=login, password=password, server=server) \
             if (login and password and server) else mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

    # MT5 copy_rates_range requires naive datetime (no tzinfo) — internally UTC
    dt_from = datetime.fromisoformat(date_from).replace(tzinfo=None)
    dt_to   = datetime.fromisoformat(date_to).replace(tzinfo=None)

    # Symbol harus di-select ke Market Watch sebelum bisa di-fetch
    mt5.symbol_select(instrument, True)

    rates = mt5.copy_rates_range(instrument, tf_int, dt_from, dt_to)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"MT5 no data for {instrument} {timeframe} {date_from}–{date_to}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    vol_col = "real_volume" if "real_volume" in df.columns else "volume"
    df["volume"] = df[vol_col].astype(float)
    return df[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


async def _fetch_recent(instrument: str, timeframe: str, bars: int) -> pd.DataFrame:
    from routers.ohlc import _fetch_from_mt5, _fetch_from_yfinance
    try:
        bl = await _fetch_from_mt5(instrument, timeframe, bars)
    except Exception:
        bl = await _fetch_from_yfinance(instrument, timeframe, bars)
    return pd.DataFrame([b.model_dump() for b in bl])
