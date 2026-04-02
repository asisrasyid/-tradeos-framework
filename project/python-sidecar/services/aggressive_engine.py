"""
aggressive_engine.py — Aggressive Layer Trading Engine v2.1
============================================================

v2 redesign:
  - Direct MT5 API calls — no HTTP self-calls for order execution (eliminates 50-150ms overhead/order)
  - Broker-side TP — calculated from profit_target input, set at order placement
  - Poll interval 2s — detect TP hit fast (was 5s)
  - Direction logic:
      Priority 1: Daily S/R proximity → flip to bounce direction
      Priority 2: EMA20 on M5        → trend anchor
      Priority 3: flip_mode (counter/percentile) — backward compat
      Priority 4: keep current_direction
  - Manual close registry — mark_manual_close() prevents re-open
  - MCGuard + Profit Guard + per-position SL all preserved (direct MT5)

v2.1 restored features:
  - HMM Gate — danger detection via /python/analysis/multi-tf before each fill cycle
  - Auto Direction HMM — confidence-weighted M1+M5+M15 vote for AUTO direction resolution
  - Limit Orders — ATR-based pending BUY_LIMIT/SELL_LIMIT via mt5_executor.place_limit_order()
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import httpx

from services import equity_cache as _eq_cache
from services import mt5_executor

# Internal sidecar base URL — HMM analysis calls only (not order execution)
PYTHON_API = os.getenv("PYTHON_API_URL", "http://localhost:8001")

# ── MT5 direct import ─────────────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2   # seconds between position checks (v1 was 5)

# ── MT5 timeframe constants (same values as mt5.TIMEFRAME_*) ─────────────────
_TF_M1  = 1
_TF_M5  = 5
_TF_M15 = 15
_TF_D1  = 16408

# ── Manual close registry ─────────────────────────────────────────────────────
_manually_closed: set[int] = set()


def mark_manual_close(ticket: int) -> None:
    """
    Mark a ticket as manually closed by the user.
    Engine will skip re-open for this ticket when it detects the position gone.
    Called by the /python/aggressive/close-ticket endpoint.
    """
    _manually_closed.add(ticket)
    logger.info("[AggrEngine] Ticket #%d marked as manual close", ticket)


# ── Session state ──────────────────────────────────────────────────────────────

@dataclass
class AggressiveSession:
    session_id:    str
    symbol:        str
    direction:     str    # BUY | SELL | BOTH | AUTO
    layers:        int
    volume:        float
    profit_target: float  # USD — engine converts to broker TP price

    # ── Flip settings (backward compat) ──────────────────────────────────────
    flip_mode:       str   = "none"   # none | counter | percentile | hybrid
    flip_percentile: float = 0.80
    flip_after:      int   = 3
    lookback_bars:   int   = 20

    # ── MCGuard ───────────────────────────────────────────────────────────────
    mc_guard:             bool  = False
    mc_level_pct:         float = 0.10
    safety_multiplier:    float = 3.0
    emergency_multiplier: float = 1.5

    # ── Per-position SL ───────────────────────────────────────────────────────
    sl_loss_multiplier: float = 0.0   # 0 = disabled
    sl_cooldown_sec:    float = 0.0   # 0 = disabled
    sl_cooldown_until:  float = 0.0   # runtime epoch

    # ── Profit Guard ──────────────────────────────────────────────────────────
    max_session_loss_usd:   float = 0.0
    max_drawdown_from_peak: float = 0.0

    # ── Runtime state ──────────────────────────────────────────────────────────
    active:                  bool          = True
    active_tickets:          list          = field(default_factory=list)
    total_opened:            int           = 0
    total_closed_win:        int           = 0
    total_closed_other:      int           = 0
    total_closed_emergency:  int           = 0
    total_closed_sl:         int           = 0
    total_profit:            float         = 0.0
    started_at:              float         = field(default_factory=time.time)
    last_action:             str           = "starting"
    error:                   Optional[str] = None

    # ── HMM Gate — danger detection + condition-based wait ───────────────────
    hmm_gate_enabled:    bool  = False
    hmm_cooldown_sec:    float = 10.0   # re-check interval (seconds), NOT a wait timer
    hmm_in_danger:       bool  = False  # True = danger active, fills paused
    hmm_last_check:      float = 0.0   # epoch of last HMM API call
    hmm_cooldown_reason: str   = ""
    hmm_vote_last:       str   = ""

    # ── Auto Direction via HMM ─────────────────────────────────────────────
    auto_direction_hmm:  bool  = False

    # ── Limit Orders (pending) ─────────────────────────────────────────────
    limit_atr_mult:     float = 0.0
    pending_expiry_sec: float = 15.0
    pending_tickets:    list  = field(default_factory=list)
    pending_placed_at:  dict  = field(default_factory=dict)

    # ── Profit Guard runtime ───────────────────────────────────────────────────
    peak_profit:         float = 0.0
    floating_pnl:        float = 0.0
    next_recommendation: str   = ""

    # ── Watchdogs ──────────────────────────────────────────────────────────────
    consecutive_fill_failures:       int   = 0
    consecutive_connection_failures: int   = 0
    stopped_at:                      float = 0.0

    # ── Direction / flip tracking ──────────────────────────────────────────────
    current_direction: str = ""
    consecutive_tp:    int = 0
    total_flips:       int = 0

    # ── MCGuard status ─────────────────────────────────────────────────────────
    mc_status: str = "OK"

    def __post_init__(self):
        if not self.current_direction:
            # AUTO and BOTH resolved later; BUY/SELL set immediately
            if self.direction not in ("AUTO", "BOTH"):
                self.current_direction = self.direction
            else:
                self.current_direction = "BUY"   # will be overridden at start


_sessions: dict[str, AggressiveSession] = {}
_threads:  dict[str, threading.Thread]  = {}


# ── Public API ─────────────────────────────────────────────────────────────────

def start_session(
    symbol:               str,
    direction:            str,
    layers:               int   = 10,
    volume:               float = 0.01,
    profit_target:        float = 0.5,
    sl_pips:              float = 0.0,   # kept for API compat, not used
    tp_pips:              float = 0.0,   # kept for API compat, replaced by profit_target
    flip_mode:            str   = "none",
    flip_percentile:      float = 0.80,
    flip_after:           int   = 3,
    lookback_bars:        int   = 20,
    trend_guided:         bool  = True,   # kept for API compat
    mc_guard:             bool  = False,
    mc_level_pct:         float = 0.10,
    safety_multiplier:    float = 3.0,
    emergency_multiplier: float = 1.5,
    sl_loss_multiplier:     float = 0.0,
    sl_cooldown_sec:        float = 0.0,
    max_session_loss_usd:   float = 0.0,
    max_drawdown_from_peak: float = 0.0,
    hmm_gate_enabled:       bool  = False,
    hmm_cooldown_sec:       float = 60.0,
    auto_direction_hmm:     bool  = False,
    limit_atr_mult:         float = 0.0,
    pending_expiry_sec:     float = 15.0,
) -> str:
    session_id = str(uuid.uuid4())
    sess = AggressiveSession(
        session_id           = session_id,
        symbol               = symbol,
        direction            = direction.upper(),
        layers               = layers,
        volume               = volume,
        profit_target        = profit_target,
        flip_mode            = flip_mode.lower(),
        flip_percentile      = flip_percentile,
        flip_after           = flip_after,
        lookback_bars        = max(5, lookback_bars),
        mc_guard             = mc_guard,
        mc_level_pct         = mc_level_pct,
        safety_multiplier    = safety_multiplier,
        emergency_multiplier = emergency_multiplier,
        sl_loss_multiplier   = sl_loss_multiplier,
        sl_cooldown_sec      = sl_cooldown_sec,
        max_session_loss_usd    = max_session_loss_usd,
        max_drawdown_from_peak  = max_drawdown_from_peak,
        hmm_gate_enabled        = hmm_gate_enabled,
        hmm_cooldown_sec        = hmm_cooldown_sec,
        auto_direction_hmm      = auto_direction_hmm,
        limit_atr_mult          = limit_atr_mult,
        pending_expiry_sec      = pending_expiry_sec,
    )
    _sessions[session_id] = sess

    t = threading.Thread(
        target=_run_session, args=(sess,),
        daemon=True, name=f"aggr-{session_id[:8]}",
    )
    t.start()
    _threads[session_id] = t

    logger.info(
        "[AggrEngine] Started %s | %s %s ×%d vol=%.2f target=$%.2f "
        "flip=%s mc_guard=%s sl_mult=%.1f",
        session_id[:8], symbol, direction, layers, volume, profit_target,
        flip_mode, mc_guard, sl_loss_multiplier,
    )
    return session_id


def stop_session(session_id: str) -> bool:
    sess = _sessions.get(session_id)
    if sess is None:
        return False
    sess.active = False
    logger.info("[AggrEngine] Stop requested: %s", session_id[:8])
    return True


def get_all_status() -> list[dict]:
    return [
        {
            "session_id":           s.session_id,
            "symbol":               s.symbol,
            "direction":            s.direction,
            "current_direction":    s.current_direction,
            "layers":               s.layers,
            "volume":               s.volume,
            "profit_target":        s.profit_target,
            "flip_mode":            s.flip_mode,
            "flip_percentile":      s.flip_percentile,
            "flip_after":           s.flip_after,
            "lookback_bars":        s.lookback_bars,
            "mc_guard":             s.mc_guard,
            "mc_level_pct":         s.mc_level_pct,
            "safety_multiplier":    s.safety_multiplier,
            "emergency_multiplier": s.emergency_multiplier,
            "mc_status":            s.mc_status,
            "sl_loss_multiplier":     s.sl_loss_multiplier,
            "sl_cooldown_sec":        s.sl_cooldown_sec,
            "sl_cooldown_remaining":  max(0.0, round(s.sl_cooldown_until - time.time(), 1))
                                      if s.sl_cooldown_sec > 0 else 0.0,
            "max_session_loss_usd":   s.max_session_loss_usd,
            "max_drawdown_from_peak": s.max_drawdown_from_peak,
            "peak_profit":            round(s.peak_profit, 2),
            "floating_pnl":           round(s.floating_pnl, 2),
            "total_net":              round(s.total_profit + s.floating_pnl, 2),
            "next_recommendation":    s.next_recommendation,
            "consecutive_fill_failures":       s.consecutive_fill_failures,
            "consecutive_connection_failures": s.consecutive_connection_failures,
            "consecutive_tp":  s.consecutive_tp,
            "total_flips":     s.total_flips,
            "hmm_gate_enabled":       s.hmm_gate_enabled,
            "hmm_cooldown_sec":       s.hmm_cooldown_sec,
            "hmm_in_danger":          s.hmm_in_danger,
            "hmm_recheck_in":         max(0.0, round(
                                          s.hmm_cooldown_sec - (time.time() - s.hmm_last_check), 1
                                      )) if s.hmm_in_danger else 0.0,
            "hmm_cooldown_reason":    s.hmm_cooldown_reason,
            "hmm_vote_last":          s.hmm_vote_last,
            "auto_direction_hmm":     s.auto_direction_hmm,
            "limit_atr_mult":         s.limit_atr_mult,
            "pending_expiry_sec":     s.pending_expiry_sec,
            "pending_orders":         len(s.pending_tickets),
            "active":          s.active,
            "active_tickets":  list(s.active_tickets),
            "open_positions":  len(s.active_tickets),
            "total_opened":         s.total_opened,
            "total_closed_win":     s.total_closed_win,
            "total_closed_other":   s.total_closed_other,
            "total_closed_sl":        s.total_closed_sl,
            "total_closed_emergency": s.total_closed_emergency,
            "total_profit":    round(s.total_profit, 2),
            "last_action":     s.last_action,
            "error":           s.error,
            "uptime_s":        int(time.time() - s.started_at),
        }
        for s in _sessions.values()
    ]


# ── Cleanup loop ───────────────────────────────────────────────────────────────

_MAX_FILL_FAILURES       = 5
_MAX_CONNECTION_FAILURES = 5
_FILL_BACKOFF_S          = [0, 10, 30, 60, 60]
_CLEANUP_INTERVAL_S      = 300
_CLEANUP_RETAIN_S        = 1800


def _cleanup_loop() -> None:
    while True:
        time.sleep(_CLEANUP_INTERVAL_S)
        cutoff  = time.time() - _CLEANUP_RETAIN_S
        expired = [
            sid for sid, s in list(_sessions.items())
            if not s.active and s.stopped_at > 0 and s.stopped_at < cutoff
        ]
        for sid in expired:
            _sessions.pop(sid, None)
            _threads.pop(sid, None)
        if expired:
            logger.info("[AggrEngine] Cleaned %d expired sessions", len(expired))


_cleanup_thread = threading.Thread(
    target=_cleanup_loop, daemon=True, name="aggr-cleanup"
)
_cleanup_thread.start()


# ── Core session loop ──────────────────────────────────────────────────────────

def _run_session(sess: AggressiveSession) -> None:
    logger.info("[AggrEngine] Thread start %s | %s %s ×%d",
                sess.session_id[:8], sess.symbol, sess.direction, sess.layers)
    try:
        # ── AUTO direction: resolve from HMM vote or Daily S/R + EMA20 M5 ──────
        if sess.direction == "AUTO":
            if sess.auto_direction_hmm:
                sess.last_action = "AUTO: analyzing HMM M1+M5+M15 vote..."
            else:
                sess.last_action = "AUTO: analyzing Daily S/R + EMA20 M5..."
            resolved = "NEUTRAL"
            for attempt in range(6):   # retry up to ~30s
                if sess.auto_direction_hmm:
                    resolved = _hmm_vote(sess.symbol)
                else:
                    resolved = _decide_direction(sess)
                if resolved != "NEUTRAL":
                    break
                logger.info(
                    "[AggrEngine] %s AUTO NEUTRAL (attempt %d/6) — retry in 5s",
                    sess.session_id[:8], attempt + 1,
                )
                time.sleep(5)
                if not sess.active:
                    return

            if resolved == "NEUTRAL":
                sess.error  = "AUTO: direction still NEUTRAL after 30s — session stopped"
                sess.active = False
                logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.error)
                return

            sess.current_direction = resolved
            sess.last_action = f"AUTO resolved → {resolved}"
            logger.info("[AggrEngine] %s AUTO direction: %s", sess.session_id[:8], resolved)

        # ── Initial fill ──────────────────────────────────────────────────────
        _fill_layers(sess)

        # ── Main poll loop ────────────────────────────────────────────────────
        while sess.active:
            time.sleep(POLL_INTERVAL)
            if not sess.active:
                break
            _poll_and_manage(sess)

    except Exception as exc:
        logger.error("[AggrEngine] Session %s crashed: %s", sess.session_id[:8], exc)
        sess.error = str(exc)
    finally:
        sess.active     = False
        sess.stopped_at = time.time()
        try:
            sess.next_recommendation = _ema20_m5_trend(sess.symbol)
        except Exception:
            sess.next_recommendation = "NEUTRAL"
        logger.info(
            "[AggrEngine] Session %s ended | opened=%d wins=%d sl=%d profit=$%.2f flips=%d",
            sess.session_id[:8], sess.total_opened, sess.total_closed_win,
            sess.total_closed_sl, sess.total_profit, sess.total_flips,
        )


# ── Fill layers ────────────────────────────────────────────────────────────────

def _fill_layers(sess: AggressiveSession) -> None:
    """Open positions up to sess.layers. Called at session start and after TP detection."""
    # SL cooldown: pause re-opens after SL events
    if sess.sl_cooldown_sec > 0 and time.time() < sess.sl_cooldown_until:
        remaining = int(sess.sl_cooldown_until - time.time())
        sess.last_action = f"SL cooldown: {remaining}s remaining"
        return

    needed = sess.layers - len(sess.active_tickets) - len(sess.pending_tickets)
    if needed <= 0:
        return

    # ── HMM Gate: condition-based danger wait ────────────────────────────────
    # hmm_cooldown_sec = re-check interval (not a timer duration)
    # Flow: danger detected → pause fills → re-check every N sec
    #       → HMM clears → resume immediately in this same cycle
    if sess.hmm_gate_enabled:
        now = time.time()

        if sess.hmm_in_danger:
            # Still in danger state — check if it's time to re-check
            since_last = now - sess.hmm_last_check
            if since_last < sess.hmm_cooldown_sec:
                recheck_in = int(sess.hmm_cooldown_sec - since_last)
                sess.last_action = (
                    f"HMM danger — re-check in {recheck_in}s "
                    f"({sess.hmm_cooldown_reason})"
                )
                return  # not time yet, skip fill

            # Time to re-check
            sess.hmm_last_check = now
            vote = _hmm_vote(sess.symbol)
            sess.hmm_vote_last = vote

            opposite = "SELL" if sess.current_direction == "BUY" else "BUY"
            if vote != opposite:
                # Danger cleared (vote neutral or confirms direction)
                sess.hmm_in_danger       = False
                sess.hmm_cooldown_reason = ""
                sess.last_action = (
                    f"HMM cleared (vote={vote}) — resuming fills"
                )
                logger.info("[AggrEngine] %s HMM danger cleared, vote=%s",
                            sess.session_id[:8], vote)
                # Fall through — fill immediately this cycle
            else:
                sess.last_action = (
                    f"HMM still dangerous (vote={vote}) — "
                    f"re-check in {int(sess.hmm_cooldown_sec)}s"
                )
                return  # still dangerous

        else:
            # Not in danger — pre-fill check (rate-limited by hmm_cooldown_sec)
            if now - sess.hmm_last_check >= sess.hmm_cooldown_sec:
                sess.hmm_last_check = now
                danger, reason = _hmm_danger_check(sess.symbol, sess.current_direction)
                if danger:
                    sess.hmm_in_danger       = True
                    sess.hmm_cooldown_reason = reason
                    sess.last_action = (
                        f"HMM GATE ⚠ {reason} — pausing fills, "
                        f"re-check in {int(sess.hmm_cooldown_sec)}s"
                    )
                    logger.warning("[AggrEngine] %s HMM gate: %s (recheck=%.0fs)",
                                   sess.session_id[:8], reason, sess.hmm_cooldown_sec)
                    return

    opened_this_cycle = 0

    for i in range(needed):
        if not sess.active:
            break

        # MCGuard check before each order
        if sess.mc_guard:
            mc = _check_mc_guard(sess)
            sess.mc_status = mc
            if mc in ("CAUTION", "WARNING", "DANGER", "EMERGENCY"):
                sess.last_action = f"MCGuard {mc} — fill blocked"
                break

        # Direction: BOTH alternates BUY/SELL; others use current_direction
        if sess.direction == "BOTH":
            d = "BUY" if len(sess.active_tickets) % 2 == 0 else "SELL"
        else:
            d = sess.current_direction

        # Limit order mode vs market order mode
        if sess.limit_atr_mult > 0:
            ticket = _open_limit_position(sess, d)
            if ticket:
                sess.pending_tickets.append(ticket)
                sess.pending_placed_at[ticket] = time.time()
                opened_this_cycle += 1
                sess.consecutive_fill_failures = 0
            else:
                sess.consecutive_fill_failures += 1
            continue  # don't go through market order path

        # Market order path
        ticket = _open_one_position(sess, d)
        if ticket:
            opened_this_cycle += 1
            sess.consecutive_fill_failures = 0
        else:
            sess.consecutive_fill_failures += 1
            backoff = _FILL_BACKOFF_S[
                min(sess.consecutive_fill_failures - 1, len(_FILL_BACKOFF_S) - 1)
            ]
            logger.warning(
                "[AggrEngine] %s fill failure %d/%d (backoff=%ds)",
                sess.session_id[:8], sess.consecutive_fill_failures,
                _MAX_FILL_FAILURES, backoff,
            )
            if backoff > 0:
                time.sleep(backoff)
            if sess.consecutive_fill_failures >= _MAX_FILL_FAILURES:
                sess.last_action = (
                    f"AUTO-STOP: {sess.consecutive_fill_failures} consecutive fill failures"
                )
                logger.error("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
                sess.active = False
            break


# ── Poll & manage ──────────────────────────────────────────────────────────────

def _poll_and_manage(sess: AggressiveSession) -> None:
    """
    Main polling function (called every POLL_INTERVAL seconds).
    Detects broker TP hits and manual closes, then re-fills as needed.
    """
    # ── MCGuard — top priority ────────────────────────────────────────────────
    if sess.mc_guard:
        mc = _check_mc_guard(sess)
        sess.mc_status = mc

        if mc == "EMERGENCY":
            if _eq_cache.claim_emergency_action():
                sess.last_action = "MCGuard EMERGENCY — closing ALL positions"
                _close_all_emergency_direct(sess)
            else:
                sess.last_action = "MCGuard EMERGENCY — another session acting, stopping"
            sess.active = False
            return

        if mc == "DANGER":
            sess.last_action = "MCGuard DANGER — closing 3 worst positions"
            _close_worst_positions_direct(sess, 3)
            return   # skip fill this cycle

    # ── Get positions directly from MT5 ───────────────────────────────────────
    try:
        positions = _get_positions_direct(sess.symbol)
        sess.consecutive_connection_failures = 0
    except Exception as e:
        sess.consecutive_connection_failures += 1
        logger.warning(
            "[AggrEngine] %s get_positions failed (%d/%d): %s",
            sess.session_id[:8], sess.consecutive_connection_failures,
            _MAX_CONNECTION_FAILURES, e,
        )
        if sess.consecutive_connection_failures >= _MAX_CONNECTION_FAILURES:
            sess.error  = f"MT5 connection lost after {_MAX_CONNECTION_FAILURES} failures"
            sess.active = False
        return

    open_tickets = {p["ticket"] for p in positions}

    # ── Pending order management: detect fills + expiry cancellation ──────────
    if sess.pending_tickets:
        _check_pending_orders(sess, open_tickets)

    # ── Profit Guard ──────────────────────────────────────────────────────────
    if _check_profit_guard(sess, positions):
        _close_all_emergency_direct(sess)
        sess.active = False
        return

    # ── Per-position SL (if enabled) ──────────────────────────────────────────
    sl_happened = False
    if sess.sl_loss_multiplier > 0:
        sl_before = sess.total_closed_sl
        _check_sl_conditions(sess, positions)
        sl_happened = sess.total_closed_sl > sl_before
        if sl_happened and sess.sl_cooldown_sec > 0:
            sess.sl_cooldown_until = time.time() + sess.sl_cooldown_sec
            logger.info("[AggrEngine] %s SL cooldown started: %.0fs",
                        sess.session_id[:8], sess.sl_cooldown_sec)
        if sl_happened:
            try:
                positions    = _get_positions_direct(sess.symbol)
                open_tickets = {p["ticket"] for p in positions}
            except Exception:
                pass

    # ── Detect closed tickets: broker TP or manual close ─────────────────────
    closed_tickets = [t for t in sess.active_tickets if t not in open_tickets]
    tp_count = 0

    for ticket in closed_tickets:
        sess.active_tickets.remove(ticket)

        if ticket in _manually_closed:
            _manually_closed.discard(ticket)
            sess.last_action = f"#{ticket} closed manually — no re-open"
            logger.info("[AggrEngine] %s manual close #%d", sess.session_id[:8], ticket)
            continue

        # Broker TP hit — decide direction then re-fill
        tp_count += 1
        sess.total_closed_win += 1
        sess.consecutive_tp   += 1
        logger.info("[AggrEngine] %s broker TP hit #%d (total wins=%d)",
                    sess.session_id[:8], ticket, sess.total_closed_win)

        # Decide new direction: HMM vote (if enabled) else S/R + EMA20
        if sess.direction not in ("BOTH",):
            if sess.auto_direction_hmm:
                hmm_dir = _hmm_vote(sess.symbol)
                new_dir = hmm_dir if hmm_dir != "NEUTRAL" else _decide_direction(sess)
            else:
                new_dir = _decide_direction(sess)
            if new_dir != sess.current_direction:
                _do_flip(sess, f"→ {new_dir}")

    # ── Re-fill: always attempt — _fill_layers guards against over-fill.
    # Unconditional call ensures HMM Gate re-check runs on its own interval
    # even when active_tickets is empty (no TP/SL to trigger it). Without
    # this, hmm_in_danger=True with zero open positions causes a permanent
    # deadlock — fills never resume.
    _fill_layers(sess)

    # ── Update floating PnL for status display ────────────────────────────────
    our_tickets   = set(sess.active_tickets)
    sess.floating_pnl = round(
        sum(float(p.get("profit", 0)) for p in positions if p.get("ticket") in our_tickets),
        2,
    )


# ── Direction decision ─────────────────────────────────────────────────────────

def _decide_direction(sess: AggressiveSession) -> str:
    """
    Decide re-open direction using layered priority:
      P1: Daily S/R proximity  → flip to bounce direction
      P2: EMA20 M5 trend       → follow trend anchor
      P3: flip_mode logic      → backward compat (counter / percentile)
      P4: keep current_direction
    """
    # P1: Daily S/R
    sr_dir = _check_daily_sr(sess.symbol)
    if sr_dir and sr_dir != sess.current_direction:
        logger.info("[AggrEngine] %s P1 Daily S/R → %s",
                    sess.session_id[:8], sr_dir)
        return sr_dir

    # P2: EMA20 M5 trend
    trend = _ema20_m5_trend(sess.symbol)
    if trend != "NEUTRAL":
        if trend != sess.current_direction:
            logger.info("[AggrEngine] %s P2 EMA20 M5 → %s",
                        sess.session_id[:8], trend)
        return trend

    # P3: flip_mode (counter / percentile / hybrid) — backward compat
    if sess.flip_mode == "counter":
        if sess.consecutive_tp >= sess.flip_after:
            new_dir = "SELL" if sess.current_direction == "BUY" else "BUY"
            sess.consecutive_tp = 0
            return new_dir

    elif sess.flip_mode == "percentile":
        pct = _get_price_percentile_direct(sess)
        if pct is not None:
            if sess.current_direction == "BUY"  and pct >= sess.flip_percentile:
                return "SELL"
            if sess.current_direction == "SELL" and pct <= (1.0 - sess.flip_percentile):
                return "BUY"

    elif sess.flip_mode == "hybrid":
        should_flip = sess.consecutive_tp >= sess.flip_after
        if not should_flip:
            pct = _get_price_percentile_direct(sess)
            if pct is not None:
                if sess.current_direction == "BUY"  and pct >= sess.flip_percentile:
                    should_flip = True
                if sess.current_direction == "SELL" and pct <= (1.0 - sess.flip_percentile):
                    should_flip = True
        if should_flip:
            sess.consecutive_tp = 0
            return "SELL" if sess.current_direction == "BUY" else "BUY"

    # P4: keep current
    return sess.current_direction


def _do_flip(sess: AggressiveSession, reason: str) -> None:
    new_dir = "SELL" if sess.current_direction == "BUY" else "BUY"
    logger.info("[AggrEngine] %s FLIP %s → %s | %s",
                sess.session_id[:8], sess.current_direction, new_dir, reason)
    sess.current_direction = new_dir
    sess.consecutive_tp    = 0
    sess.total_flips      += 1
    sess.last_action       = f"flipped → {new_dir} ({reason})"


# ── Daily S/R check ────────────────────────────────────────────────────────────

def _check_daily_sr(symbol: str) -> Optional[str]:
    """
    Check if current price is near a daily S/R level.

    Levels checked:
      PDH — Previous Day High  → resistance → expect SELL bounce
      PDL — Previous Day Low   → support    → expect BUY bounce
      CDH — Current Day High   → resistance → expect SELL bounce
      CDL — Current Day Low    → support    → expect BUY bounce

    Proximity tolerance = 0.5 × ATR(M5, 14).

    Returns:
      "SELL" — near resistance (bounce down expected)
      "BUY"  — near support (bounce up expected)
      None   — price clear of all daily levels
    """
    try:
        if not _MT5_AVAILABLE or not mt5_executor.ensure_connected():
            return None

        # 3 D1 bars: [-3]=2 days ago, [-2]=yesterday, [-1]=today
        bars_d1 = mt5.copy_rates_from_pos(symbol, _TF_D1, 0, 3)
        if bars_d1 is None or len(bars_d1) < 2:
            return None

        PDH = float(bars_d1[-2]["high"])   # Previous Day High
        PDL = float(bars_d1[-2]["low"])    # Previous Day Low
        CDH = float(bars_d1[-1]["high"])   # Current Day High (so far)
        CDL = float(bars_d1[-1]["low"])    # Current Day Low (so far)

        # Tolerance = 0.5 × ATR(M5) for intraday precision
        atr = _calc_atr_direct(symbol, _TF_M5, period=14, n_bars=20)
        if atr <= 0:
            return None
        tolerance = atr * 0.5

        # Mid price for proximity check
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        price = (tick.ask + tick.bid) / 2.0

        # Resistance levels → SELL (expect bounce down)
        for level in (PDH, CDH):
            if abs(price - level) <= tolerance:
                logger.info(
                    "[AggrEngine] Daily S/R: %.5f near resistance %.5f (tol=%.5f) → SELL",
                    price, level, tolerance,
                )
                return "SELL"

        # Support levels → BUY (expect bounce up)
        for level in (PDL, CDL):
            if abs(price - level) <= tolerance:
                logger.info(
                    "[AggrEngine] Daily S/R: %.5f near support %.5f (tol=%.5f) → BUY",
                    price, level, tolerance,
                )
                return "BUY"

        return None   # price clear of all daily levels

    except Exception as e:
        logger.warning("[AggrEngine] _check_daily_sr error: %s", e)
        return None


# ── EMA20 M5 trend ─────────────────────────────────────────────────────────────

def _ema20_m5_trend(symbol: str) -> str:
    """
    Trend direction using EMA20 on M5 bars (100 min window — stable anchor).
    0.01% buffer prevents oscillation on flat market.
    Returns: "BUY" | "SELL" | "NEUTRAL"
    """
    try:
        if not _MT5_AVAILABLE or not mt5_executor.ensure_connected():
            return "NEUTRAL"
        bars = mt5.copy_rates_from_pos(symbol, _TF_M5, 0, 30)
        if bars is None or len(bars) < 22:
            return "NEUTRAL"
        closes  = [float(b["close"]) for b in bars]
        ema20   = _calc_ema(closes, 20)
        current = closes[-1]
        if current > ema20 * 1.0001:
            return "BUY"
        if current < ema20 * 0.9999:
            return "SELL"
        return "NEUTRAL"
    except Exception as e:
        logger.warning("[AggrEngine] _ema20_m5_trend error: %s", e)
        return "NEUTRAL"


# ── Open one position (with broker TP) ─────────────────────────────────────────

def _open_one_position(sess: AggressiveSession, direction: str) -> Optional[int]:
    """
    Place a market order and set broker TP calculated from sess.profit_target.

    Flow:
      1. Get current price (ask/bid)
      2. Calculate TP price: fill_price ± (profit_target / (volume × contract_size))
      3. Place order with TP embedded (one API call to MT5)
      4. If actual fill differs from pre-calc price, modify TP (best-effort)

    Returns ticket on success, None on failure.
    """
    if not mt5_executor.is_available():
        logger.warning("[AggrEngine] %s MT5 not available", sess.session_id[:8])
        return None

    try:
        # Pre-calculate TP from current price estimate
        sym_info = mt5_executor.get_symbol_info(sess.symbol)
        if sym_info is None:
            logger.warning("[AggrEngine] %s symbol info unavailable", sess.session_id[:8])
            return None

        est_price = sym_info["ask"] if direction == "BUY" else sym_info["bid"]
        est_tp    = mt5_executor.calc_tp_price(
            symbol        = sess.symbol,
            action        = direction,
            fill_price    = est_price,
            profit_target = sess.profit_target,
            volume        = sess.volume,
        )

        # Place market order with TP set
        result = mt5_executor.place_order(
            symbol   = sess.symbol,
            action   = direction,
            volume   = sess.volume,
            tp_price = est_tp,
            comment  = f"Aggr:{sess.session_id[:8]}",
        )

        if not result["success"]:
            logger.warning(
                "[AggrEngine] %s order rejected retcode=%d",
                sess.session_id[:8], result["retcode"],
            )
            return None

        ticket     = result["order_id"]
        fill_price = result["fill_price"]

        # Recalculate TP from actual fill price (handles slippage)
        actual_tp = mt5_executor.calc_tp_price(
            symbol        = sess.symbol,
            action        = direction,
            fill_price    = fill_price,
            profit_target = sess.profit_target,
            volume        = sess.volume,
        )

        # Modify TP if actual fill differs from estimate (best-effort, non-blocking)
        if abs(actual_tp - est_tp) > 1e-5:
            _modify_position_tp(sess.symbol, ticket, actual_tp)

        sess.active_tickets.append(ticket)
        sess.total_opened += 1
        sess.last_action   = (
            f"open {direction} #{ticket} @{fill_price:.5f} TP={actual_tp:.5f}"
        )
        logger.info(
            "[AggrEngine] %s opened %s #%d @%.5f TP=%.5f ($%.2f target)",
            sess.session_id[:8], direction, ticket,
            fill_price, actual_tp, sess.profit_target,
        )
        return ticket

    except Exception as e:
        sess.last_action = f"open {direction} error: {e}"
        logger.error("[AggrEngine] %s _open_one_position: %s", sess.session_id[:8], e)
        return None


def _modify_position_tp(symbol: str, ticket: int, tp_price: float) -> None:
    """Modify TP of an open position. Best-effort — errors logged, not raised."""
    try:
        if not _MT5_AVAILABLE:
            return
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return
        pos      = positions[0]
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   symbol,
            "position": ticket,
            "sl":       pos.sl,
            "tp":       round(tp_price, sym_info.digits),
        }
        mt5.order_send(request)
    except Exception as e:
        logger.warning("[AggrEngine] _modify_position_tp #%d: %s", ticket, e)


# ── Get positions (direct) ─────────────────────────────────────────────────────

def _get_positions_direct(symbol: str) -> list[dict]:
    """Fetch open positions for symbol directly from MT5 API (no HTTP)."""
    if not _MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 not available")
    if not mt5_executor.ensure_connected():
        raise RuntimeError("MT5 not connected")

    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []

    return [
        {
            "ticket":     int(p.ticket),
            "symbol":     p.symbol,
            "type":       "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume":     p.volume,
            "open_price": p.price_open,
            "profit":     p.profit,
            "sl":         p.sl,
            "tp":         p.tp,
        }
        for p in positions
    ]


# ── Emergency & danger close (direct) ─────────────────────────────────────────

def _close_all_emergency_direct(sess: AggressiveSession) -> None:
    """EMERGENCY: close all session positions directly via MT5 (no HTTP)."""
    closed = 0
    for ticket in list(sess.active_tickets):
        result = mt5_executor.close_position_direct(ticket, comment="AggrEmergency")
        if result.get("success"):
            sess.active_tickets.remove(ticket)
            sess.total_closed_emergency += 1
            sess.total_profit           += result.get("profit", 0.0)
            closed += 1
        else:
            logger.error(
                "[AggrEngine] %s emergency close #%d failed: %s",
                sess.session_id[:8], ticket, result.get("error", "unknown"),
            )
    sess.floating_pnl = 0.0
    logger.warning("[AggrEngine] %s EMERGENCY closed %d positions",
                   sess.session_id[:8], closed)


def _close_worst_positions_direct(sess: AggressiveSession, n: int) -> None:
    """DANGER: close the N most losing session positions directly."""
    try:
        positions = _get_positions_direct(sess.symbol)
        our_pos   = sorted(
            [p for p in positions if p["ticket"] in sess.active_tickets],
            key=lambda p: float(p.get("profit", 0)),
        )
        for pos in our_pos[:n]:
            ticket = pos["ticket"]
            result = mt5_executor.close_position_direct(ticket, comment="AggrDanger")
            if result.get("success") and ticket in sess.active_tickets:
                sess.active_tickets.remove(ticket)
                sess.total_closed_other += 1
                logger.warning(
                    "[AggrEngine] %s DANGER closed #%d profit=$%.2f",
                    sess.session_id[:8], ticket, pos.get("profit", 0),
                )
    except Exception as e:
        logger.error("[AggrEngine] _close_worst_positions_direct: %s", e)


# ── Per-position SL (direct) ───────────────────────────────────────────────────

def _check_sl_conditions(sess: AggressiveSession, positions: list[dict]) -> None:
    """
    Hard SL: close position immediately when floating_loss >= sl_loss_multiplier × profit_target.
    Direct MT5 call — no HTTP.
    """
    threshold = sess.sl_loss_multiplier * sess.profit_target

    for pos in positions:
        ticket = pos.get("ticket")
        if ticket not in sess.active_tickets:
            continue
        profit = float(pos.get("profit", 0.0))
        if profit >= 0:
            continue

        floating_loss = abs(profit)
        if floating_loss < threshold:
            continue

        logger.warning(
            "[AggrEngine] %s Hard SL #%d loss=$%.2f >= threshold=$%.2f — closing",
            sess.session_id[:8], ticket, floating_loss, threshold,
        )
        result = mt5_executor.close_position_direct(ticket, comment="AggrSL")
        if result.get("success") and ticket in sess.active_tickets:
            sess.active_tickets.remove(ticket)
            sess.total_closed_sl  += 1
            sess.total_profit     += profit   # negative value = realized loss
            sess.last_action       = f"Hard SL #{ticket} -${floating_loss:.2f}"


# ── MCGuard ────────────────────────────────────────────────────────────────────

def _check_mc_guard(sess: AggressiveSession) -> str:
    """Read shared equity snapshot and return guard level. Uses equity_cache (no HTTP)."""
    snap        = _eq_cache.get_equity_snapshot()
    balance     = snap["balance"]
    equity      = snap["equity"]
    free_margin = snap["free_margin"]

    if balance <= 0:
        return "OK"   # fail-open if cache not yet populated

    mc_level        = balance * sess.mc_level_pct
    safety_floor    = mc_level * sess.safety_multiplier
    emergency_floor = mc_level * sess.emergency_multiplier

    if equity      <= emergency_floor:     return "EMERGENCY"
    if free_margin <= mc_level:            return "DANGER"
    if free_margin <= safety_floor:        return "WARNING"
    if free_margin <= safety_floor * 1.5:  return "CAUTION"
    return "OK"


# ── Profit Guard ───────────────────────────────────────────────────────────────

def _check_profit_guard(sess: AggressiveSession, positions: list[dict]) -> bool:
    """
    Two-layer session net P&L protection:
      Floor:    stop if total_net <= -max_session_loss_usd
      Drawdown: stop if total_net < peak_profit - max_drawdown_from_peak
    Returns True if triggered (caller must close all and stop).
    """
    if sess.max_session_loss_usd <= 0 and sess.max_drawdown_from_peak <= 0:
        return False

    our_tickets = set(sess.active_tickets)
    floating    = sum(
        float(p.get("profit", 0))
        for p in positions
        if p.get("ticket") in our_tickets
    )
    sess.floating_pnl = round(floating, 2)
    total_net         = sess.total_profit + floating

    # Track peak only after first realized profit (prevents phantom peak)
    if sess.total_profit > 0 and total_net > sess.peak_profit:
        sess.peak_profit = total_net

    if sess.max_session_loss_usd > 0 and total_net <= -sess.max_session_loss_usd:
        sess.last_action = (
            f"PROFIT GUARD (floor): net=${total_net:.2f} ≤ "
            f"-${sess.max_session_loss_usd:.2f} → stopping"
        )
        logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
        return True

    if sess.max_drawdown_from_peak > 0 and sess.peak_profit > 0:
        if total_net < sess.peak_profit - sess.max_drawdown_from_peak:
            sess.last_action = (
                f"PROFIT GUARD (drawdown): dropped "
                f"${sess.peak_profit - total_net:.2f} from peak=${sess.peak_profit:.2f} → stopping"
            )
            logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
            return True

    return False


# ── HMM helpers (HTTP to analysis endpoint) ───────────────────────────────────

def _hmm_vote(symbol: str) -> str:
    """
    Query M1+M5+M15 HMM analysis and return confidence-weighted direction.
    Scoring: sum confidence per action; if ≥65% weight on one side → that direction.
    Used for: AUTO direction resolution (auto_direction_hmm=True) + cooldown-break vote.
    Returns: "BUY" | "SELL" | "NEUTRAL"
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{PYTHON_API}/python/analysis/multi-tf",
                json={"instrument": symbol, "timeframes": ["M5", "M15"]},
            )
            resp.raise_for_status()
            alerts = resp.json()

        buy_score = sell_score = 0.0
        for alert in alerts:
            action     = alert.get("action", "NEUTRAL")
            confidence = float(alert.get("confidence", 0.0))
            if action == "BUY":
                buy_score  += confidence
            elif action == "SELL":
                sell_score += confidence

        total = buy_score + sell_score
        if total < 0.5:
            return "NEUTRAL"
        ratio = buy_score / total
        if ratio >= 0.65:
            return "BUY"
        if ratio <= 0.35:
            return "SELL"
        return "NEUTRAL"
    except Exception as exc:
        logger.warning("[AggrEngine] _hmm_vote failed (fail-open): %s", exc)
        return "NEUTRAL"


