"""C-Code evaluation router — computes SMC conditions via smartmoneyconcepts + pandas-ta."""

import logging
import numpy as np
import pandas as pd
from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from models.schemas import CCodCalculateRequest, CCodCalculateResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/calculate", response_model=CCodCalculateResponse)
async def calculate_ccodes(req: CCodCalculateRequest) -> CCodCalculateResponse:
    """
    Evaluate all C-Codes for given OHLC data.
    Returns dict of code → value (0/1 or float).
    """
    try:
        df = pd.read_json(req.ohlc_json)
        df.columns = [c.lower() for c in df.columns]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ohlc_json: {e}")

    codes: dict = {}

    # ── SMC conditions ────────────────────────────────────────────────────
    try:
        import smartmoneyconcepts.smc as smc  # type: ignore

        # Ensure volume column (required by ob)
        if "volume" not in df.columns:
            df = df.copy()
            df["volume"] = 1.0

        swings = smc.swing_highs_lows(df, swing_length=20)

        # Break of Structure
        bos = smc.bos_choch(df, swings, close_break=True)
        bos_val   = bos["BOS"].dropna().iloc[-1]   if "BOS"   in bos.columns and bos["BOS"].notna().any()   else 0
        choch_val = bos["CHOCH"].dropna().iloc[-1] if "CHOCH" in bos.columns and bos["CHOCH"].notna().any() else 0
        codes["BOS_BULLISH"]   = int(bos_val   == 1)
        codes["BOS_BEARISH"]   = int(bos_val   == -1)
        codes["CHOCH_BULLISH"] = int(choch_val == 1)
        codes["CHOCH_BEARISH"] = int(choch_val == -1)

        # Order Blocks
        ob = smc.ob(df, swings)
        active_obs = ob.dropna(subset=["OB"])
        if not active_obs.empty:
            last_ob_row = active_obs.iloc[-1]
            last_ob     = last_ob_row["OB"]
            close_price = float(df["close"].iloc[-1])
            in_zone     = float(last_ob_row["Bottom"]) <= close_price <= float(last_ob_row["Top"])
            codes["OB_BULLISH_ACTIVE"] = int(last_ob == 1)
            codes["OB_BEARISH_ACTIVE"] = int(last_ob == -1)
            codes["PRICE_IN_OB_BULL"]  = int(in_zone and last_ob == 1)
            codes["PRICE_IN_OB_BEAR"]  = int(in_zone and last_ob == -1)
        else:
            for k in ("OB_BULLISH_ACTIVE", "OB_BEARISH_ACTIVE", "PRICE_IN_OB_BULL", "PRICE_IN_OB_BEAR"):
                codes[k] = 0

        # FVG
        fvg = smc.fvg(df)
        last_fvg = fvg["FVG"].dropna().iloc[-1] if "FVG" in fvg.columns and fvg["FVG"].notna().any() else 0
        codes["FVG_BULLISH"] = int(last_fvg == 1)
        codes["FVG_BEARISH"] = int(last_fvg == -1)

        # Liquidity (EQH/EQL)
        liq = smc.liquidity(df, swings)
        swept    = liq["Swept"].dropna().iloc[-1]    if "Swept"     in liq.columns and liq["Swept"].notna().any()     else 0
        liq_type = liq["Liquidity"].dropna().iloc[-1] if "Liquidity" in liq.columns and liq["Liquidity"].notna().any() else 0
        codes["EQH_SWEPT"] = int(swept == 1 and liq_type == 1)
        codes["EQL_SWEPT"] = int(swept == 1 and liq_type == -1)

        # Sessions — derive from time column
        if "time" in df.columns:
            last_time = pd.to_datetime(df["time"].iloc[-1])
            hour = last_time.hour
            codes["SESSION_LONDON"]         = int(8  <= hour < 17)
            codes["SESSION_NY"]             = int(13 <= hour < 22)
            codes["SESSION_LONDON_OPEN_KZ"] = int(8  <= hour < 10)
            codes["SESSION_NY_KZ"]          = int(13 <= hour < 15)
        else:
            for k in ("SESSION_LONDON", "SESSION_NY", "SESSION_LONDON_OPEN_KZ", "SESSION_NY_KZ"):
                codes[k] = 0

    except Exception as e:
        logger.warning(f"smartmoneyconcepts failed: {e}")
        for k in ("BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH",
                   "OB_BULLISH_ACTIVE", "OB_BEARISH_ACTIVE", "PRICE_IN_OB_BULL", "PRICE_IN_OB_BEAR",
                   "FVG_BULLISH", "FVG_BEARISH", "EQH_SWEPT", "EQL_SWEPT",
                   "SESSION_LONDON", "SESSION_NY", "SESSION_LONDON_OPEN_KZ", "SESSION_NY_KZ"):
            codes.setdefault(k, 0)

    # ── ta conditions ─────────────────────────────────────────────────────
    try:
        from ta.trend import ADXIndicator, EMAIndicator  # type: ignore
        from ta.momentum import RSIIndicator  # type: ignore
        from ta.volatility import AverageTrueRange  # type: ignore

        adx_val = float(ADXIndicator(df["high"], df["low"], df["close"], window=14, fillna=False).adx().iloc[-1])
        codes["MARKET_TRENDING"] = float(np.clip(adx_val / 100.0, 0.0, 1.0))

        ema200 = EMAIndicator(df["close"], window=200, fillna=False).ema_indicator()
        codes["ABOVE_200EMA"] = int(df["close"].iloc[-1] > ema200.iloc[-1]) if not ema200.isna().iloc[-1] else 0

        rsi_val = float(RSIIndicator(df["close"], window=14, fillna=False).rsi().iloc[-1])
        codes["CANDLE_MOMENTUM_BULL"] = float(max(0.0, (rsi_val - 50.0) / 50.0))
        codes["CANDLE_MOMENTUM_BEAR"] = float(max(0.0, (50.0 - rsi_val) / 50.0))

        atr_series = AverageTrueRange(df["high"], df["low"], df["close"], window=14, fillna=False).average_true_range()
        pct = atr_series.rank(pct=True).iloc[-1]
        codes["ATR_NORMAL"] = int(0.2 <= pct <= 0.8)

        if "volume" in df.columns:
            vol_mean = df["volume"].rolling(20).mean().iloc[-1]
            codes["HIGH_VOLUME"] = int(df["volume"].iloc[-1] > vol_mean * 1.5)
        else:
            codes["HIGH_VOLUME"] = 0

    except Exception as e:
        logger.warning(f"ta failed: {e}")
        for k in ("MARKET_TRENDING", "ABOVE_200EMA", "CANDLE_MOMENTUM_BULL",
                   "CANDLE_MOMENTUM_BEAR", "ATR_NORMAL", "HIGH_VOLUME"):
            codes.setdefault(k, 0)

    # ── HMM state C-codes (injected by C# caller) ────────────────────────
    hmm_state  = req.hmm_state
    hmm_h4     = req.hmm_h4_state
    codes["HMM_STATE_CURRENT"]   = hmm_state if hmm_state is not None else -1
    codes["HTF_BIAS_BULLISH"]    = int(hmm_h4 == 0) if hmm_h4 is not None else 0
    codes["HTF_BIAS_BEARISH"]    = int(hmm_h4 == 1) if hmm_h4 is not None else 0
    codes["HMM_STATE_IS_RETEST"]   = int(hmm_state == 4) if hmm_state is not None else 0
    codes["HMM_STATE_IS_POST_BOS"] = int(hmm_state == 3) if hmm_state is not None else 0
    codes["HMM_STATE_IS_RANGING"]  = int(hmm_state == 2) if hmm_state is not None else 0

    return CCodCalculateResponse(
        instrument=req.instrument,
        timeframe=req.timeframe,
        codes=codes,
    )


