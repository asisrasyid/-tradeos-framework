"""
Backtest Runner — TradeOS v5.2
Full candle-by-candle replay loop over historical OHLC data.

Pipeline per bar:
  1. Extract features from rolling window
  2. Classify HMM state sequence via Viterbi
  3. Compute pattern similarity (Opsi A: ordered subsequence match)
  4. If similarity >= threshold → record signal
  5. Simulate trade: entry @ next bar open, configurable SL/TP (ATR or fixed pips),
     max holding period in bars → outcome: win / loss / breakeven

Returns: BacktestRunResult with full stats + equity curve + per-trade log.

Config (via backtest_config dict):
  sl_type       : 'atr' | 'fixed'   (default: 'atr')
  sl_value      : float              (ATR multiplier OR fixed price distance)
  tp_type       : 'atr' | 'fixed'
  tp_value      : float
  max_hold_bars : int                (max bars before forced close at market)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from services.feature_extractor import extract_features
from services.hmm_classifier import get_classifier

logger = logging.getLogger(__name__)

# ── Defaults (used when backtest_config not provided) ─────────────────────────
LOOKBACK            = 50
DEFAULT_TP_ATR      = 2.0
DEFAULT_SL_ATR      = 1.0
DEFAULT_MAX_HOLD    = 20
DEFAULT_SIMILARITY  = 0.60
SEQ_WINDOW          = 10


# ─── Per-trade record ─────────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    bar_index:   int
    time:        str        # ISO datetime of signal bar
    direction:   str        # LONG | SHORT
    entry:       float      # entry price (close of signal bar)
    sl:          float      # stop-loss price
    tp:          float      # take-profit price
    sl_type:     str        # 'atr' | 'fixed'
    tp_type:     str
    atr:         float      # ATR at signal bar
    outcome:     str        # 'win' | 'loss' | 'breakeven'
    exit_bar:    int        # bar index where trade closed
    exit_price:  float      # price at exit
    pnl_pips:    float      # P&L in pips (positive = profit)
    rr_achieved: float      # actual RR relative to SL distance
    seq_repr:    str        # state sequence that triggered signal
    similarity:  float      # pattern similarity score


# ─── Summary dataclass ────────────────────────────────────────────────────────

@dataclass
class BacktestRunResult:
    total_signals:     int
    wins:              int
    losses:            int
    breakeven:         int
    win_rate:          float
    profit_factor:     float
    sharpe_ratio:      float
    sortino_ratio:     float
    max_drawdown:      float
    avg_rr:            float
    total_pips:        float
    equity_curve:      list[float]
    state_distribution: dict[str, float]
    best_seq_repr:     Optional[str]
    worst_seq_repr:    Optional[str]
    trades:            list[BacktestTrade] = field(default_factory=list)
    # config echo (so caller knows what was used)
    sl_type:           str   = 'atr'
    sl_value:          float = DEFAULT_SL_ATR
    tp_type:           str   = 'atr'
    tp_value:          float = DEFAULT_TP_ATR
    max_hold_bars:     int   = DEFAULT_MAX_HOLD


# ─── Public API ───────────────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    theory_config: dict,
    instrument: str,
    timeframe: str,
    backtest_config: dict | None = None,
) -> BacktestRunResult:
    """
    Run full historical replay backtest.

    Args:
        df:              OHLC DataFrame, sorted ascending. Must have ≥ 50 rows.
        theory_config:   Dict with keys: threshold, direction, pattern_states, similarity_threshold.
        instrument:      e.g. "XAUUSDm"
        timeframe:       e.g. "M15"
        backtest_config: Dict with SL/TP configuration. Falls back to defaults if None.
    """
    cfg = _resolve_config(backtest_config or {})
    df  = _normalize(df)

    direction      = str(theory_config.get("direction", "LONG")).upper()
    pattern_states = [int(s) for s in theory_config.get("pattern_states", [])]
    similarity_min = float(theory_config.get("similarity_threshold", DEFAULT_SIMILARITY))

    max_hold = cfg["max_hold_bars"]

    if len(df) < LOOKBACK + max_hold:
        logger.warning(f"[Backtest] Too few bars: {len(df)} — returning empty result")
        return _empty_result(cfg)

    if not pattern_states:
        logger.warning("[Backtest] No pattern_states in theory_config — returning empty result")
        return _empty_result(cfg)

    signals: list[dict] = []
    state_counts: dict[str, int] = {}
    clf = get_classifier()

    if not clf.is_loaded(instrument, timeframe):
        logger.warning(f"[Backtest] HMM not loaded for {instrument}/{timeframe}")
        return _empty_result(cfg)

    # ── Pre-compute features + Viterbi states for ALL bars (O(N)) ─────────────
    try:
        full_features = extract_features(df)
        clf_obj       = clf._cache[(instrument.upper(), timeframe.upper())]
        model         = clf_obj.model
        scaler        = clf_obj.scaler
        X_scaled      = scaler.transform(full_features)
        all_states    = model.predict(X_scaled).tolist()
        logger.info(f"[Backtest] Pre-computed {len(all_states)} states for {instrument}/{timeframe}")
    except Exception as e:
        logger.warning(f"[Backtest] Pre-compute failed ({e}) — falling back to per-bar")
        all_states = None

    # ── Per-bar replay ────────────────────────────────────────────────────────
    for i in range(LOOKBACK, len(df) - max_hold):

        if all_states is not None:
            recent_states = all_states[max(0, i - SEQ_WINDOW): i]
            cur_state     = all_states[i]
            seq_repr      = "".join(f"S{s}" for s in recent_states)
        else:
            window = df.iloc[i - LOOKBACK: i + 1].copy()
            try:
                feat_matrix   = extract_features(window)
                seq_result    = clf.get_state_sequence(
                    feat_matrix, instrument, timeframe, seq_length=SEQ_WINDOW
                )
                cur_result    = clf.classify_current_state(feat_matrix, instrument, timeframe)
                recent_states = list(seq_result.sequence)
                cur_state     = cur_result.state
                seq_repr      = seq_result.repr
            except Exception as e:
                logger.debug(f"[Backtest bar {i}] HMM classify failed: {e}")
                continue

        state_counts[f"S{cur_state}"] = state_counts.get(f"S{cur_state}", 0) + 1

        similarity = _pattern_similarity(recent_states, pattern_states)
        if similarity < similarity_min:
            continue

        row         = df.iloc[i]
        close_price = float(row["close"])
        atr         = _atr(df.iloc[i - LOOKBACK: i + 1])
        bar_time    = _bar_time(row)

        signals.append({
            "bar_index":  i,
            "time":       bar_time,
            "similarity": similarity,
            "direction":  direction,
            "close":      close_price,
            "atr":        atr,
            "seq_repr":   seq_repr,
        })

    # ── Simulate trades ───────────────────────────────────────────────────────
    wins = losses = breakeven = 0
    pnl_list:       list[float]      = []
    trades:         list[BacktestTrade] = []
    seq_win_counts: dict[str, int]   = {}
    seq_loss_counts: dict[str, int]  = {}

    for sig in signals:
        i     = sig["bar_index"]
        atr   = sig["atr"] if sig["atr"] > 0 else 1.0
        entry = sig["close"]   # entry at close of signal bar
        seq   = sig["seq_repr"]

        # ── SL/TP calculation ─────────────────────────────────────────────────
        sl_dist = _sl_distance(atr, cfg)
        tp_dist = _tp_distance(atr, cfg)

        if sig["direction"] == "LONG":
            sl = entry - sl_dist
            tp = entry + tp_dist
        else:
            sl = entry + sl_dist
            tp = entry - tp_dist

        # ── Forward scan for outcome ──────────────────────────────────────────
        outcome    = "breakeven"
        pnl_pips   = 0.0
        exit_bar   = i + max_hold   # default: forced close at max_hold
        exit_price = float(df.iloc[min(exit_bar, len(df) - 1)]["close"])

        future = df.iloc[i + 1: i + 1 + max_hold]
        for fi, (_, bar) in enumerate(future.iterrows()):
            if sig["direction"] == "LONG":
                if bar["high"] >= tp:
                    outcome    = "win"
                    pnl_pips   = tp_dist * _pip_factor(atr)
                    exit_bar   = i + 1 + fi
                    exit_price = tp
                    break
                if bar["low"] <= sl:
                    outcome    = "loss"
                    pnl_pips   = -sl_dist * _pip_factor(atr)
                    exit_bar   = i + 1 + fi
                    exit_price = sl
                    break
            else:
                if bar["low"] <= tp:
                    outcome    = "win"
                    pnl_pips   = tp_dist * _pip_factor(atr)
                    exit_bar   = i + 1 + fi
                    exit_price = tp
                    break
                if bar["high"] >= sl:
                    outcome    = "loss"
                    pnl_pips   = -sl_dist * _pip_factor(atr)
                    exit_bar   = i + 1 + fi
                    exit_price = sl
                    break

        # max-hold forced close: pnl from entry → exit close
        if outcome == "breakeven" and sl_dist > 0:
            price_diff = exit_price - entry if sig["direction"] == "LONG" else entry - exit_price
            pnl_pips   = price_diff * _pip_factor(atr)
            if pnl_pips > 0:
                outcome = "win"
            elif pnl_pips < 0:
                outcome = "loss"

        rr = abs(pnl_pips) / (sl_dist * _pip_factor(atr)) if sl_dist > 0 else 0.0
        if outcome == "loss":
            rr = -rr

        pnl_list.append(pnl_pips)

        trades.append(BacktestTrade(
            bar_index   = i,
            time        = sig["time"],
            direction   = sig["direction"],
            entry       = round(entry, 5),
            sl          = round(sl, 5),
            tp          = round(tp, 5),
            sl_type     = cfg["sl_type"],
            tp_type     = cfg["tp_type"],
            atr         = round(atr, 5),
            outcome     = outcome,
            exit_bar    = exit_bar,
            exit_price  = round(exit_price, 5),
            pnl_pips    = round(pnl_pips, 2),
            rr_achieved = round(rr, 3),
            seq_repr    = seq,
            similarity  = round(sig["similarity"], 3),
        ))

        if outcome == "win":
            wins += 1
            seq_win_counts[seq]  = seq_win_counts.get(seq, 0) + 1
        elif outcome == "loss":
            losses += 1
            seq_loss_counts[seq] = seq_loss_counts.get(seq, 0) + 1
        else:
            breakeven += 1

    # ── Metrics ───────────────────────────────────────────────────────────────
    total      = len(signals)
    win_rate   = (wins / total * 100) if total > 0 else 0.0
    gross_win  = sum(p for p in pnl_list if p > 0)
    gross_loss = abs(sum(p for p in pnl_list if p < 0))
    pf         = (gross_win / gross_loss) if gross_loss > 0 else float(wins or 0)
    total_pips = sum(pnl_list)
    avg_rr     = float(np.mean([abs(p) for p in pnl_list if p != 0])) if pnl_list else 0.0

    equity_curve = _build_equity_curve(pnl_list)
    sharpe       = _sharpe(equity_curve)
    sortino      = _sortino(equity_curve)
    max_dd       = _max_drawdown(equity_curve)

    total_bars = sum(state_counts.values()) or 1
    state_dist = {k: round(v / total_bars, 4) for k, v in state_counts.items()}

    best_seq  = _best_seq(seq_win_counts, seq_loss_counts, min_occ=3)
    worst_seq = _worst_seq(seq_win_counts, seq_loss_counts, min_occ=3)

    logger.info(
        f"[Backtest] Done: {total} signals, {wins}W/{losses}L/{breakeven}BE, "
        f"WR={win_rate:.1f}% PF={pf:.2f} Sharpe={sharpe:.2f} | "
        f"SL={cfg['sl_type']}×{cfg['sl_value']} TP={cfg['tp_type']}×{cfg['tp_value']} MaxHold={max_hold}"
    )

    return BacktestRunResult(
        total_signals      = total,
        wins               = wins,
        losses             = losses,
        breakeven          = breakeven,
        win_rate           = round(win_rate, 2),
        profit_factor      = round(pf, 3),
        sharpe_ratio       = round(sharpe, 4),
        sortino_ratio      = round(sortino, 4),
        max_drawdown       = round(max_dd, 2),
        avg_rr             = round(avg_rr, 4),
        total_pips         = round(total_pips, 2),
        equity_curve       = equity_curve,
        state_distribution = state_dist,
        best_seq_repr      = best_seq,
        worst_seq_repr     = worst_seq,
        trades             = trades,
        sl_type            = cfg["sl_type"],
        sl_value           = cfg["sl_value"],
        tp_type            = cfg["tp_type"],
        tp_value           = cfg["tp_value"],
        max_hold_bars      = max_hold,
    )


# ─── Config helpers ───────────────────────────────────────────────────────────

def _resolve_config(cfg: dict) -> dict:
    return {
        "sl_type":       str(cfg.get("sl_type",       "atr")).lower(),
        "sl_value":      float(cfg.get("sl_value",    DEFAULT_SL_ATR)),
        "tp_type":       str(cfg.get("tp_type",       "atr")).lower(),
        "tp_value":      float(cfg.get("tp_value",    DEFAULT_TP_ATR)),
        "max_hold_bars": int(cfg.get("max_hold_bars", DEFAULT_MAX_HOLD)),
    }


def _sl_distance(atr: float, cfg: dict) -> float:
    """Returns the absolute price distance for SL."""
    if cfg["sl_type"] == "fixed":
        return cfg["sl_value"]     # direct price units (e.g. 1.5 for gold = $1.5)
    return atr * cfg["sl_value"]   # ATR multiple


def _tp_distance(atr: float, cfg: dict) -> float:
    """Returns the absolute price distance for TP."""
    if cfg["tp_type"] == "fixed":
        return cfg["tp_value"]
    return atr * cfg["tp_value"]


def _pip_factor(atr: float) -> float:
    """
    Convert price distance → 'pips'.
    For gold (XAUUSDm): 1 pip = $0.01 → factor = 100.
    We normalise pips as atr/atr = 1 RR, so we use 10 as a cosmetic scale.
    """
    return 10.0


def _bar_time(row) -> str:
    try:
        t = row.get("time", row.get("datetime", None))
        if t is None:
            return ""
        if isinstance(t, (int, float)):
            return datetime.utcfromtimestamp(t).isoformat()
        return pd.Timestamp(t).isoformat()
    except Exception:
        return ""


# ─── Statistical helpers ──────────────────────────────────────────────────────

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    return df.reset_index(drop=True)


def _pattern_similarity(recent_states: list[int], pattern: list[int]) -> float:
    """
    Opsi A: ordered subsequence match.
    Checks how many pattern states appear IN ORDER within recent_states.
    Allows noise states in between.
    """
    if not pattern or not recent_states:
        return 0.0
    matched    = 0
    search_pos = 0
    for target in pattern:
        for j in range(search_pos, len(recent_states)):
            if recent_states[j] == target:
                matched    += 1
                search_pos  = j + 1
                break
    return matched / len(pattern)


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    try:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"]  - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(period, min_periods=1).mean().iloc[-1])
    except Exception:
        return float((df["high"].iloc[-1] - df["low"].iloc[-1]))


def _build_equity_curve(pnl_list: list[float]) -> list[float]:
    equity = [100.0]
    for pnl in pnl_list:
        equity.append(round(equity[-1] + pnl * 0.01, 2))
    return equity


def _sharpe(equity: list[float]) -> float:
    if len(equity) < 2:
        return 0.0
    returns = np.diff(equity) / np.array(equity[:-1])
    return float(returns.mean() / returns.std()) if returns.std() > 0 else 0.0


def _sortino(equity: list[float]) -> float:
    if len(equity) < 2:
        return 0.0
    returns  = np.diff(equity) / np.array(equity[:-1])
    downside = returns[returns < 0]
    return float(returns.mean() / downside.std()) if len(downside) > 0 and downside.std() > 0 else 0.0


def _max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak   = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        max_dd = max(max_dd, dd)
    return max_dd


def _best_seq(win_counts: dict[str, int], loss_counts: dict[str, int], min_occ: int = 3) -> Optional[str]:
    best, best_wr = None, -1.0
    for seq in win_counts:
        w = win_counts.get(seq, 0)
        l = loss_counts.get(seq, 0)
        if w + l < min_occ:
            continue
        wr = w / (w + l)
        if wr > best_wr:
            best_wr, best = wr, seq
    return best


def _worst_seq(win_counts: dict[str, int], loss_counts: dict[str, int], min_occ: int = 3) -> Optional[str]:
    worst, worst_wr = None, 2.0
    for seq in loss_counts:
        w = win_counts.get(seq, 0)
        l = loss_counts.get(seq, 0)
        if w + l < min_occ:
            continue
        wr = w / (w + l)
        if wr < worst_wr:
            worst_wr, worst = wr, seq
    return worst


def _empty_result(cfg: dict | None = None) -> BacktestRunResult:
    c = _resolve_config(cfg or {})
    return BacktestRunResult(
        total_signals=0, wins=0, losses=0, breakeven=0,
        win_rate=0.0, profit_factor=0.0, sharpe_ratio=0.0,
        sortino_ratio=0.0, max_drawdown=0.0, avg_rr=0.0, total_pips=0.0,
        equity_curve=[100.0], state_distribution={},
        best_seq_repr=None, worst_seq_repr=None,
        trades=[],
        sl_type=c["sl_type"], sl_value=c["sl_value"],
        tp_type=c["tp_type"], tp_value=c["tp_value"],
        max_hold_bars=c["max_hold_bars"],
    )
