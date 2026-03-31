"""Shared Pydantic schemas for TradeOS Python sidecar."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


# ─── OHLC ────────────────────────────────────────────────────────────────────

class OhlcFetchRequest(BaseModel):
    instrument: str          # e.g. "XAUUSD"
    timeframe: str           # e.g. "H1"
    bars: int = 500          # number of candles to fetch


class OhlcBar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class OhlcFetchResponse(BaseModel):
    instrument: str
    timeframe: str
    bars: list[OhlcBar]
    source: str              # "mt5" | "yfinance"


# ─── Feature Extraction ──────────────────────────────────────────────────────

class FeatureExtractRequest(BaseModel):
    ohlc_json: str           # JSON-serialized OHLC DataFrame
    instrument: str
    timeframe: str


class FeatureVector(BaseModel):
    f0_atr_percentile: float
    f1_momentum_zscore: float
    f2_swing_proximity: float
    f3_body_dominance: float
    f4_htf_trend_slope: float
    f5_liquidity_proximity: float


class FeatureExtractResponse(BaseModel):
    instrument: str
    timeframe: str
    features: list[FeatureVector]     # one per candle


# ─── HMM ─────────────────────────────────────────────────────────────────────

class HmmTrainRequest(BaseModel):
    instrument: str
    timeframe: str
    date_from: str
    date_to: str
    data_source: str = 'db'  # 'db' | 'mt5'


class HmmTrainResponse(BaseModel):
    version: str
    n_states: int
    bic_score: float
    n_samples: int
    model_pickle_b64: str    # base64 encoded pickle bytes
    scaler_pickle_b64: str
    state_labels: dict[str, str]


class HmmClassifyRequest(BaseModel):
    instrument: str
    timeframe: str
    lookback: int = 20


class HmmClassifyResponse(BaseModel):
    state: int
    state_label: str
    model_version: str


class HmmSequenceRequest(BaseModel):
    instrument: str
    timeframe: str
    length: int = 5


class HmmSequenceResponse(BaseModel):
    sequence: list[int]
    repr: str                # "S0S0S3S2S4"
    log_prob: float
    model_version: str


# ─── C-Code ──────────────────────────────────────────────────────────────────

class CCodCalculateRequest(BaseModel):
    ohlc_json: str
    instrument: str
    timeframe: str
    hmm_state: Optional[int] = None
    hmm_h4_state: Optional[int] = None


class CCodCalculateResponse(BaseModel):
    instrument: str
    timeframe: str
    codes: dict[str, Any]    # {"BOS_BULLISH": 1, "HTF_BIAS_BULLISH": 1, ...}


# ─── Backtest ────────────────────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    session_id: str          # UUID — used to write results back
    theory_snapshot: str     # JSON theory + factors
    instrument: str
    timeframe: str
    date_from: str
    date_to: str
    params: dict[str, Any] = {}


class BacktestTradeSchema(BaseModel):
    bar_index:   int
    time:        str
    direction:   str
    entry:       float
    sl:          float
    tp:          float
    sl_type:     str
    tp_type:     str
    atr:         float
    outcome:     str        # 'win' | 'loss' | 'breakeven'
    exit_bar:    int
    exit_price:  float
    pnl_pips:    float
    rr_achieved: float
    seq_repr:    str
    similarity:  float


class BacktestRunResponse(BaseModel):
    session_id: str
    total_signals: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    avg_rr: float
    total_pips: float
    equity_curve: list[float]
    state_distribution: dict[str, float]
    best_seq_repr: Optional[str]
    worst_seq_repr: Optional[str]
    trades: list[BacktestTradeSchema] = []
    sl_type: str = 'atr'
    sl_value: float = 1.0
    tp_type: str = 'atr'
    tp_value: float = 2.0
    max_hold_bars: int = 20


# ─── Pattern Mining ──────────────────────────────────────────────────────────

class PatternMineRequest(BaseModel):
    instrument: str
    timeframe: str
    min_win_rate: float = 0.6
    min_occurrences: int = 5


class MinedPattern(BaseModel):
    state_seq_repr: str
    win_rate: float
    occurrences: int
    avg_log_prob: float


class PatternMineResponse(BaseModel):
    instrument: str
    timeframe: str
    patterns: list[MinedPattern]
