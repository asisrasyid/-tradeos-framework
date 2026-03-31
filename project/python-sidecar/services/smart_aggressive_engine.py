"""
smart_aggressive_engine.py — Smart Aggressive Layer Trading Engine
==================================================================
Two decision modes:
  - VOTING mode: HMM + EMA20 + Momentum vote system (original)
  - AI mode:     Claude LLM decides direction, TP, SL via multi-TF analysis

AI mode uses M15 (50 bars) for entry timing + H1 (20 bars) for trend context.
Every position open/close is logged to C# via callback HTTP calls.
"""
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────
PYTHON_API        = "http://localhost:8001"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
LLM_MODEL         = "claude-haiku-4-5-20251001"
LLM_PROMPT_VER    = "v1.0"
LLM_TIMEOUT       = 15   # seconds

_BULLISH_LABELS = {"trending_up", "breakout", "uptrend", "bull", "bullish", "up"}
_BEARISH_LABELS = {"trending_down", "breakdown", "downtrend", "bear", "bearish", "down"}

# ── LLM Tool definition (structured output) ───────────────────────────────

_TRADING_TOOL = {
    "name": "make_trading_decision",
    "description": "Submit a structured trading decision after analyzing multi-timeframe market data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["BUY", "SELL", "SKIP"],
                "description": "Trade direction or SKIP if conditions not met"
            },
            "tp_price": {
                "type": "number",
                "description": "Take profit absolute price level. Required if decision is BUY or SELL."
            },
            "sl_price": {
                "type": "number",
                "description": "Stop loss absolute price level. Required if decision is BUY or SELL."
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score 0.0 to 1.0"
            },
            "reasoning": {
                "type": "string",
                "description": "Concise reasoning max 250 characters"
            },
            "skip_reason": {
                "type": "string",
                "description": "Reason for SKIP. Null if not skipping."
            }
        },
        "required": ["decision", "confidence", "reasoning"]
    }
}

_SYSTEM_PROMPT = """You are an expert algorithmic trading analyst specializing in forex and gold (XAU/USD) markets.

TASK: Analyze multi-timeframe OHLC data and make a precise trading decision.

ANALYSIS FRAMEWORK:
1. H1 bars = TREND DIRECTION. Identify the dominant trend. Only trade WITH H1 trend unless strong reversal evidence exists.
2. M15 bars = ENTRY TIMING. Confirm momentum aligns with H1 trend. Look for pullbacks, breakouts, or continuation setups.
3. ATR = VOLATILITY CONTEXT. Used to assess if market conditions are suitable.
4. HMM State = REGIME CLASSIFICATION. Use to confirm market structure.
5. EMA20 = DYNAMIC SUPPORT/RESISTANCE. Price above = bullish bias, below = bearish bias.

TP/SL RULES:
- Set TP at next significant resistance (BUY) or support (SELL) on M15/H1 structure.
- Set SL just beyond the most recent swing high (SELL) or swing low (BUY).
- Minimum Risk/Reward ratio: 1.5:1. If not achievable, SKIP.
- Both TP and SL must be absolute price values.

SKIP CONDITIONS:
- Conflicting H1 vs M15 signals with no clear resolution
- Price in ranging/consolidating market with no breakout confirmation
- ATR too low (flat market) or extremely elevated (news spike)
- Insufficient R:R ratio
- HMM confidence below threshold

CONFIDENCE SCALE:
- 0.90-1.0: Exceptional setup, all factors aligned
- 0.75-0.89: Strong setup, minor uncertainties
- 0.65-0.74: Acceptable setup, proceed with caution
- Below 0.65: SKIP

Always respond by calling make_trading_decision with your structured decision."""


# ── Session state ──────────────────────────────────────────────────────────