# ─── Evaluate (sp_evaluate_theory via DB) ────────────────────────────────────

class SpEvaluateRequest(BaseModel):
    theory_id: str
    instrument: str
    timeframe: str
    ccode_snapshot: dict[str, Any]
    seq_repr: str = "S0"


class SpEvaluateResponse(BaseModel):
    composite_score: int
    threshold_met: bool
    p_win: float
    signal_decision: str


@router.post("/evaluate", response_model=SpEvaluateResponse)
async def evaluate_theory(req: SpEvaluateRequest) -> SpEvaluateResponse:
    """
    Call sp_evaluate_theory stored procedure in PostgreSQL.
    Returns composite_score, threshold_met, signal_decision.
    """
    try:
        import asyncpg  # type: ignore
        import os, json, uuid

        conn_str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:P%40ss1234@localhost:5432/tradeos"
        )
        conn = await asyncpg.connect(conn_str)

        try:
            theory_id = uuid.UUID(req.theory_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid theory_id: {req.theory_id}")

        # Call sp_evaluate_theory(p_theory_id, p_instrument, p_timeframe, p_ccode_snapshot)
        row = await conn.fetchrow(
            "SELECT * FROM sp_evaluate_theory($1, $2, $3, $4::jsonb)",
            theory_id,
            req.instrument.upper(),
            req.timeframe.upper(),
            json.dumps(req.ccode_snapshot),
        )
        await conn.close()

        if row is None:
            raise HTTPException(status_code=500, detail="sp_evaluate_theory returned no result")

        composite_score = int(row.get("composite_score", 0) or 0)
        threshold_met   = bool(row.get("threshold_met", False))
        signal_decision = str(row.get("signal_decision", "SKIP") or "SKIP")

        return SpEvaluateResponse(
            composite_score=composite_score,
            threshold_met=threshold_met,
            p_win=0.5,       # Bayesian P(WIN) is computed in C# — pass-through default
            signal_decision=signal_decision,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[/ccode/evaluate] DB error: {e}")
        raise HTTPException(status_code=500, detail=f"sp_evaluate_theory failed: {e}")

