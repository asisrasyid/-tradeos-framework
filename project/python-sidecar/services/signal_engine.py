"""
Signal Engine — TradeOS v5.1
Live candle-loop: waits for bar close → HMM classify → pattern match → emit signal.

Per session:
  1. Wait for next bar close (based on timeframe)
  2. Fetch last N bars from MT5 (or yfinance fallback)
  3. HMM classify → get recent state sequence (last SEQ_WINDOW states)
  4. Pattern similarity vs theory's pattern_states (Opsi A: ordered subsequence)
  5. If similarity >= threshold → POST signal to C# callback URL
  6. Repeat until session stopped or engine cancelled
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
import pandas as pd

from services.feature_extractor import extract_features
from services.hmm_classifier import get_classifier
from services import mt5_executor

# Persistent HTTP client for async C# logging (fire-and-forget only)
# Timeout kept short — logging failure must never block order execution.
_log_client: httpx.AsyncClient | None = None

def _get_log_client() -> httpx.AsyncClient:
    global _log_client
    if _log_client is None or _log_client.is_closed:
        _log_client = httpx.AsyncClient(timeout=3.0)
    return _log_client

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TF_SECONDS: dict[str, int] = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H8": 28800, "D1": 86400,
}
BAR_CLOSE_BUFFER_S = 3     # seconds after bar close before fetching
LOOKBACK_BARS      = 60    # bars to fetch per evaluation cycle
SEQ_WINDOW         = 10    # recent states window for similarity check


# ── Session dataclass ─────────────────────────────────────────────────────────

@dataclass
class EngineSession:
    session_id:           str
    theory_id:            str
    instrument:           str
    timeframe:            str
    pattern_states:       list[int]
    similarity_threshold: float
    direction:            str
    tp_mult:              float
    sl_mult:              float
    callback_url:         str
    auto_execute:         bool = False   # True → place real MT5 order on signal
    volume:               float = 0.01  # lot size for auto-execute
    started_at:           datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_checked:         Optional[datetime] = None
    last_signal:          Optional[datetime] = None
    last_similarity:      float           = 0.0   # similarity score of the last fired signal
    last_signal_dir:      str             = ""    # direction of last fired signal (LONG | SHORT)
    signals_fired:        int = 0
    bars_evaluated:       int = 0          # total bar evaluations (for no-signal timeout)
    no_signal_warning:    bool = False     # True if many bars evaluated but no signal fired
    status:               str = "running"   # running | stopped | error
    error_msg:            Optional[str] = None


# ── Session registry (in-memory) ──────────────────────────────────────────────

_sessions: dict[str, EngineSession] = {}
_tasks:    dict[str, asyncio.Task]  = {}


# ── Public API ────────────────────────────────────────────────────────────────

def start_session(session: EngineSession) -> None:
    """Register and launch background asyncio loop for a session."""
    if session.session_id in _tasks:
        stop_session(session.session_id)   # cancel stale task for same ID

    _sessions[session.session_id] = session
    task = asyncio.create_task(
        _engine_loop(session),
        name=f"engine-{session.session_id[:8]}",
    )
    _tasks[session.session_id] = task
    logger.info(
        "[Engine] Session started: %s  %s/%s  pattern=%s  threshold=%.2f",
        session.session_id[:8], session.instrument, session.timeframe,
        session.pattern_states, session.similarity_threshold,
    )


def stop_session(session_id: str) -> bool:
    """Cancel a running session. Returns True if it was running."""
    task = _tasks.pop(session_id, None)
    sess = _sessions.get(session_id)
    if task and not task.done():
        task.cancel()
    if sess:
        sess.status = "stopped"
    return task is not None


def get_all_status() -> list[dict]:
    """Return status snapshot for all known sessions."""
    return [
        {
            "session_id":    s.session_id,
            "theory_id":     s.theory_id,
            "instrument":    s.instrument,
            "timeframe":     s.timeframe,
            "direction":     s.direction,
            "pattern_states": s.pattern_states,
            "similarity_threshold": s.similarity_threshold,
            "auto_execute":  s.auto_execute,
            "volume":        s.volume,
            "status":        s.status,
            "started_at":    s.started_at.isoformat(),
            "last_checked":  s.last_checked.isoformat() if s.last_checked else None,
            "last_signal":   s.last_signal.isoformat() if s.last_signal else None,
            "signals_fired":     s.signals_fired,
            "bars_evaluated":    s.bars_evaluated,
            "no_signal_warning": s.no_signal_warning,
            "error_msg":         s.error_msg,
        }
        for s in _sessions.values()
    ]


def get_last_signal_for_symbol(symbol: str) -> dict:
    """Return the most recent fired signal for a symbol across all active sessions.
    Used by AGGR/CASCADE HMM filter to gate position opens.
    """
    best: Optional[EngineSession] = None
    for s in _sessions.values():
        if s.instrument.upper() != symbol.upper():
            continue
        if s.last_signal is None:
            continue
        if best is None or s.last_signal > best.last_signal:  # type: ignore[operator]
            best = s

    if best is None:
        return {"found": False, "symbol": symbol}

    age_s = (datetime.now(timezone.utc) - best.last_signal).total_seconds()
    return {
        "found":      True,
        "symbol":     symbol,
        "direction":  best.last_signal_dir,   # LONG | SHORT
        "similarity": best.last_similarity,
        "age_s":      round(age_s, 1),
        "timeframe":  best.timeframe,
        "session_id": best.session_id,
    }


# ── Engine loop ───────────────────────────────────────────────────────────────

async def _engine_loop(sess: EngineSession) -> None:
    """Async loop: evaluate immediately, then sleep until next bar close, repeat."""
    logger.info("[Engine] Loop starting for %s/%s", sess.instrument, sess.timeframe)

    # Evaluate once immediately at start
    try:
        await _evaluate(sess)
    except Exception as e:
        logger.warning("[Engine] Initial evaluation error: %s", e)

    while True:
        try:
            sleep_s = _seconds_to_next_close(sess.timeframe)
            logger.info(
                "[Engine] %s/%s sleeping %.0fs until next bar close",
                sess.instrument, sess.timeframe, sleep_s,
            )
            await asyncio.sleep(sleep_s)
            await _evaluate(sess)

        except asyncio.CancelledError:
            sess.status = "stopped"
            logger.info("[Engine] Session %s cancelled", sess.session_id[:8])
            return

        except Exception as e:
            logger.error("[Engine] Unhandled loop error: %s", e)
            sess.error_msg = str(e)
            # Back off one bar length then retry (don't crash the loop)
            await asyncio.sleep(TF_SECONDS.get(sess.timeframe.upper(), 3600))


# ── Per-bar evaluation ────────────────────────────────────────────────────────

NO_SIGNAL_WARN_BARS = 20   # warn after 20 bars with no signal (e.g. 5h on M15)


async def _evaluate(sess: EngineSession) -> None:
    """Fetch → classify → similarity → emit if match."""
    sess.last_checked   = datetime.now(timezone.utc)
    sess.bars_evaluated += 1

    # 1. Fetch recent bars
    df = await _fetch_bars(sess.instrument, sess.timeframe, LOOKBACK_BARS)
    if df is None or len(df) < 30:
        logger.warning("[Engine] Not enough bars for %s/%s", sess.instrument, sess.timeframe)
        return

    # 2. HMM classify
    clf = get_classifier()
    if not clf.is_loaded(sess.instrument, sess.timeframe):
        logger.warning("[Engine] HMM not loaded for %s/%s", sess.instrument, sess.timeframe)
        return

    try:
        features  = extract_features(df)
        clf_obj   = clf._cache[(sess.instrument.upper(), sess.timeframe.upper())]
        X_scaled  = clf_obj.scaler.transform(features)
        all_states = clf_obj.model.predict(X_scaled).tolist()
        recent_states = all_states[-SEQ_WINDOW:]
        seq_repr      = "".join(f"S{s}" for s in recent_states)
    except Exception as e:
        logger.warning("[Engine] HMM classify error: %s", e)
        return

    # 3. Pattern similarity
    similarity = _pattern_similarity(recent_states, sess.pattern_states)
    logger.info(
        "[Engine] %s/%s similarity=%.2f threshold=%.2f seq=%s",
        sess.instrument, sess.timeframe, similarity, sess.similarity_threshold, seq_repr,
    )

    if similarity < sess.similarity_threshold:
        # No-signal timeout warning: after N bars with no signal, flag for UI
        if sess.signals_fired == 0 and sess.bars_evaluated >= NO_SIGNAL_WARN_BARS:
            if not sess.no_signal_warning:
                sess.no_signal_warning = True
                logger.warning(
                    "[Engine] %s/%s: No signal fired after %d bars. "
                    "Check pattern_states configuration (current: %s).",
                    sess.instrument, sess.timeframe, sess.bars_evaluated, sess.pattern_states,
                )
        return

    # 4. Compute entry / SL / TP from last bar
    close_price = float(df["close"].iloc[-1])
    atr         = _atr(df)
    atr         = atr if atr > 0 else 1.0

    if sess.direction == "LONG":
        entry = close_price
        tp    = close_price + atr * sess.tp_mult
        sl    = close_price - atr * sess.sl_mult
    else:
        entry = close_price
        tp    = close_price - atr * sess.tp_mult
        sl    = close_price + atr * sess.sl_mult

    # 5a. AUTO-EXECUTE: direct MT5 call — 0 HTTP hops, ~10-30ms
    mt5_ticket: int | None = None
    fill_price: float      = entry

    if sess.auto_execute and mt5_executor.is_available():
        try:
            order_result = mt5_executor.place_order(
                symbol   = sess.instrument,
                action   = "BUY" if sess.direction == "LONG" else "SELL",
                volume   = sess.volume,
                sl_price = round(sl, 5),
                tp_price = round(tp, 5),
                comment  = f"TradeOS {sess.session_id[:8]}",
            )
            mt5_ticket = order_result["order_id"]
            fill_price = order_result["fill_price"]
            logger.info(
                "[Engine] MT5 ORDER SENT → %s %s  fill=%.5f  TP=%.5f  SL=%.5f  "
                "ticket=%s  retcode=%d  sim=%.2f",
                sess.instrument, sess.direction, fill_price, tp, sl,
                mt5_ticket, order_result["retcode"], similarity,
            )
        except Exception as e:
            logger.error("[Engine] MT5 direct execute FAILED: %s", e)
            # Do not fire callback if order failed — avoid phantom signals in C#
            return

    # 5b. LOG to C# — fire-and-forget (never blocks execution)
    payload = {
        "session_id":   sess.session_id,
        "theory_id":    sess.theory_id,
        "instrument":   sess.instrument,
        "timeframe":    sess.timeframe,
        "direction":    sess.direction,
        "entry_price":  round(fill_price, 5),
        "sl_price":     round(sl, 5),
        "tp_price":     round(tp, 5),
        "similarity":   round(similarity, 4),
        "seq_repr":     seq_repr,
        "signal_time":  sess.last_checked.isoformat(),
        "auto_execute": sess.auto_execute,
        "volume":       sess.volume,
        "mt5_ticket":   mt5_ticket,
    }

    async def _log_to_backend() -> None:
        try:
            client = _get_log_client()
            resp = await client.post(sess.callback_url, json=payload)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[Engine] C# log callback failed (non-blocking): %s", exc)

    asyncio.create_task(_log_to_backend())   # fire-and-forget

    sess.signals_fired    += 1
    sess.last_signal       = sess.last_checked
    sess.last_similarity   = round(similarity, 4)
    sess.last_signal_dir   = sess.direction
    sess.no_signal_warning = False
    logger.info(
        "[Engine] SIGNAL → %s %s  entry=%.5f  TP=%.5f  SL=%.5f  sim=%.2f  ticket=%s",
        sess.instrument, sess.direction, fill_price, tp, sl, similarity, mt5_ticket,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seconds_to_next_close(timeframe: str) -> float:
    """Seconds until the next bar close + BAR_CLOSE_BUFFER_S."""
    bar_s = TF_SECONDS.get(timeframe.upper(), 3600)
    import time
    now_ts         = time.time()
    elapsed_in_bar = now_ts % bar_s
    remaining      = bar_s - elapsed_in_bar
    return max(remaining + BAR_CLOSE_BUFFER_S, BAR_CLOSE_BUFFER_S)


def _pattern_similarity(recent_states: list[int], pattern: list[int]) -> float:
    """Ordered subsequence match (same logic as backtest_runner)."""
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
        return float(df["high"].iloc[-1] - df["low"].iloc[-1])


async def _fetch_bars(instrument: str, timeframe: str, bars: int) -> pd.DataFrame | None:
    """Fetch recent N bars via MT5 (or yfinance fallback)."""
    try:
        from routers.ohlc import _fetch_from_mt5
        bar_list = await _fetch_from_mt5(instrument, timeframe, bars)
        if not bar_list:
            raise RuntimeError("empty response")
        df = pd.DataFrame([b.model_dump() for b in bar_list])
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        logger.warning("[Engine] MT5 fetch failed (%s), trying yfinance", e)

    try:
        from routers.ohlc import _fetch_from_yfinance
        bar_list = await _fetch_from_yfinance(instrument, timeframe, bars)
        df = pd.DataFrame([b.model_dump() for b in bar_list])
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e2:
        logger.error("[Engine] yfinance fallback failed: %s", e2)
        return None