@dataclass
class SmartSession:
    session_id:          str
    symbol:              str
    timeframe:           str
    max_layers:          int
    open_per_interval:   int
    eval_interval_s:     int
    volume:              float
    tp_atr_mult:         float
    sl_atr_mult:         float
    min_atr:             float
    max_atr:             float
    min_confidence:      float
    callback_url:        str
    # AI params
    ai_enabled:          bool  = False
    entries_per_decision:int   = 5
    max_calls_per_hour:  int   = 6

    # Runtime state
    active:              bool       = True
    active_tickets:      list       = field(default_factory=list)
    total_opened:        int        = 0
    total_closed_win:    int        = 0
    total_closed_loss:   int        = 0
    total_closed_other:  int        = 0
    total_profit:        float      = 0.0
    started_at:          float      = field(default_factory=time.time)
    last_action:         str        = "starting"
    last_direction:      str        = ""
    last_score:          int        = 0
    error:               str | None = None
    # AI runtime state
    ai_status:           str        = "active"   # active | ai_paused
    ai_calls_this_hour:  int        = 0
    ai_hour_window_start:float      = field(default_factory=time.time)
    ai_last_reasoning:   str        = ""
    ai_last_decision:    str        = ""
    ai_last_confidence:  float      = 0.0
    ai_calls_total:      int        = 0
    ai_retry_pending:    bool       = False


_sessions: dict[str, SmartSession] = {}
_threads:  dict[str, threading.Thread] = {}


# ── Public API ─────────────────────────────────────────────────────────────

def start_session(
    symbol:              str,
    timeframe:           str   = "M15",
    max_layers:          int   = 10,
    open_per_interval:   int   = 1,
    eval_interval_s:     int   = 30,
    volume:              float = 0.01,
    tp_atr_mult:         float = 1.5,
    sl_atr_mult:         float = 0.5,
    min_atr:             float = 0.5,
    max_atr:             float = 15.0,
    min_confidence:      float = 0.70,
    callback_url:        str   = "",
    ai_enabled:          bool  = False,
    entries_per_decision:int   = 5,
    max_calls_per_hour:  int   = 6,
) -> str:
    session_id = str(uuid.uuid4())
    sess = SmartSession(
        session_id           = session_id,
        symbol               = symbol,
        timeframe            = timeframe,
        max_layers           = max_layers,
        open_per_interval    = open_per_interval,
        eval_interval_s      = eval_interval_s,
        volume               = volume,
        tp_atr_mult          = tp_atr_mult,
        sl_atr_mult          = sl_atr_mult,
        min_atr              = min_atr,
        max_atr              = max_atr,
        min_confidence       = min_confidence,
        callback_url         = callback_url,
        ai_enabled           = ai_enabled,
        entries_per_decision = entries_per_decision,
        max_calls_per_hour   = max_calls_per_hour,
    )
    _sessions[session_id] = sess

    t = threading.Thread(
        target=_run_session, args=(sess,),
        daemon=True, name=f"smart-{session_id[:8]}"
    )
    t.start()
    _threads[session_id] = t

    mode = "AI" if ai_enabled else "VOTING"
    logger.info(
        "[SmartEngine] Started %s | %s %s layers=%d mode=%s eval=%ds",
        session_id[:8], symbol, timeframe, max_layers, mode, eval_interval_s
    )
    return session_id


def stop_session(session_id: str) -> bool:
    sess = _sessions.get(session_id)
    if sess is None:
        return False
    sess.active = False
    logger.info("[SmartEngine] Stop requested for %s", session_id[:8])
    return True


def resume_ai(session_id: str) -> bool:
    """Manually resume AI after ai_paused state."""
    sess = _sessions.get(session_id)
    if sess is None:
        return False
    if sess.ai_status == "ai_paused":
        sess.ai_status = "active"
        sess.ai_retry_pending = False
        logger.info("[SmartEngine] AI manually resumed for %s", session_id[:8])
    return True


