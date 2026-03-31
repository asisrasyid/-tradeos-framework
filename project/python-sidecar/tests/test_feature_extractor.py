"""
Unit tests for feature_extractor.py
Run: python -m pytest tests/test_feature_extractor.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest
from services.feature_extractor import extract_features, extract_single, FeatureVector


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_ohlc(n: int = 200, seed: int = 42, trend: float = 0.0) -> pd.DataFrame:
    """Generate synthetic OHLC data."""
    rng = np.random.default_rng(seed)
    close = 2000.0 + trend * np.arange(n) + rng.normal(0, 5, n).cumsum()
    spread = rng.uniform(1, 15, n)
    high   = close + spread * rng.uniform(0.3, 1.0, n)
    low    = close - spread * rng.uniform(0.3, 1.0, n)
    open_  = close + rng.normal(0, 2, n)
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.uniform(1000, 5000, n),
    })


# ─── Shape tests ──────────────────────────────────────────────────────────────

def test_output_shape_small():
    df = make_ohlc(50)
    matrix = extract_features(df)
    assert matrix.shape == (50, 6), f"Expected (50,6), got {matrix.shape}"


def test_output_shape_standard():
    df = make_ohlc(200)
    matrix = extract_features(df)
    assert matrix.shape == (200, 6), f"Expected (200,6), got {matrix.shape}"


def test_output_shape_minimal():
    df = make_ohlc(10)
    matrix = extract_features(df)
    assert matrix.shape == (10, 6)


# ─── Feature range tests ──────────────────────────────────────────────────────

def test_f0_atr_percentile_range():
    """f0 must be in [0.0, 1.0]"""
    df = make_ohlc(200)
    matrix = extract_features(df)
    f0 = matrix[:, 0]
    assert np.all(f0 >= 0.0), f"f0 min = {f0.min():.4f}"
    assert np.all(f0 <= 1.0), f"f0 max = {f0.max():.4f}"


def test_f3_body_dominance_range():
    """f3 must be in [0.0, 1.0]"""
    df = make_ohlc(200)
    matrix = extract_features(df)
    f3 = matrix[:, 3]
    assert np.all(f3 >= 0.0), f"f3 min = {f3.min():.4f}"
    assert np.all(f3 <= 1.0), f"f3 max = {f3.max():.4f}"


def test_f5_liquidity_proximity_range():
    """f5 must be in [0.0, 1.0]"""
    df = make_ohlc(200)
    matrix = extract_features(df)
    f5 = matrix[:, 5]
    assert np.all(f5 >= 0.0), f"f5 min = {f5.min():.4f}"
    assert np.all(f5 <= 1.0), f"f5 max = {f5.max():.4f}"


def test_f1_momentum_clipped():
    """f1 momentum z-score should be clipped to [-5, 5]"""
    df = make_ohlc(200)
    matrix = extract_features(df)
    f1 = matrix[:, 1]
    assert np.all(f1 >= -5.0), f"f1 min = {f1.min():.4f}"
    assert np.all(f1 <= 5.0),  f"f1 max = {f1.max():.4f}"


# ─── Directionality tests ─────────────────────────────────────────────────────

def test_f1_positive_in_uptrend():
    """In a strong uptrend, mean f1 (momentum) should be > 0."""
    df = make_ohlc(200, trend=1.0)  # strong uptrend
    matrix = extract_features(df)
    mean_f1 = matrix[50:, 1].mean()  # skip warmup
    assert mean_f1 > 0, f"Expected positive momentum in uptrend, got {mean_f1:.4f}"


def test_f1_negative_in_downtrend():
    """In a strong downtrend, mean f1 should be < 0."""
    df = make_ohlc(200, trend=-1.0)
    matrix = extract_features(df)
    mean_f1 = matrix[50:, 1].mean()
    assert mean_f1 < 0, f"Expected negative momentum in downtrend, got {mean_f1:.4f}"


def test_f4_positive_in_uptrend():
    """In a strong uptrend, mean f4 (HTF slope) should be > 0."""
    df = make_ohlc(200, trend=2.0)
    matrix = extract_features(df)
    mean_f4 = matrix[50:, 4].mean()
    assert mean_f4 > 0, f"Expected positive slope in uptrend, got {mean_f4:.4f}"


# ─── Scale invariance test ────────────────────────────────────────────────────

def test_scale_invariance():
    """
    Features should be nearly identical for XAUUSD (price ~2000) vs
    a hypothetical instrument scaled by 10x, if price dynamics are identical.
    """
    rng = np.random.default_rng(99)
    n = 100
    close = rng.normal(0, 5, n).cumsum() + 2000.0
    spread = rng.uniform(1, 10, n)
    df_base = pd.DataFrame({
        "open":  close + rng.normal(0, 2, n),
        "high":  close + spread,
        "low":   close - spread,
        "close": close,
    })
    df_scaled = df_base * 10.0  # scale all prices 10x

    m1 = extract_features(df_base)
    m2 = extract_features(df_scaled)

    # f0, f3, f1 should be identical (scale-invariant)
    for fi in [0, 3]:  # f0 and f3 are most strictly scale-invariant
        np.testing.assert_allclose(m1[:, fi], m2[:, fi], rtol=1e-4,
            err_msg=f"f{fi} not scale-invariant")


# ─── No NaN / Inf ─────────────────────────────────────────────────────────────

def test_no_nan_or_inf():
    df = make_ohlc(200)
    matrix = extract_features(df)
    assert not np.any(np.isnan(matrix)), "NaN values in feature matrix"
    assert not np.any(np.isinf(matrix)), "Inf values in feature matrix"


# ─── extract_single ───────────────────────────────────────────────────────────

def test_extract_single_returns_feature_vector():
    df = make_ohlc(100)
    fv = extract_single(df)
    assert isinstance(fv, FeatureVector)
    arr = fv.to_array()
    assert arr.shape == (6,)
    assert not np.any(np.isnan(arr))


def test_extract_single_matches_matrix_last_row():
    df = make_ohlc(100)
    matrix = extract_features(df)
    fv     = extract_single(df)
    np.testing.assert_allclose(fv.to_array(), matrix[-1], rtol=1e-8)


# ─── Doji edge case ───────────────────────────────────────────────────────────

def test_doji_body_dominance_is_zero():
    """When open == close, body dominance (f3) = 0."""
    df = make_ohlc(100)
    df.at[df.index[-1], "open"]  = df["close"].iloc[-1]
    fv = extract_single(df)
    assert fv.f3_body_dominance < 0.01, f"Doji f3={fv.f3_body_dominance}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
