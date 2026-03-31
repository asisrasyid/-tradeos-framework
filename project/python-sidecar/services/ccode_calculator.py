"""
C-Code Calculator — TradeOS v5.1
Evaluates all standard C-Codes from OHLC data.
Returns dict[str, float] where values are in [0.0 – 1.0] (or exact 0/1 for binary codes).

Libraries:
  - smartmoneyconcepts  → BOS, CHoCH, OB, FVG, liquidity, sessions
  - pandas-ta           → ATR, ADX, EMA, RSI, momentum
  - HMM state codes injected by caller (C# backend passes current HMM state)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────

def calculate_all_ccodes(
    df: pd.DataFrame,
    instrument: str,
    timeframe: str,
    hmm_state: Optional[int] = None,        # current TF HMM state (0-5)
    hmm_h4_state: Optional[int] = None,     # H4 HMM state for HTF bias
) -> dict[str, float]:
    """
    Compute all C-Codes for the LATEST candle in `df`.

    Args:
        df:            OHLC DataFrame (≥ 50 bars recommended). Columns lowercase.
        instrument:    e.g. "XAUUSD"
        timeframe:     e.g. "H1"
        hmm_state:     Current HMM state (0-5) for this timeframe. None if not yet trained.
        hmm_h4_state:  HMM state from H4 chart for HTF bias. None if not available.

    Returns:
        dict mapping C-Code string → float score (mostly 0.0 or 1.0, some continuous).
    """
    df = _normalize(df)
    codes: dict[str, float] = {}

    # ── 1. SMC conditions ────────────────────────────────────────────────────
    _compute_smc(df, codes)

    # ── 2. pandas-ta conditions ──────────────────────────────────────────────
    _compute_ta(df, codes)

    # ── 3. HMM state codes (injected from classifier) ────────────────────────
    _inject_hmm_codes(codes, hmm_state, hmm_h4_state)

    # ── 4. Ensure all known codes exist (default 0.0 if not computed) ────────
    for code in _ALL_KNOWN_CODES:
        codes.setdefault(code, 0.0)

    return codes


# ─── SMC Conditions ──────────────────────────────────────────────────────────

def _compute_smc(df: pd.DataFrame, codes: dict[str, float]) -> None:
    """Compute BOS, CHoCH, OB, FVG, Liquidity, Sessions via smartmoneyconcepts."""
    try:
        import smartmoneyconcepts.smc as smc  # type: ignore

        # Ensure volume column exists (required by ob())
        if "volume" not in df.columns:
            df = df.copy()
            df["volume"] = 1.0

        # Pre-compute swing highs/lows (required by bos_choch, ob, liquidity)
        swings = smc.swing_highs_lows(df, swing_length=20)

        # BOS / CHoCH
        try:
            bos_df = smc.bos_choch(df, swings, close_break=True)
            # Use most recent non-null row
            bos_val   = bos_df["BOS"].dropna().iloc[-1]   if "BOS"   in bos_df.columns and bos_df["BOS"].notna().any()   else 0
            choch_val = bos_df["CHOCH"].dropna().iloc[-1] if "CHOCH" in bos_df.columns and bos_df["CHOCH"].notna().any() else 0
            codes["BOS_BULLISH"]   = 1.0 if bos_val   == 1  else 0.0
            codes["BOS_BEARISH"]   = 1.0 if bos_val   == -1 else 0.0
            codes["CHOCH_BULLISH"] = 1.0 if choch_val == 1  else 0.0
            codes["CHOCH_BEARISH"] = 1.0 if choch_val == -1 else 0.0
        except Exception as e:
            logger.debug(f"BOS/CHOCH failed: {e}")
            for k in ("BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH"):
                codes[k] = 0.0

        # Order Blocks
        try:
            ob_df = smc.ob(df, swings)
            # Most recent active OB row
            active_obs = ob_df.dropna(subset=["OB"])
            if not active_obs.empty:
                last_ob_row = active_obs.iloc[-1]
                last_ob     = last_ob_row["OB"]
                codes["OB_BULLISH_ACTIVE"] = 1.0 if last_ob == 1  else 0.0
                codes["OB_BEARISH_ACTIVE"] = 1.0 if last_ob == -1 else 0.0
                close_price = float(df["close"].iloc[-1])
                ob_top      = float(last_ob_row["Top"])
                ob_bottom   = float(last_ob_row["Bottom"])
                in_zone     = ob_bottom <= close_price <= ob_top
                codes["PRICE_IN_OB_BULL"] = 1.0 if (in_zone and last_ob == 1)  else 0.0
                codes["PRICE_IN_OB_BEAR"] = 1.0 if (in_zone and last_ob == -1) else 0.0
            else:
                for k in ("OB_BULLISH_ACTIVE", "OB_BEARISH_ACTIVE", "PRICE_IN_OB_BULL", "PRICE_IN_OB_BEAR"):
                    codes[k] = 0.0
        except Exception as e:
            logger.debug(f"OB failed: {e}")
            for k in ("OB_BULLISH_ACTIVE", "OB_BEARISH_ACTIVE", "PRICE_IN_OB_BULL", "PRICE_IN_OB_BEAR"):
                codes[k] = 0.0

        # FVG
        try:
            fvg_df = smc.fvg(df)
            last_fvg = fvg_df["FVG"].dropna().iloc[-1] if "FVG" in fvg_df.columns and fvg_df["FVG"].notna().any() else 0
            codes["FVG_BULLISH"] = 1.0 if last_fvg == 1  else 0.0
            codes["FVG_BEARISH"] = 1.0 if last_fvg == -1 else 0.0
        except Exception as e:
            logger.debug(f"FVG failed: {e}")
            codes["FVG_BULLISH"] = 0.0
            codes["FVG_BEARISH"] = 0.0

        # Liquidity (EQH/EQL)
        try:
            liq_df = smc.liquidity(df, swings)
            swept    = liq_df["Swept"].dropna().iloc[-1]    if "Swept"     in liq_df.columns and liq_df["Swept"].notna().any()     else 0
            liq_type = liq_df["Liquidity"].dropna().iloc[-1] if "Liquidity" in liq_df.columns and liq_df["Liquidity"].notna().any() else 0
            codes["EQH_SWEPT"] = 1.0 if (swept == 1 and liq_type == 1)  else 0.0
            codes["EQL_SWEPT"] = 1.0 if (swept == 1 and liq_type == -1) else 0.0
        except Exception as e:
            logger.debug(f"Liquidity failed: {e}")
            codes["EQH_SWEPT"] = 0.0
            codes["EQL_SWEPT"] = 0.0

        # Sessions — derive from time column if available
        try:
            if "time" in df.columns:
                last_time = pd.to_datetime(df["time"].iloc[-1])
                hour = last_time.hour
                codes["SESSION_LONDON"]         = 1.0 if 8  <= hour < 17 else 0.0
                codes["SESSION_NY"]             = 1.0 if 13 <= hour < 22 else 0.0
                codes["SESSION_LONDON_OPEN_KZ"] = 1.0 if 8  <= hour < 10 else 0.0
                codes["SESSION_NY_KZ"]          = 1.0 if 13 <= hour < 15 else 0.0
            else:
                for k in ("SESSION_LONDON", "SESSION_NY", "SESSION_LONDON_OPEN_KZ", "SESSION_NY_KZ"):
                    codes[k] = 0.0
        except Exception as e:
            logger.debug(f"Sessions failed: {e}")
            for k in ("SESSION_LONDON", "SESSION_NY", "SESSION_LONDON_OPEN_KZ", "SESSION_NY_KZ"):
                codes[k] = 0.0

    except (ImportError, ModuleNotFoundError):
        logger.warning("smartmoneyconcepts not installed — all SMC codes = 0")
        for k in _SMC_CODES:
            codes[k] = 0.0


# ─── pandas-ta Conditions ────────────────────────────────────────────────────

def _compute_ta(df: pd.DataFrame, codes: dict[str, float]) -> None:
    """Compute trend, momentum, volume codes via 'ta' library."""
    try:
        import ta as ta_lib  # type: ignore

        # ADX — market trending score (0.0 – 1.0)
        try:
            from ta.trend import ADXIndicator  # type: ignore
            adx_ind = ADXIndicator(df["high"], df["low"], df["close"], window=14, fillna=False)
            adx_val = float(adx_ind.adx().iloc[-1])
            codes["MARKET_TRENDING"] = float(np.clip(adx_val / 100.0, 0.0, 1.0))
        except Exception as e:
            logger.debug(f"ADX failed: {e}")
            codes["MARKET_TRENDING"] = 0.0

        # 200 EMA
        try:
            from ta.trend import EMAIndicator  # type: ignore
            ema200 = EMAIndicator(df["close"], window=200, fillna=False).ema_indicator()
            if not ema200.isna().iloc[-1]:
                codes["ABOVE_200EMA"] = 1.0 if df["close"].iloc[-1] > ema200.iloc[-1] else 0.0
            else:
                codes["ABOVE_200EMA"] = 0.0
        except Exception as e:
            logger.debug(f"EMA200 failed: {e}")
            codes["ABOVE_200EMA"] = 0.0

        # RSI-based momentum
        try:
            from ta.momentum import RSIIndicator  # type: ignore
            rsi_val = float(RSIIndicator(df["close"], window=14, fillna=False).rsi().iloc[-1])
            codes["CANDLE_MOMENTUM_BULL"] = float(np.clip((rsi_val - 50.0) / 50.0, 0.0, 1.0))
            codes["CANDLE_MOMENTUM_BEAR"] = float(np.clip((50.0 - rsi_val) / 50.0, 0.0, 1.0))
        except Exception as e:
            logger.debug(f"RSI failed: {e}")
            codes["CANDLE_MOMENTUM_BULL"] = 0.0
            codes["CANDLE_MOMENTUM_BEAR"] = 0.0

        # ATR normal (percentile 20–80 → normal volatility)
        try:
            from ta.volatility import AverageTrueRange  # type: ignore
            atr_series = AverageTrueRange(df["high"], df["low"], df["close"], window=14, fillna=False).average_true_range()
            pct_rank = atr_series.rank(pct=True).iloc[-1]
            codes["ATR_NORMAL"] = 1.0 if 0.2 <= pct_rank <= 0.8 else 0.0
        except Exception as e:
            logger.debug(f"ATR normal failed: {e}")
            codes["ATR_NORMAL"] = 0.0

        # Volume (if present)
        try:
            if "volume" in df.columns and df["volume"].sum() > 0:
                vol_ma = df["volume"].rolling(20, min_periods=5).mean().iloc[-1]
                vol_cur = df["volume"].iloc[-1]
                codes["HIGH_VOLUME"] = 1.0 if vol_cur > vol_ma * 1.5 else 0.0
            else:
                codes["HIGH_VOLUME"] = 0.0
        except Exception:
            codes["HIGH_VOLUME"] = 0.0

    except ImportError:
        logger.warning("ta not installed — all TA codes = 0")
        for k in _TA_CODES:
            codes[k] = 0.0


# ─── HMM State Code Injection ────────────────────────────────────────────────

def _inject_hmm_codes(
    codes: dict[str, float],
    hmm_state: Optional[int],
    hmm_h4_state: Optional[int],
) -> None:
    """
    Inject HMM state-based C-Codes.
    These are computed by the C# caller after getting state from classifier,
    then passed here for scoring.

    State mapping (matches idea_framework.md):
      S0 = Trending Bull
      S1 = Trending Bear
      S2 = Ranging Low Vol
      S3 = Post-BOS Expansion
      S4 = Retest / Pullback
      S5 = High Volatility
    """
    codes["HMM_STATE_CURRENT"]     = float(hmm_state) if hmm_state is not None else -1.0
    codes["HTF_BIAS_BULLISH"]      = 1.0 if hmm_h4_state == 0 else 0.0
    codes["HTF_BIAS_BEARISH"]      = 1.0 if hmm_h4_state == 1 else 0.0
    codes["HMM_STATE_IS_RETEST"]   = 1.0 if hmm_state == 4 else 0.0
    codes["HMM_STATE_IS_POST_BOS"] = 1.0 if hmm_state == 3 else 0.0
    codes["HMM_STATE_IS_RANGING"]  = 1.0 if hmm_state == 2 else 0.0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    return df


# ─── Known code sets (for default=0.0 fill) ─────────────────────────────────

_SMC_CODES = [
    "BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH",
    "OB_BULLISH_ACTIVE", "OB_BEARISH_ACTIVE", "PRICE_IN_OB_BULL", "PRICE_IN_OB_BEAR",
    "FVG_BULLISH", "FVG_BEARISH", "EQH_SWEPT", "EQL_SWEPT",
    "SESSION_LONDON", "SESSION_NY", "SESSION_LONDON_OPEN_KZ", "SESSION_NY_KZ",
]

_TA_CODES = [
    "MARKET_TRENDING", "ABOVE_200EMA",
    "CANDLE_MOMENTUM_BULL", "CANDLE_MOMENTUM_BEAR",
    "ATR_NORMAL", "HIGH_VOLUME",
]

_HMM_CODES = [
    "HMM_STATE_CURRENT", "HTF_BIAS_BULLISH", "HTF_BIAS_BEARISH",
    "HMM_STATE_IS_RETEST", "HMM_STATE_IS_POST_BOS", "HMM_STATE_IS_RANGING",
]

_ALL_KNOWN_CODES = _SMC_CODES + _TA_CODES + _HMM_CODES