def get_all_status() -> list[dict]:
    return [
        {
            "session_id":           s.session_id,
            "symbol":               s.symbol,
            "timeframe":            s.timeframe,
            "max_layers":           s.max_layers,
            "open_per_interval":    s.open_per_interval,
            "eval_interval_s":      s.eval_interval_s,
            "volume":               s.volume,
            "tp_atr_mult":          s.tp_atr_mult,
            "sl_atr_mult":          s.sl_atr_mult,
            "min_atr":              s.min_atr,
            "max_atr":              s.max_atr,
            "active":               s.active,
            "active_tickets":       list(s.active_tickets),
            "open_positions":       len(s.active_tickets),
            "total_opened":         s.total_opened,
            "total_closed_win":     s.total_closed_win,
            "total_closed_loss":    s.total_closed_loss,
            "total_closed_other":   s.total_closed_other,
            "total_profit":         round(s.total_profit, 2),
            "last_action":          s.last_action,
            "last_direction":       s.last_direction,
            "last_score":           s.last_score,
            "error":                s.error,
            "uptime_s":             int(time.time() - s.started_at),
            # AI fields
            "ai_enabled":           s.ai_enabled,
            "ai_status":            s.ai_status,
            "entries_per_decision": s.entries_per_decision,
            "max_calls_per_hour":   s.max_calls_per_hour,
            "ai_calls_this_hour":   s.ai_calls_this_hour,
            "ai_calls_total":       s.ai_calls_total,
            "ai_last_reasoning":    s.ai_last_reasoning,
            "ai_last_decision":     s.ai_last_decision,
            "ai_last_confidence":   s.ai_last_confidence,
        }
        for s in _sessions.values()
    ]


# ── Core loop ──────────────────────────────────────────────────────────────

def _run_session(sess: SmartSession) -> None:
    logger.info("[SmartEngine] Thread start %s mode=%s",
                sess.session_id[:8], "AI" if sess.ai_enabled else "VOTING")
    client = httpx.Client(timeout=20)
    try:
        while sess.active:
            _eval_and_trade(sess, client)
            _check_closed_positions(sess, client)
            for _ in range(sess.eval_interval_s * 2):
                if not sess.active:
                    break
                time.sleep(0.5)
    except Exception as exc:
        logger.error("[SmartEngine] Session %s crashed: %s", sess.session_id[:8], exc)
        sess.error = str(exc)
    finally:
        sess.active = False
        client.close()
        logger.info(
            "[SmartEngine] Session %s ended | opened=%d wins=%d profit=$%.2f",
            sess.session_id[:8], sess.total_opened, sess.total_closed_win, sess.total_profit
        )


# ── Evaluation dispatcher ──────────────────────────────────────────────────

def _eval_and_trade(sess: SmartSession, client: httpx.Client) -> None:
    if sess.ai_enabled:
        _eval_ai(sess, client)
    else:
        _eval_voting(sess, client)


# ── AI Decision Path ───────────────────────────────────────────────────────

