"""
Feature Extractor — TradeOS v5.1
Computes 6 scale-invariant features per candle from OHLC data.
All features are normalized so they do not depend on absolute price level.

Feature vector shape per candle: (6,)
  f0 = atr_percentile         [0.0 – 1.0]
  f1 = price_momentum_zscore  (unbounded, typically -3..+3)
  f2 = swing_proximity_ratio  (signed, normalized per ATR)
  f3 = body_dominance         [0.0 – 1.0]
  f4 = htf_trend_slope        (signed, normalized per ATR)
  f5 = liquidity_proximity    [0.0 – 1.0]
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureVector:
    f0_atr_percentile: float
    f1_momentum_zscore: float
    f2_swing_proximity: float
    f3_body_dominance: float
    f4_htf_trend_slope: float
    f5_liquidity_proximity: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.f0_atr_percentile,
            self.f1_momentum_zscore,
            self.f2_swing_proximity,
            self.f3_body_dominance,
            self.f4_htf_trend_slope,
            self.f5_liquidity_proximity,
        ], dtype=np.float64)


# ─── Public API ───────────────────────────────────────────────────────────────

def extract_features(df: pd.DataFrame, htf_df: pd.DataFrame | None = None) -> np.ndarray:
    """
    Extract feature matrix from OHLC DataFrame.

    Args:
        df:      OHLC DataFrame with columns [open, high, low, close, volume?]
                 Minimum 30 rows recommended; first rows padded with 0 for insufficient history.
        htf_df:  Optional higher-timeframe OHLC (H4) for f4_htf_trend_slope.
                 If None, f4 is computed from df itself.

    Returns:
        np.ndarray of shape (N, 6) where N = len(df).
    """
    df = _normalize_columns(df)
    n = len(df)
    matrix = np.zeros((n, 6), dtype=np.float64)

    tr_series = _true_range(df)
    atr_series = tr_series.rolling(14, min_periods=1).mean()

    for i in range(n):
        window_start = max(0, i - 99)
        window = df.iloc[window_start : i + 1]
        candle = df.iloc[i]
        atr_val = float(atr_series.iloc[i])
        tr_window = tr_series.iloc[window_start : i + 1]

        f0 = _atr_percentile(tr_window, atr_val)
        f1 = _momentum_zscore(window)
        f2 = _swing_proximity(window, atr_val)
        f3 = _body_dominance(candle)
        f4 = _htf_trend_slope(window, atr_val) if htf_df is None else _htf_trend_slope_from_htf(htf_df, i, atr_val)
        f5 = _liquidity_proximity(window, atr_val)

        matrix[i] = [f0, f1, f2, f3, f4, f5]

    return matrix


def extract_single(df: pd.DataFrame) -> FeatureVector:
    """Extract feature vector for the LAST candle only. Efficient for live use."""
    matrix = extract_features(df)
    row = matrix[-1]
    return FeatureVector(
        f0_atr_percentile=float(row[0]),
        f1_momentum_zscore=float(row[1]),
        f2_swing_proximity=float(row[2]),
        f3_body_dominance=float(row[3]),
        f4_htf_trend_slope=float(row[4]),
        f5_liquidity_proximity=float(row[5]),
    )


# ─── Individual Feature Computations ─────────────────────────────────────────

def _atr_percentile(tr_window: pd.Series, atr_current: float) -> float:
    """
    f0: Where does the current ATR sit in its own 100-candle distribution?
    Formula: percentileofscore(last_100_ATR, current_ATR) / 100
    Returns [0.0 – 1.0]
    """
    if len(tr_window) < 2:
        return 0.0
    pct = stats.percentileofscore(tr_window.values, atr_current, kind="rank")
    return float(np.clip(pct / 100.0, 0.0, 1.0))


def _momentum_zscore(window: pd.DataFrame, n: int = 20) -> float:
    """
    f1: Z-score of current close vs distribution of last N closes.
    Formula: (close_t - mean(close_N)) / std(close_N)
    Unbounded; typical range -3..+3.
    """
    closes = window["close"].values
    if len(closes) < 3:
        return 0.0
    recent = closes[-min(n, len(closes)):]
    mean = recent.mean()
    std  = recent.std()
    if std < 1e-10:
        return 0.0
    return float(np.clip((closes[-1] - mean) / std, -5.0, 5.0))


def _swing_proximity(window: pd.DataFrame, atr: float, swing_lookback: int = 20) -> float:
    """
    f2: Signed distance to nearest swing high/low, normalized by ATR.
    Positive = price above nearest swing (trending up side).
    Negative = price below nearest swing (trending down side).
    Formula: (swing_level - close) / ATR  (signed)
    """
    if len(window) < 5 or atr < 1e-10:
        return 0.0
    lb = min(swing_lookback, len(window))
    recent = window.tail(lb)
    swing_high = recent["high"].max()
    swing_low  = recent["low"].min()
    close      = window["close"].iloc[-1]

    dist_to_high = (swing_high - close) / atr   # positive = below swing high
    dist_to_low  = (close - swing_low)  / atr   # positive = above swing low

    # Return smaller absolute distance (signed by direction)
    if abs(dist_to_high) < abs(dist_to_low):
        return float(np.clip(dist_to_high, -10.0, 10.0))
    else:
        return float(np.clip(-dist_to_low, -10.0, 10.0))


def _body_dominance(candle: pd.Series) -> float:
    """
    f3: Ratio of body to full range. 0 = doji, 1 = full body candle.
    Formula: |close - open| / (high - low + ε)
    Returns [0.0 – 1.0]
    """
    rng = float(candle["high"]) - float(candle["low"])
    if rng < 1e-10:
        return 0.0
    body = abs(float(candle["close"]) - float(candle["open"]))
    return float(np.clip(body / rng, 0.0, 1.0))


def _htf_trend_slope(window: pd.DataFrame, atr: float, n: int = 20) -> float:
    """
    f4: Linear regression slope of last N closes, normalized by ATR.
    Positive = uptrend, Negative = downtrend.
    """
    closes = window["close"].values
    if len(closes) < 3 or atr < 1e-10:
        return 0.0
    y = closes[-min(n, len(closes)):]
    x = np.arange(len(y), dtype=np.float64)
    slope = float(np.polyfit(x, y, 1)[0])
    return float(np.clip(slope / atr, -10.0, 10.0))


def _htf_trend_slope_from_htf(htf_df: pd.DataFrame, live_idx: int, atr: float, n: int = 20) -> float:
    """f4 variant using an actual H4 DataFrame when available."""
    if htf_df is None or len(htf_df) < 3:
        return 0.0
    htf_df = _normalize_columns(htf_df)
    atr_htf = float(_true_range(htf_df).rolling(14, min_periods=1).mean().iloc[-1])
    return _htf_trend_slope(htf_df, atr_htf if atr_htf > 1e-10 else atr, n)


def _liquidity_proximity(window: pd.DataFrame, atr: float, lookback: int = 20) -> float:
    """
    f5: How close is price to a liquidity pool (equal highs / equal lows)?
    Uses tolerance = 0.3 × ATR to detect "equal" highs/lows.
    Returns [0.0 – 1.0]. 1.0 = price sitting right on a liquidity level.
    """
    if len(window) < 5 or atr < 1e-10:
        return 0.0

    recent  = window.tail(min(lookback, len(window)))
    close   = float(window["close"].iloc[-1])
    tol     = atr * 0.3

    highs   = recent["high"].values
    lows    = recent["low"].values

    # Find liquidity levels (equal highs/lows within tolerance)
    levels: list[float] = []
    for h in highs:
        cluster = [x for x in highs if abs(x - h) <= tol]
        if len(cluster) >= 2:
            levels.append(float(np.mean(cluster)))
    for lo in lows:
        cluster = [x for x in lows if abs(x - lo) <= tol]
        if len(cluster) >= 2:
            levels.append(float(np.mean(cluster)))

    if not levels:
        return 0.0

    min_dist = min(abs(close - lvl) for lvl in levels)
    proximity = max(0.0, 1.0 - (min_dist / (atr * 2.0)))
    return float(np.clip(proximity, 0.0, 1.0))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _true_range(df: pd.DataFrame) -> pd.Series:
    high  = df["high"]
    low   = df["low"]
    prev  = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev).abs(),
        (low  - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.fillna(0.0)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure lowercase column names."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    return df