def _hmm_danger_check(symbol: str, direction: str) -> tuple[bool, str]:
    """
    Detect conditions dangerous for `direction` via multi-TF HMM analysis.
    Fails open: returns (False, "") if endpoint unreachable.

    Danger conditions:
      - S/R trap: near resistance when BUY, near support when SELL (conf ≥ 0.65)
      - Extreme momentum reversal risk (MOM severity=danger, action opposes direction)
      - Cross-TF divergence (DIV tag — always dangerous)
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{PYTHON_API}/python/analysis/multi-tf",
                json={"instrument": symbol, "timeframes": ["M5", "M15"]},
            )
            resp.raise_for_status()
            alerts = resp.json()

        for alert in alerts:
            tag        = alert.get("tag", "")
            action     = alert.get("action", "NEUTRAL")
            severity   = alert.get("severity", "info")
            confidence = float(alert.get("confidence", 0.0))

            if tag == "S/R" and confidence >= 0.65:
                if (direction == "BUY"  and action == "SELL") or \
                   (direction == "SELL" and action == "BUY"):
                    level = "resistance" if direction == "BUY" else "support"
                    return True, f"S/R trap: near {level} (conf={confidence:.0%})"

            if tag == "MOM" and severity == "danger":
                if (direction == "BUY"  and action == "SELL") or \
                   (direction == "SELL" and action == "BUY"):
                    return True, f"Extreme momentum reversal (conf={confidence:.0%})"

            if tag == "DIV":
                return True, f"Cross-TF divergence (conf={confidence:.0%})"

        return False, ""
    except Exception as exc:
        logger.warning("[AggrEngine] _hmm_danger_check failed (fail-open): %s", exc)
        return False, ""


# ── Limit order helpers ────────────────────────────────────────────────────────

def _open_limit_position(sess: AggressiveSession, direction: str) -> Optional[int]:
    """
    Place a BUY_LIMIT / SELL_LIMIT order at current_price ± ATR × limit_atr_mult.
      BUY:  limit_price = ask - offset  (buy cheaper than current ask)
      SELL: limit_price = bid + offset  (sell higher than current bid)
    TP is calculated from limit_price using calc_tp_price.
    Returns pending order ticket, or None on failure.
    """
    if not mt5_executor.is_available():
        return None
    try:
        sym = mt5_executor.get_symbol_info(sess.symbol)
        if sym is None:
            return None

        atr = _calc_atr_direct(sess.symbol, _TF_M1, period=14)
        if atr <= 0:
            logger.warning("[AggrEngine] %s limit order: ATR=0 — skipping", sess.session_id[:8])
            return None

        offset  = atr * sess.limit_atr_mult
        digits  = sym["digits"]
        is_buy  = direction == "BUY"

        limit_price = round(
            sym["ask"] - offset if is_buy else sym["bid"] + offset,
            digits,
        )
        tp_price = mt5_executor.calc_tp_price(
            symbol        = sess.symbol,
            action        = direction,
            fill_price    = limit_price,
            profit_target = sess.profit_target,
            volume        = sess.volume,
        )

        result = mt5_executor.place_limit_order(
            symbol      = sess.symbol,
            action      = direction,
            volume      = sess.volume,
            limit_price = limit_price,
            tp_price    = tp_price,
            comment     = f"AggrLmt:{sess.session_id[:8]}",
        )

        if result["success"]:
            ticket = result["order_id"]
            sess.last_action = (
                f"limit {direction} #{ticket} @{limit_price:.5f} "
                f"(ATR×{sess.limit_atr_mult}={offset:.5f})"
            )
            logger.info("[AggrEngine] %s limit %s #%d @%.5f TP=%.5f",
                        sess.session_id[:8], direction, ticket, limit_price, tp_price)
            return ticket

        logger.warning("[AggrEngine] %s limit order FAILED retcode=%s",
                       sess.session_id[:8], result.get("retcode"))
        return None

    except Exception as exc:
        sess.last_action = f"limit order error: {exc}"
        logger.error("[AggrEngine] %s _open_limit_position: %s", sess.session_id[:8], exc)
        return None


def _check_pending_orders(sess: AggressiveSession, open_tickets: set) -> None:
    """
    Called every poll cycle when pending_tickets is non-empty.
      - Fill detected: ticket gone from pending AND in open positions → promote to active
      - Expired:       ticket still pending AND placed > pending_expiry_sec ago → cancel
      - Externally gone: not pending, not open → remove silently
    """
    if not mt5_executor.is_available():
        return

    mt5_pending = mt5_executor.get_pending_tickets()
    now = time.time()

    for ticket in list(sess.pending_tickets):
        if ticket in mt5_pending:
            placed_at = sess.pending_placed_at.get(ticket, now)
            if now - placed_at >= sess.pending_expiry_sec:
                _cancel_pending(sess, ticket)
        else:
            if ticket in open_tickets:
                # Filled — promote to active
                sess.pending_tickets.remove(ticket)
                sess.pending_placed_at.pop(ticket, None)
                sess.active_tickets.append(ticket)
                sess.total_opened += 1
                sess.last_action   = f"limit #{ticket} FILLED → active"
                logger.info("[AggrEngine] %s limit #%d filled", sess.session_id[:8], ticket)
            else:
                # Gone from both — external cancel or expired
                sess.pending_tickets.remove(ticket)
                sess.pending_placed_at.pop(ticket, None)
                logger.debug("[AggrEngine] %s limit #%d gone (not pending, not active)",
                             sess.session_id[:8], ticket)


def _cancel_pending(sess: AggressiveSession, ticket: int) -> None:
    """Cancel a pending limit order and remove from session tracking."""
    ok = mt5_executor.cancel_order(ticket) if mt5_executor.is_available() else False
    sess.pending_tickets.remove(ticket)
    sess.pending_placed_at.pop(ticket, None)
    action = "cancelled" if ok else "cancel-failed (removed from tracking)"
    sess.last_action = (
        f"limit #{ticket} expired ({sess.pending_expiry_sec:.0f}s) → {action}"
    )
    logger.info("[AggrEngine] %s limit #%d expired → %s",
                sess.session_id[:8], ticket, action)


# ── Math helpers ───────────────────────────────────────────────────────────────

def _calc_ema(closes: list[float], period: int) -> float:
    """EMA: SMA seed for first `period` bars, then α = 2/(period+1)."""
    if not closes:
        return 0.0
    if len(closes) < period:
        return sum(closes) / len(closes)
    alpha = 2.0 / (period + 1)
    ema   = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * alpha + ema * (1.0 - alpha)
    return ema


def _calc_atr_direct(
    symbol: str, timeframe: int, period: int = 14, n_bars: int = 20
) -> float:
    """ATR(period) directly from MT5. Returns 0.0 on any failure."""
    try:
        raw = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
        if raw is None or len(raw) < 3:
            return 0.0
        trs = []
        for i in range(1, len(raw)):
            h  = float(raw[i]["high"])
            l  = float(raw[i]["low"])
            pc = float(raw[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs[-period:]) / min(period, len(trs))
    except Exception:
        return 0.0


def _get_price_percentile_direct(sess: AggressiveSession) -> Optional[float]:
    """Price percentile within lookback range on M1 (for flip_mode=percentile/hybrid)."""
    try:
        raw = mt5.copy_rates_from_pos(sess.symbol, _TF_M1, 0, sess.lookback_bars)
        if raw is None or len(raw) == 0:
            return None
        highs   = [float(b["high"]) for b in raw]
        lows    = [float(b["low"])  for b in raw]
        rng_max = max(highs)
        rng_min = min(lows)
        current = float(raw[-1]["close"])
        rng     = rng_max - rng_min
        if rng == 0:
            return None
        return (current - rng_min) / rng
    except Exception:
        return None