def _eval_ai(sess: SmartSession, client: httpx.Client) -> None:
    """AI-powered evaluation using Claude LLM."""

    if len(sess.active_tickets) >= sess.max_layers:
        sess.last_action = f"at max layers ({sess.max_layers}), waiting for closes"
        return

    # Check rate limit
    _refresh_hour_window(sess)
    if sess.ai_calls_this_hour >= sess.max_calls_per_hour:
        remaining = int(3600 - (time.time() - sess.ai_hour_window_start))
        sess.last_action = f"LLM budget reached ({sess.ai_calls_this_hour}/{sess.max_calls_per_hour}/hr) — reset in {remaining}s"
        return

    # Check AI paused status
    if sess.ai_status == "ai_paused":
        if sess.ai_retry_pending:
            # Auto retry once
            sess.ai_retry_pending = False
            logger.info("[SmartEngine] %s Auto-retrying AI after pause", sess.session_id[:8])
        else:
            sess.last_action = "AI paused — LLM error. Auto-retry next interval."
            sess.ai_retry_pending = True
            return

    # Fetch OHLC for both timeframes
    try:
        bars_m15 = _fetch_ohlc(sess.symbol, "M15", 50, client)
        bars_h1  = _fetch_ohlc(sess.symbol, "H1",  20, client)
    except Exception as e:
        sess.last_action = f"OHLC fetch failed: {e}"
        return

    if len(bars_m15) < 20 or len(bars_h1) < 10:
        sess.last_action = "insufficient OHLC bars"
        return

    # Compute indicators on M15
    closes_m15 = [b["close"] for b in bars_m15]
    highs_m15  = [b["high"]  for b in bars_m15]
    lows_m15   = [b["low"]   for b in bars_m15]
    atr   = _calc_atr(highs_m15, lows_m15, closes_m15, 14)
    ema20 = _calc_ema(closes_m15, 20)

    if atr < sess.min_atr or atr > sess.max_atr:
        sess.last_action = f"ATR {atr:.3f} out of range [{sess.min_atr},{sess.max_atr}]"
        return

    # HMM classify
    hmm_state: Optional[int]   = None
    hmm_label: Optional[str]   = None
    hmm_conf:  Optional[float] = None
    try:
        hmm_resp  = _classify_hmm(sess.symbol, sess.timeframe, client)
        hmm_state = hmm_resp.get("state")
        hmm_label = hmm_resp.get("state_label", "")
        hmm_conf  = float(hmm_resp.get("confidence", 0.5))
    except Exception:
        hmm_label = "unknown"
        hmm_conf  = 0.5

    # Voting scores (sent as context to LLM)
    vote_hmm      = _vote_hmm(hmm_label or "")
    vote_ema      = 1 if closes_m15[-1] > ema20 else -1
    vote_momentum = _vote_momentum(closes_m15)
    vote_score    = vote_hmm + vote_ema + vote_momentum

    # Trading session
    session_name = _get_trading_session()

    # Build LLM prompt
    user_prompt = _build_prompt(
        symbol       = sess.symbol,
        bars_m15     = bars_m15,
        bars_h1      = bars_h1,
        atr          = atr,
        ema20        = ema20,
        hmm_state    = hmm_state,
        hmm_label    = hmm_label or "unknown",
        hmm_conf     = hmm_conf or 0.0,
        vote_hmm     = vote_hmm,
        vote_ema     = vote_ema,
        vote_momentum= vote_momentum,
        vote_score   = vote_score,
        open_count   = len(sess.active_tickets),
        max_layers   = sess.max_layers,
        session_profit = sess.total_profit,
        session_name = session_name,
    )

    # Call LLM
    t_start = time.time()
    ai_result, error_msg = _call_llm(user_prompt)
    latency_ms = int((time.time() - t_start) * 1000)

    if error_msg or ai_result is None:
        logger.error("[SmartEngine] %s LLM error: %s", sess.session_id[:8], error_msg)
        sess.ai_status    = "ai_paused"
        sess.ai_retry_pending = False
        sess.last_action  = f"AI paused — {error_msg}"
        return

    # Count this call
    sess.ai_calls_this_hour += 1
    sess.ai_calls_total     += 1

    decision   = ai_result.get("decision", "SKIP")
    tp_price   = ai_result.get("tp_price")
    sl_price   = ai_result.get("sl_price")
    confidence = float(ai_result.get("confidence", 0.0))
    reasoning  = ai_result.get("reasoning", "")
    skip_reason= ai_result.get("skip_reason")

    # Update session state
    sess.ai_last_decision   = decision
    sess.ai_last_reasoning  = reasoning or ""
    sess.ai_last_confidence = confidence
    sess.last_direction     = f"AI:{decision} conf={confidence:.2f}"
    sess.last_score         = vote_score  # keep for reference

    logger.info(
        "[SmartEngine] %s AI decision=%s conf=%.2f latency=%dms | %s",
        sess.session_id[:8], decision, confidence, latency_ms,
        (reasoning or "")[:80]
    )

    if decision == "SKIP":
        sess.last_action = f"AI SKIP: {skip_reason or reasoning or 'no reason'}"
        return

    if confidence < sess.min_confidence:
        sess.last_action = f"AI conf {confidence:.2f} < min {sess.min_confidence} — skipped"
        return

    if decision not in ("BUY", "SELL") or not tp_price or not sl_price:
        sess.last_action = "AI returned invalid decision format"
        return

    # Validate TP/SL direction
    current_price = closes_m15[-1]
    if decision == "BUY"  and (tp_price <= current_price or sl_price >= current_price):
        sess.last_action = f"AI BUY invalid: TP={tp_price} SL={sl_price} price={current_price}"
        return
    if decision == "SELL" and (tp_price >= current_price or sl_price <= current_price):
        sess.last_action = f"AI SELL invalid: TP={tp_price} SL={sl_price} price={current_price}"
        return

    # Open entries_per_decision positions (capped by available slots)
    slots     = sess.max_layers - len(sess.active_tickets)
    to_open   = min(sess.entries_per_decision, slots)
    sess.last_action = f"AI {decision} conf={confidence:.2f} — opening {to_open} positions"

    for i in range(to_open):
        if not sess.active:
            break
        _open_ai_position(
            sess       = sess,
            client     = client,
            direction  = decision,
            tp_price   = tp_price,
            sl_price   = sl_price,
            atr        = atr,
            ema20      = ema20,
            hmm_state  = hmm_state,
            hmm_label  = hmm_label,
            hmm_conf   = hmm_conf,
            close_price= current_price,
            vote_hmm   = vote_hmm,
            vote_ema   = vote_ema,
            vote_momentum = vote_momentum,
            score      = vote_score,
            reasoning  = reasoning,
            confidence = confidence,
            latency_ms = latency_ms,
        )


def _open_ai_position(
    sess, client, direction, tp_price, sl_price,
    atr, ema20, hmm_state, hmm_label, hmm_conf, close_price,
    vote_hmm, vote_ema, vote_momentum, score,
    reasoning, confidence, latency_ms,
) -> None:
    payload = {
        "symbol":   sess.symbol,
        "action":   direction,
        "volume":   sess.volume,
        "tp_price": round(tp_price, 5),
        "sl_price": round(sl_price, 5),
        "comment":  f"SmartAI:{sess.session_id[:8]}",
    }

    try:
        r = client.post(f"{PYTHON_API}/python/mt5/order", json=payload)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        sess.last_action = f"order HTTP error: {e}"
        return

    if not data.get("success"):
        rc   = data.get("retcode")
        desc = data.get("retcode_desc", "?")
        sess.last_action = f"order FAILED {direction}: {desc} (rc={rc})"
        logger.warning("[SmartEngine] %s %s", sess.session_id[:8], sess.last_action)
        return

    ticket      = data["order_id"]
    entry_price = data.get("price", close_price)

    sess.active_tickets.append(ticket)
    sess.total_opened += 1
    sess.last_action = (
        f"AI opened {direction} ticket={ticket} "
        f"TP={tp_price:.2f} SL={sl_price:.2f} conf={confidence:.2f}"
    )
    logger.info("[SmartEngine] %s AI opened %s ticket=%d TP=%.2f SL=%.2f",
                sess.session_id[:8], direction, ticket, tp_price, sl_price)

    _log_open(sess, client, {
        "sessionId":        sess.session_id,
        "symbol":           sess.symbol,
        "direction":        direction,
        "directionScore":   score,
        "atrValue":         atr,
        "ema20Value":       ema20,
        "hmmState":         hmm_state,
        "hmmStateLabel":    hmm_label,
        "hmmConfidence":    hmm_conf,
        "closePrice":       close_price,
        "spreadPips":       0.0,
        "voteHmm":          vote_hmm,
        "voteEma":          vote_ema,
        "voteMomentum":     vote_momentum,
        "entryPrice":       entry_price,
        "tpPrice":          tp_price,
        "slPrice":          sl_price,
        "tpAtrMult":        sess.tp_atr_mult,
        "slAtrMult":        sess.sl_atr_mult,
        "volume":           sess.volume,
        "mt5Ticket":        ticket,
        "aiEnabled":        True,
        "llmModel":         LLM_MODEL,
        "llmReasoning":     reasoning,
        "llmConfidence":    confidence,
        "llmPromptVer":     LLM_PROMPT_VER,
        "llmLatencyMs":     latency_ms,
        "entriesPerDecision": sess.entries_per_decision,
    })


# ── Voting Decision Path (unchanged logic) ────────────────────────────────

def _eval_voting(sess: SmartSession, client: httpx.Client) -> None:
    if len(sess.active_tickets) >= sess.max_layers:
        sess.last_action = f"at max layers ({sess.max_layers}), waiting for closes"
        return

    try:
        ohlc_bars = _fetch_ohlc(sess.symbol, sess.timeframe, 50, client)
    except Exception as e:
        sess.last_action = f"OHLC fetch failed: {e}"
        return

    if len(ohlc_bars) < 20:
        sess.last_action = "insufficient OHLC bars"
        return

    closes = [b["close"] for b in ohlc_bars]
    highs  = [b["high"]  for b in ohlc_bars]
    lows   = [b["low"]   for b in ohlc_bars]

    atr   = _calc_atr(highs, lows, closes, 14)
    ema20 = _calc_ema(closes, 20)

    if atr < sess.min_atr or atr > sess.max_atr:
        sess.last_action = f"ATR {atr:.3f} out of range [{sess.min_atr},{sess.max_atr}]"
        return

    hmm_state: Optional[int]   = None
    hmm_label: Optional[str]   = None
    hmm_conf:  Optional[float] = None
    try:
        hmm_resp  = _classify_hmm(sess.symbol, sess.timeframe, client)
        hmm_state = hmm_resp.get("state")
        hmm_label = hmm_resp.get("state_label", "")
        hmm_conf  = float(hmm_resp.get("confidence", 0.5))
    except Exception:
        hmm_label = ""
        hmm_conf  = 0.0

    vote_hmm      = _vote_hmm(hmm_label or "")
    vote_ema      = 1 if closes[-1] > ema20 else -1
    vote_momentum = _vote_momentum(closes)
    score         = vote_hmm + vote_ema + vote_momentum
    sess.last_score = score

    if score >= 2:
        direction = "BUY"
    elif score <= -2:
        direction = "SELL"
    else:
        sess.last_direction = f"SKIP (score={score})"
        sess.last_action    = f"score={score} H={vote_hmm} E={vote_ema} M={vote_momentum} ATR={atr:.3f}"
        return

    if vote_hmm != 0 and (hmm_conf or 0) < sess.min_confidence:
        sess.last_action = f"HMM conf {hmm_conf:.2f} < min {sess.min_confidence}"
        return

    sess.last_direction = direction
    slots    = sess.max_layers - len(sess.active_tickets)
    to_open  = min(sess.open_per_interval, slots)

    for _ in range(to_open):
        if not sess.active:
            break
        _open_voting_position(
            sess, direction, atr, ema20, closes[-1],
            hmm_state, hmm_label, hmm_conf,
            vote_hmm, vote_ema, vote_momentum, score, client
        )


def _open_voting_position(
    sess, direction, atr, ema20, current_close,
    hmm_state, hmm_label, hmm_conf,
    vote_hmm, vote_ema, vote_momentum, score, client,
) -> None:
    is_buy   = direction == "BUY"
    tp_price = round(current_close + atr * sess.tp_atr_mult if is_buy else current_close - atr * sess.tp_atr_mult, 5)
    sl_price = round(current_close - atr * sess.sl_atr_mult if is_buy else current_close + atr * sess.sl_atr_mult, 5)

    payload = {
        "symbol":   sess.symbol,
        "action":   direction,
        "volume":   sess.volume,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "comment":  f"Smart:{sess.session_id[:8]}",
    }

    try:
        r = client.post(f"{PYTHON_API}/python/mt5/order", json=payload)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        sess.last_action = f"order HTTP error: {e}"
        return

    if not data.get("success"):
        sess.last_action = f"order FAILED {direction}: {data.get('retcode_desc','?')} (rc={data.get('retcode')})"
        return

    ticket      = data["order_id"]
    entry_price = data.get("price", current_close)

    sess.active_tickets.append(ticket)
    sess.total_opened += 1
    sess.last_action = f"opened {direction} ticket={ticket} TP={tp_price:.2f} SL={sl_price:.2f} score={score}"

    _log_open(sess, client, {
        "sessionId":      sess.session_id,
        "symbol":         sess.symbol,
        "direction":      direction,
        "directionScore": score,
        "atrValue":       atr,
        "ema20Value":     ema20,
        "hmmState":       hmm_state,
        "hmmStateLabel":  hmm_label,
        "hmmConfidence":  hmm_conf,
        "closePrice":     current_close,
        "spreadPips":     0.0,
        "voteHmm":        vote_hmm,
        "voteEma":        vote_ema,
        "voteMomentum":   vote_momentum,
        "entryPrice":     entry_price,
        "tpPrice":        tp_price,
        "slPrice":        sl_price,
        "tpAtrMult":      sess.tp_atr_mult,
        "slAtrMult":      sess.sl_atr_mult,
        "volume":         sess.volume,
        "mt5Ticket":      ticket,
        "aiEnabled":      False,
    })


# ── Position monitoring ────────────────────────────────────────────────────

def _check_closed_positions(sess: SmartSession, client: httpx.Client) -> None:
    if not sess.active_tickets:
        return
    try:
        all_positions = _get_positions(sess.symbol, client)
    except Exception as e:
        logger.warning("[SmartEngine] %s get_positions: %s", sess.session_id[:8], e)
        return

    open_tickets = {p["ticket"] for p in all_positions}
    closed = [t for t in sess.active_tickets if t not in open_tickets]

    for ticket in closed:
        sess.active_tickets.remove(ticket)
        exit_price, profit, outcome, reason = _fetch_close_info(ticket, client)
        if profit > 0:
            sess.total_closed_win  += 1
        elif profit < 0:
            sess.total_closed_loss += 1
        else:
            sess.total_closed_other += 1
        sess.total_profit += profit
        sess.last_action = f"ticket {ticket} closed {outcome} profit=${profit:.2f}"

        _log_close(sess, client, {
            "mt5Ticket":   ticket,
            "exitPrice":   exit_price,
            "profitUsd":   profit,
            "outcome":     outcome,
            "closeReason": reason,
        })


def _fetch_close_info(ticket: int, client: httpx.Client) -> tuple[float, float, str, str]:
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/deal-history?ticket={ticket}")
        if r.status_code == 200:
            d = r.json()
            if d:
                profit  = float(d.get("profit", 0.0))
                exit_p  = float(d.get("price",  0.0))
                outcome = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "BE")
                reason  = "SL/TP"
                return exit_p, profit, outcome, reason
    except Exception:
        pass
    return 0.0, 0.0, "UNKNOWN", "external"


# ── LLM Integration ────────────────────────────────────────────────────────

def _call_llm(user_prompt: str) -> tuple[Optional[dict], Optional[str]]:
    """Call Claude API. Returns (result_dict, error_message)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not set"

    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":       LLM_MODEL,
        "max_tokens":  512,
        "temperature": 0,
        "system":      _SYSTEM_PROMPT,
        "tools":       [_TRADING_TOOL],
        "tool_choice": {"type": "tool", "name": "make_trading_decision"},
        "messages":    [{"role": "user", "content": user_prompt}],
    }

    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as c:
            r = c.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            r.raise_for_status()
            resp = r.json()
    except httpx.TimeoutException:
        return None, "LLM timeout"
    except Exception as e:
        return None, f"LLM HTTP error: {e}"

    # Extract tool_use block
    content = resp.get("content", [])
    for block in content:
        if block.get("type") == "tool_use" and block.get("name") == "make_trading_decision":
            return block.get("input", {}), None

    return None, "LLM returned no tool_use block"


def _build_prompt(
    symbol, bars_m15, bars_h1, atr, ema20,
    hmm_state, hmm_label, hmm_conf,
    vote_hmm, vote_ema, vote_momentum, vote_score,
    open_count, max_layers, session_profit, session_name,
) -> str:
    current_price = bars_m15[-1]["close"] if bars_m15 else 0.0

    def fmt_bars(bars: list, n: int) -> str:
        rows = []
        for b in bars[-n:]:
            t = b.get("time", "")[:16]
            rows.append(
                f"  {t}  {b['open']:.2f}  {b['high']:.2f}  {b['low']:.2f}  {b['close']:.2f}"
            )
        return "\n".join(rows)

    vote_str = (
        f"HMM={'+' if vote_hmm>0 else ''}{vote_hmm}  "
        f"EMA={'+' if vote_ema>0 else ''}{vote_ema}  "
        f"MOM={'+' if vote_momentum>0 else ''}{vote_momentum}  "
        f"TOTAL={'+' if vote_score>0 else ''}{vote_score}"
    )

    return f"""=== TRADING ANALYSIS REQUEST ===
Instrument : {symbol}
Price      : {current_price:.5f}
Session    : {session_name}
Open Pos   : {open_count}/{max_layers}
Session P&L: ${session_profit:.2f}

=== H1 TREND CONTEXT (last 20 bars) ===
  Time              Open     High     Low      Close
{fmt_bars(bars_h1, 20)}

=== M15 ENTRY TIMING (last 50 bars) ===
  Time              Open     High     Low      Close
{fmt_bars(bars_m15, 50)}

=== INDICATORS (M15) ===
ATR(14)  : {atr:.5f}
EMA(20)  : {ema20:.5f}
HMM State: {hmm_state} ({hmm_label}) | Confidence: {hmm_conf:.2f}

=== VOTE SYSTEM SCORES ===
{vote_str}

Analyze the data above and call make_trading_decision with your structured decision."""


def _refresh_hour_window(sess: SmartSession) -> None:
    """Reset hourly call counter if window has elapsed."""
    if time.time() - sess.ai_hour_window_start >= 3600:
        sess.ai_calls_this_hour  = 0
        sess.ai_hour_window_start = time.time()


def _get_trading_session() -> str:
    """Return current trading session name based on UTC hour."""
    h = time.gmtime().tm_hour
    if 0 <= h < 8:
        return "Asia"
    elif 8 <= h < 13:
        return "London"
    elif 13 <= h < 17:
        return "London/NY Overlap"
    elif 17 <= h < 22:
        return "New York"
    return "Off-hours"


# ── Callbacks ──────────────────────────────────────────────────────────────

def _log_open(sess: SmartSession, client: httpx.Client, payload: dict) -> None:
    if not sess.callback_url:
        return
    try:
        r = client.post(f"{sess.callback_url}/open", json=payload)
        r.raise_for_status()
    except Exception as e:
        logger.warning("[SmartEngine] %s log/open: %s", sess.session_id[:8], e)


def _log_close(sess: SmartSession, client: httpx.Client, payload: dict) -> None:
    if not sess.callback_url:
        return
    try:
        r = client.post(f"{sess.callback_url}/close", json=payload)
        r.raise_for_status()
    except Exception as e:
        logger.warning("[SmartEngine] %s log/close: %s", sess.session_id[:8], e)


# ── MT5 / HMM helpers ─────────────────────────────────────────────────────

def _fetch_ohlc(symbol: str, timeframe: str, bars: int, client: httpx.Client) -> list[dict]:
    r = client.post(
        f"{PYTHON_API}/python/mt5/ohlc",
        json={"symbol": symbol, "timeframe": timeframe, "bars": bars}
    )
    r.raise_for_status()
    return r.json().get("bars", [])


def _classify_hmm(symbol: str, timeframe: str, client: httpx.Client) -> dict:
    r = client.post(
        f"{PYTHON_API}/python/hmm/classify",
        json={"instrument": symbol, "timeframe": timeframe, "lookback": 50}
    )
    r.raise_for_status()
    return r.json()


def _get_positions(symbol: str, client: httpx.Client) -> list[dict]:
    r = client.get(f"{PYTHON_API}/python/mt5/positions")
    r.raise_for_status()
    return [p for p in r.json() if p["symbol"].upper() == symbol.upper()]


# ── Technical indicators ───────────────────────────────────────────────────

def _calc_atr(highs, lows, closes, period=14) -> float:
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i-1]),
                       abs(lows[i]  - closes[i-1])))
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return round(atr, 6)


def _calc_ema(closes, period) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k   = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]:
        ema = c * k + ema * (1 - k)
    return round(ema, 6)


def _vote_hmm(label: str) -> int:
    low = label.lower()
    if any(kw in low for kw in _BULLISH_LABELS): return 1
    if any(kw in low for kw in _BEARISH_LABELS): return -1
    return 0


def _vote_momentum(closes, lookback=5) -> int:
    if len(closes) < lookback + 1: return 0
    d = closes[-1] - closes[-1 - lookback]
    return 1 if d > 0 else (-1 if d < 0 else 0)
