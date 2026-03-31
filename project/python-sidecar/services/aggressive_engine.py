"""
aggressive_engine.py — Aggressive Layer Trading Engine
=======================================================
Maintains N concurrent positions for a given symbol/direction.
When any position reaches profit_target (USD) → close it → immediately re-open.
No HMM / pattern validation. Pure aggressive scalping.

Flip modes (anti-trap at top/bottom):
  none        — always re-open same direction (original behaviour)
  percentile  — flip when price > flip_percentile of lookback_bars range
  counter     — flip after flip_after consecutive TPs in same direction
  hybrid      — flip if EITHER condition is met

Trend-Guided Re-open (cascade merge) — enabled via trend_guided=True:
  After each TP close, before re-opening, check M1+M5 EMA trend.
  - Trend confirms current direction → re-open same direction
  - Trend is opposite → flip direction (overrides counter/percentile flip)
  - Trend is NEUTRAL → apply existing flip logic as fallback
  Prevents "nyangkut di ujung" (stuck at top/bottom after trend reversal).

MCGuard — enabled via mc_guard=True:
  Checks equity/free_margin before EVERY position open.
  Levels:
    CAUTION   free_margin < safety_floor × 1.5 → skip this open cycle
    WARNING   free_margin < safety_floor        → block all new orders
    DANGER    free_margin < mc_level            → close 3 worst positions, block orders
    EMERGENCY equity      < emergency_floor     → close ALL positions, stop session
  Where:
    mc_level       = balance × mc_level_pct
    safety_floor   = mc_level × safety_multiplier
    emergency_floor = mc_level × emergency_multiplier

Uses threading (not asyncio tasks) for reliable execution on Windows/uvicorn.
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import httpx

from services import equity_cache as _eq_cache

logger = logging.getLogger(__name__)

PYTHON_API    = "http://localhost:8001"
POLL_INTERVAL = 5   # seconds between position checks


# ── Session state ──────────────────────────────────────────────────────────────

@dataclass
class AggressiveSession:
    session_id:         str
    symbol:             str
    direction:          str    # BUY | SELL | BOTH  (original setting, immutable)
    layers:             int
    volume:             float
    profit_target:      float  # USD profit per position to trigger close
    sl_pips:            float  # 0 = no SL
    tp_pips:            float  # 0 = no TP (rely on profit monitoring)

    # ── Flip / anti-trap settings ──────────────────────────────────────────────
    flip_mode:          str   = "none"  # none | percentile | counter | hybrid
    flip_percentile:    float = 0.80
    flip_after:         int   = 3
    lookback_bars:      int   = 20

    # ── Cascade merge: trend-guided re-open ───────────────────────────────────
    trend_guided:       bool  = True    # use M1+M5+M15 trend to decide re-open direction (default on)

    # ── MCGuard ───────────────────────────────────────────────────────────────
    mc_guard:             bool  = False
    mc_level_pct:         float = 0.10   # broker MC level (% of balance)
    safety_multiplier:    float = 3.0    # safety floor = mc_level × this
    emergency_multiplier: float = 1.5    # emergency floor = mc_level × this

    # ── Per-position SL ───────────────────────────────────────────────────────
    sl_loss_multiplier:   float = 1.0   # 0 = disabled; e.g. 1.0 = 1× profit_target (break-even at 50% win rate)

    # ── SL Cooldown — pause re-opens after SL to avoid revenge trading ────────
    sl_cooldown_sec:      float = 0.0   # 0 = disabled; N = wait N seconds after SL before reopen
    sl_cooldown_until:    float = 0.0   # runtime: timestamp when cooldown expires

    # ── Profit Guard ──────────────────────────────────────────────────────────
    max_session_loss_usd:   float = 0.0  # 0 = disabled; stop if total_net <= -this
    max_drawdown_from_peak: float = 0.0  # 0 = disabled; stop if total_net < peak - this

    # ── Runtime state ──────────────────────────────────────────────────────────
    active:               bool        = True
    active_tickets:       list        = field(default_factory=list)
    total_opened:         int         = 0
    total_closed_win:     int         = 0
    total_closed_other:   int         = 0
    total_closed_emergency: int       = 0
    total_closed_sl:        int       = 0
    total_profit:         float       = 0.0
    started_at:           float       = field(default_factory=time.time)
    last_action:          str         = "starting"
    error:                Optional[str] = None

    # ── Profit Guard runtime ───────────────────────────────────────────────────
    peak_profit:          float = 0.0
    floating_pnl:         float = 0.0
    next_recommendation:  str   = ""

    # ── Order failure watchdog ─────────────────────────────────────────────────
    # Counts consecutive fill cycles where 0 positions were opened (e.g. "Not enough money").
    # Session auto-stops after MAX_FILL_FAILURES (5) consecutive empty fills (with backoff).
    consecutive_fill_failures: int = 0

    # ── Cleanup tracking ───────────────────────────────────────────────────────
    stopped_at: float = 0.0   # timestamp when session became inactive (for registry cleanup)

    # ── Connection failure watchdog ────────────────────────────────────────────
    # Counts consecutive _get_positions failures (MT5 disconnect / zombie session).
    # Session auto-stops after MAX_CONNECTION_FAILURES (5) consecutive failures.
    consecutive_connection_failures: int = 0

    # ── HMM Gate — danger detection + cooldown ─────────────────────────────────
    # Default OFF: must be explicitly enabled in session settings.
    # When enabled: checks M1+M5+M15 before every fill for SR trap / extreme MOM / divergence.
    # On danger: pauses fills for hmm_cooldown_sec, then requires HMM vote to resume.
    hmm_gate_enabled:    bool  = False
    hmm_cooldown_sec:    float = 60.0   # seconds to pause on danger (like sl_cooldown_sec)
    hmm_cooldown_until:  float = 0.0   # runtime: epoch when cooldown expires
    hmm_cooldown_reason: str   = ""    # why cooldown was triggered
    hmm_vote_last:       str   = ""    # last voting result (BUY/SELL/NEUTRAL)

    # ── Auto Direction via HMM ─────────────────────────────────────────────────
    # Default OFF. When ON: resolve direction from HMM state (M1+M5+M15 action vote)
    # at session start (AUTO mode) and re-check after each TP close.
    auto_direction_hmm:  bool  = False

    # ── Limit Order (pending) ──────────────────────────────────────────────────
    # Default OFF (limit_atr_mult=0 = market order as before).
    # When ON: place BUY_LIMIT / SELL_LIMIT offset below/above current price by ATR × mult.
    # Pending orders tracked separately; cancelled if not filled within pending_expiry_sec.
    limit_atr_mult:     float = 0.0    # 0 = disabled; e.g. 0.1 = 10% ATR offset
    pending_expiry_sec: float = 15.0   # seconds before cancelling an unfilled pending order
    pending_tickets:    list  = field(default_factory=list)       # order tickets not yet filled
    pending_placed_at:  dict  = field(default_factory=dict)       # ticket → placed_at (epoch)

    # ── Flip tracking ──────────────────────────────────────────────────────────
    current_direction:  str  = ""
    consecutive_tp:     int  = 0
    total_flips:        int  = 0

    # ── MCGuard status ─────────────────────────────────────────────────────────
    mc_status:          str  = "OK"    # OK | CAUTION | WARNING | DANGER | EMERGENCY

    def __post_init__(self):
        if not self.current_direction:
            self.current_direction = "BUY" if self.direction == "BOTH" else self.direction


_sessions: dict[str, AggressiveSession] = {}
_threads:  dict[str, threading.Thread]  = {}


# ── Public API ─────────────────────────────────────────────────────────────────

def start_session(
    symbol:               str,
    direction:            str,
    layers:               int   = 10,
    volume:               float = 0.01,
    profit_target:        float = 0.5,
    sl_pips:              float = 0.0,
    tp_pips:              float = 0.0,
    flip_mode:            str   = "none",
    flip_percentile:      float = 0.80,
    flip_after:           int   = 3,
    lookback_bars:        int   = 20,
    trend_guided:         bool  = True,
    mc_guard:             bool  = False,
    mc_level_pct:         float = 0.10,
    safety_multiplier:    float = 3.0,
    emergency_multiplier: float = 1.5,
    sl_loss_multiplier:     float = 1.0,
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
        sl_pips              = sl_pips,
        tp_pips              = tp_pips,
        flip_mode            = flip_mode.lower(),
        flip_percentile      = flip_percentile,
        flip_after           = flip_after,
        lookback_bars        = max(5, lookback_bars),
        trend_guided         = trend_guided,
        mc_guard             = mc_guard,
        mc_level_pct         = mc_level_pct,
        safety_multiplier    = safety_multiplier,
        emergency_multiplier = emergency_multiplier,
        sl_loss_multiplier      = sl_loss_multiplier,
        sl_cooldown_sec         = sl_cooldown_sec,
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
        daemon=True, name=f"aggr-{session_id[:8]}"
    )
    t.start()
    _threads[session_id] = t

    logger.info(
        "[AggrEngine] Started %s | %s %s x%d vol=%.2f target=$%.2f "
        "flip=%s trend_guided=%s mc_guard=%s sl_loss_mult=%.1f",
        session_id[:8], symbol, direction, layers, volume, profit_target,
        flip_mode, trend_guided, mc_guard, sl_loss_multiplier,
    )
    return session_id


def stop_session(session_id: str) -> bool:
    sess = _sessions.get(session_id)
    if sess is None:
        return False
    sess.active = False
    logger.info("[AggrEngine] Stop requested for %s", session_id[:8])
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
            "sl_pips":              s.sl_pips,
            "flip_mode":            s.flip_mode,
            "flip_percentile":      s.flip_percentile,
            "flip_after":           s.flip_after,
            "lookback_bars":        s.lookback_bars,
            "trend_guided":         s.trend_guided,
            "mc_guard":             s.mc_guard,
            "mc_level_pct":         s.mc_level_pct,
            "safety_multiplier":    s.safety_multiplier,
            "emergency_multiplier": s.emergency_multiplier,
            "mc_status":            s.mc_status,
            "sl_loss_multiplier":     s.sl_loss_multiplier,
            "sl_cooldown_sec":        s.sl_cooldown_sec,
            "sl_cooldown_remaining":  max(0, round(s.sl_cooldown_until - time.time(), 1)) if s.sl_cooldown_sec > 0 else 0,
            "max_session_loss_usd":   s.max_session_loss_usd,
            "max_drawdown_from_peak": s.max_drawdown_from_peak,
            "peak_profit":            round(s.peak_profit, 2),
            "floating_pnl":           round(s.floating_pnl, 2),
            "total_net":              round(s.total_profit + s.floating_pnl, 2),
            "next_recommendation":    s.next_recommendation,
            "consecutive_fill_failures":      s.consecutive_fill_failures,
            "consecutive_connection_failures": s.consecutive_connection_failures,
            "consecutive_tp":           s.consecutive_tp,
            "total_flips":          s.total_flips,
            "hmm_gate_enabled":     s.hmm_gate_enabled,
            "hmm_cooldown_sec":     s.hmm_cooldown_sec,
            "hmm_cooldown_remaining": max(0.0, round(s.hmm_cooldown_until - time.time(), 1)) if s.hmm_gate_enabled else 0.0,
            "hmm_cooldown_reason":  s.hmm_cooldown_reason,
            "hmm_vote_last":        s.hmm_vote_last,
            "auto_direction_hmm":   s.auto_direction_hmm,
            "limit_atr_mult":       s.limit_atr_mult,
            "pending_expiry_sec":   s.pending_expiry_sec,
            "pending_orders":       len(s.pending_tickets),
            "active":               s.active,
            "active_tickets":       list(s.active_tickets),
            "open_positions":       len(s.active_tickets),
            "total_opened":         s.total_opened,
            "total_closed_win":     s.total_closed_win,
            "total_closed_other":   s.total_closed_other,
            "total_closed_sl":        s.total_closed_sl,
            "total_closed_emergency": s.total_closed_emergency,
            "total_profit":         round(s.total_profit, 2),
            "last_action":          s.last_action,
            "error":                s.error,
            "uptime_s":             int(time.time() - s.started_at),
        }
        for s in _sessions.values()
    ]


# ── Core loop ──────────────────────────────────────────────────────────────────

def _run_session(sess: AggressiveSession) -> None:
    logger.info("[AggrEngine] Thread start %s", sess.session_id[:8])
    client = httpx.Client(timeout=15)
    try:
        # ── AUTO direction: resolve via HMM vote or EMA trend ────────────────
        if sess.direction == "AUTO":
            use_hmm = sess.auto_direction_hmm
            method  = "HMM M1+M5+M15" if use_hmm else "EMA M1+M5+M15"
            sess.last_action = f"AUTO: analyzing {method}..."
            resolved = "NEUTRAL"
            for attempt in range(6):   # retry up to ~30 seconds
                resolved = (
                    _hmm_vote(sess.symbol, client)
                    if use_hmm
                    else _ema_trend_vote(sess.symbol, client)
                )
                if resolved != "NEUTRAL":
                    break
                logger.info(
                    "[AggrEngine] %s AUTO direction NEUTRAL via %s (attempt %d/6) — retrying in 5s",
                    sess.session_id[:8], method, attempt + 1,
                )
                time.sleep(5)
                if not sess.active:
                    return

            if resolved == "NEUTRAL":
                sess.error  = f"AUTO: direction still NEUTRAL after 30s ({method}) — session stopped"
                sess.active = False
                logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.error)
                return

            sess.current_direction = resolved
            sess.last_action = f"AUTO: direction resolved → {resolved} ({method})"
            logger.info(
                "[AggrEngine] %s AUTO direction resolved: %s via %s",
                sess.session_id[:8], resolved, method,
            )

        _fill_layers(sess, client)
        while sess.active:
            time.sleep(POLL_INTERVAL)
            if not sess.active:
                break
            _poll_and_manage(sess, client)
    except Exception as exc:
        logger.error("[AggrEngine] Session %s crashed: %s", sess.session_id[:8], exc)
        sess.error = str(exc)
    finally:
        sess.active     = False
        sess.stopped_at = time.time()
        try:
            sess.next_recommendation = _ema_trend_vote(sess.symbol, client)
        except Exception:
            sess.next_recommendation = "NEUTRAL"
        client.close()
        logger.info(
            "[AggrEngine] Session %s ended | opened=%d wins=%d profit=$%.2f flips=%d next=%s",
            sess.session_id[:8], sess.total_opened, sess.total_closed_win,
            sess.total_profit, sess.total_flips, sess.next_recommendation,
        )


_MAX_FILL_FAILURES        = 5   # stop session after this many consecutive empty fill cycles
_MAX_CONNECTION_FAILURES  = 5   # stop session after this many consecutive MT5 connection failures
_FILL_BACKOFF_S           = [0, 10, 30, 60, 60]   # wait per failure (index = failure count - 1)

_CLEANUP_INTERVAL_S = 300    # run cleanup every 5 minutes
_CLEANUP_RETAIN_S   = 1800   # keep stopped sessions for 30 minutes after stopping


def _cleanup_loop() -> None:
    """Background thread: remove expired stopped sessions from registry."""
    while True:
        time.sleep(_CLEANUP_INTERVAL_S)
        cutoff = time.time() - _CLEANUP_RETAIN_S
        expired = [
            sid for sid, s in list(_sessions.items())
            if not s.active and s.stopped_at > 0 and s.stopped_at < cutoff
        ]
        for sid in expired:
            _sessions.pop(sid, None)
            _threads.pop(sid, None)
        if expired:
            logger.info("[AggrEngine] Cleaned up %d expired sessions", len(expired))


_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True, name="aggr-cleanup")
_cleanup_thread.start()


def _fill_layers(sess: AggressiveSession, client: httpx.Client) -> None:
    # ── SL Cooldown: pause re-opens after SL events ────────────────────────────
    if sess.sl_cooldown_sec > 0 and time.time() < sess.sl_cooldown_until:
        remaining = int(sess.sl_cooldown_until - time.time())
        sess.last_action = f"SL cooldown: {remaining}s remaining before reopen"
        return

    # ── HMM Gate: danger detection + vote-based cooldown ──────────────────────
    if sess.hmm_gate_enabled:
        now = time.time()
        if now < sess.hmm_cooldown_until:
            # In HMM cooldown — try to break it with M1+M5+M15 vote
            vote = _hmm_vote(sess.symbol, client)
            sess.hmm_vote_last = vote
            if vote == sess.current_direction:
                # Vote confirms our direction → clear cooldown, proceed
                sess.hmm_cooldown_until = 0.0
                sess.hmm_cooldown_reason = ""
                sess.last_action = f"HMM vote {vote} ✓ — cooldown cleared, resuming"
                logger.info(
                    "[AggrEngine] %s HMM vote confirmed %s — cooldown cleared",
                    sess.session_id[:8], vote,
                )
            else:
                remaining = int(sess.hmm_cooldown_until - now)
                sess.last_action = (
                    f"HMM cooldown {remaining}s remaining "
                    f"(vote={vote} ≠ {sess.current_direction}) — {sess.hmm_cooldown_reason}"
                )
                return
        else:
            # No active cooldown — run danger check before opening positions
            danger, reason = _hmm_danger_check(sess.symbol, sess.current_direction, client)
            if danger:
                sess.hmm_cooldown_until  = now + sess.hmm_cooldown_sec
                sess.hmm_cooldown_reason = reason
                sess.last_action = (
                    f"HMM GATE ⚠ {reason} — "
                    f"cooldown {sess.hmm_cooldown_sec:.0f}s"
                )
                logger.warning(
                    "[AggrEngine] %s HMM gate triggered: %s (cooldown=%.0fs)",
                    sess.session_id[:8], reason, sess.hmm_cooldown_sec,
                )
                return

    needed = sess.layers - len(sess.active_tickets) - len(sess.pending_tickets)
    if needed <= 0:
        return

    directions = ["BUY", "SELL"] if sess.direction == "BOTH" else [sess.current_direction]
    opened_this_cycle = 0
    use_limit = sess.limit_atr_mult > 0

    for _ in range(needed):
        if not sess.active:
            break

        # MCGuard: check before each individual order
        if sess.mc_guard:
            mc = _check_mc_guard(sess, client)
            sess.mc_status = mc
            if mc == "CAUTION":
                sess.last_action = "MCGuard CAUTION — skipping this fill cycle"
                break
            if mc in ("WARNING", "DANGER", "EMERGENCY"):
                sess.last_action = f"MCGuard {mc} — fills blocked"
                break

        for d in directions:
            if use_limit:
                ticket = _open_limit_position(sess, d, client)
                if ticket:
                    sess.pending_tickets.append(ticket)
                    sess.pending_placed_at[ticket] = time.time()
                    opened_this_cycle += 1
            else:
                ticket = _open_position(sess, d, client)
                if ticket:
                    sess.active_tickets.append(ticket)
                    opened_this_cycle += 1

    # ── Watchdog: stop session if broker keeps rejecting orders ───────────────
    if needed > 0 and opened_this_cycle == 0:
        sess.consecutive_fill_failures += 1
        backoff = _FILL_BACKOFF_S[min(sess.consecutive_fill_failures - 1, len(_FILL_BACKOFF_S) - 1)]
        logger.warning(
            "[AggrEngine] %s fill cycle: 0/%d opened (fail streak=%d/%d, backoff=%ds)",
            sess.session_id[:8], needed, sess.consecutive_fill_failures, _MAX_FILL_FAILURES, backoff,
        )
        if backoff > 0:
            time.sleep(backoff)
        if sess.consecutive_fill_failures >= _MAX_FILL_FAILURES:
            sess.last_action = (
                f"AUTO-STOP: {sess.consecutive_fill_failures} consecutive fill failures "
                f"(last error: {sess.last_action}) — broker rejecting all orders"
            )
            logger.error("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
            sess.active = False
    else:
        sess.consecutive_fill_failures = 0   # reset on any successful open


def _poll_and_manage(sess: AggressiveSession, client: httpx.Client) -> None:
    # ── MCGuard check at top of every poll cycle ───────────────────────────────
    if sess.mc_guard:
        mc = _check_mc_guard(sess, client)
        sess.mc_status = mc

        if mc == "EMERGENCY":
            if _eq_cache.claim_emergency_action():
                sess.last_action = "MCGuard EMERGENCY — closing ALL positions, stopping session"
                _close_all_emergency(sess, client)
            else:
                sess.last_action = "MCGuard EMERGENCY — another session already acting, stopping"
            sess.active = False
            return

        if mc == "DANGER":
            sess.last_action = "MCGuard DANGER — closing 3 worst positions"
            _close_worst_positions(sess, 3, client)
            return   # skip topup this cycle

    # ── Normal poll: check positions ───────────────────────────────────────────
    try:
        positions = _get_positions(sess.symbol, client)
        sess.consecutive_connection_failures = 0   # reset on success
    except Exception as e:
        sess.consecutive_connection_failures += 1
        logger.warning(
            "[AggrEngine] %s get_positions failed (%d/%d): %s",
            sess.session_id[:8], sess.consecutive_connection_failures, _MAX_CONNECTION_FAILURES, e,
        )
        if sess.consecutive_connection_failures >= _MAX_CONNECTION_FAILURES:
            sess.error = (
                f"MT5 connection lost: {sess.consecutive_connection_failures} consecutive failures — session stopped"
            )
            sess.active = False
        return

    open_tickets = {p["ticket"] for p in positions}

    # ── Pending order management: detect fills + expiry cancellation ───────────
    if sess.pending_tickets:
        _check_pending_orders(sess, open_tickets, client)

    # ── Profit Guard check ─────────────────────────────────────────────────────
    if _check_profit_guard(sess, positions):
        _close_all_emergency(sess, client)
        sess.active = False
        return

    # Per-position SL check: close bleeding positions immediately
    sl_happened = False
    if sess.sl_loss_multiplier > 0:
        sl_before = sess.total_closed_sl
        _check_sl_conditions(sess, positions, client)
        sl_happened = sess.total_closed_sl > sl_before
        if sl_happened and sess.sl_cooldown_sec > 0:
            sess.sl_cooldown_until = time.time() + sess.sl_cooldown_sec
            logger.info(
                "[AggrEngine] %s SL cooldown started: %.0fs",
                sess.session_id[:8], sess.sl_cooldown_sec,
            )
        # Re-fetch positions after potential SL closes so profit check is accurate
        try:
            positions = _get_positions(sess.symbol, client)
            open_tickets = {p["ticket"] for p in positions}
        except Exception:
            pass

    # Detect externally-closed positions (broker SL/TP)
    closed_ext = [t for t in sess.active_tickets if t not in open_tickets]
    for t in closed_ext:
        sess.active_tickets.remove(t)
        sess.total_closed_other += 1
        sess.last_action = f"ticket {t} closed externally"

    # Check profit → close winners
    to_close: list[tuple[int, float, str]] = []
    for pos in positions:
        t = pos["ticket"]
        if t not in sess.active_tickets:
            continue
        profit = float(pos.get("profit", 0.0))
        if profit >= sess.profit_target:
            to_close.append((t, profit, pos.get("type", sess.current_direction)))

    last_closed_dir: Optional[str] = None
    for ticket, profit, pos_dir in to_close:
        if _close_position(sess, ticket, client):
            sess.active_tickets.remove(ticket)
            sess.total_closed_win += 1
            sess.total_profit += profit
            last_closed_dir = pos_dir
            sess.last_action = f"TP {pos_dir} #{ticket} +${profit:.2f}"
            logger.info(
                "[AggrEngine] %s TP %s #%d +$%.2f",
                sess.session_id[:8], pos_dir, ticket, profit,
            )

    # Re-fill: determine direction first, then open
    # Trigger re-fill if: TP close, external close, OR per-position SL close
    if to_close or closed_ext or sl_happened:
        closed_dir = last_closed_dir or sess.current_direction
        if closed_dir and sess.direction != "BOTH":
            _update_direction(sess, client, closed_dir)
        _fill_layers(sess, client)


# ── Direction decision: flip logic + trend-guided re-open ─────────────────────

def _update_direction(sess: AggressiveSession, client: httpx.Client, closed_dir: str) -> None:
    """
    Decide current_direction for the next re-open batch.

    Priority:
      1. trend_guided=True → M1+M5+M15 vote is the primary signal (majority = 2 of 3)
         - Trend confirms current dir → keep (reset counter)
         - Trend opposes current dir  → flip
         - Trend NEUTRAL              → use last_closed_dir (already set as current_direction)
      2. flip_mode logic (counter / percentile / hybrid) as fallback / complement
    """

    # Sync consecutive counter
    if closed_dir == sess.current_direction:
        sess.consecutive_tp += 1
    else:
        sess.consecutive_tp = 1
        sess.current_direction = closed_dir

    # ── Trend-guided check (EMA or HMM depending on setting) ─────────────────
    if sess.trend_guided or sess.auto_direction_hmm:
        trend = (
            _hmm_vote(sess.symbol, client)
            if sess.auto_direction_hmm
            else _ema_trend_vote(sess.symbol, client)
        )
        method = "HMM" if sess.auto_direction_hmm else "EMA"
        logger.debug("[AggrEngine] %s %s_vote=%s cur=%s", sess.session_id[:8], method, trend, sess.current_direction)

        if trend != "NEUTRAL":
            if trend != sess.current_direction:
                # Trend says opposite → flip regardless of counter/percentile
                _do_flip(sess, reason=f"trend-guided ({trend})")
            else:
                # Trend confirms → reset consecutive counter (no false flip)
                sess.consecutive_tp = 0
            return
        # NEUTRAL → use last_closed_dir (already set at top of function) — no flip
        return

    # ── Existing flip_mode logic ──────────────────────────────────────────────
    if sess.flip_mode == "none":
        return

    should_flip = False

    if sess.flip_mode in ("counter", "hybrid"):
        if sess.consecutive_tp >= sess.flip_after:
            should_flip = True

    if not should_flip and sess.flip_mode in ("percentile", "hybrid"):
        pct = _get_price_percentile(sess, client)
        if pct is not None:
            if sess.current_direction == "BUY" and pct >= sess.flip_percentile:
                should_flip = True
            elif sess.current_direction == "SELL" and pct <= (1.0 - sess.flip_percentile):
                should_flip = True

    if should_flip:
        _do_flip(sess, reason=f"{sess.flip_mode} (consec={sess.consecutive_tp})")


def _do_flip(sess: AggressiveSession, reason: str) -> None:
    new_dir = "SELL" if sess.current_direction == "BUY" else "BUY"
    logger.info(
        "[AggrEngine] %s FLIP %s → %s | %s",
        sess.session_id[:8], sess.current_direction, new_dir, reason,
    )
    sess.current_direction = new_dir
    sess.consecutive_tp    = 0
    sess.total_flips      += 1
    sess.last_action       = f"flipped → {new_dir} ({reason})"


# ── HMM Gate helpers ──────────────────────────────────────────────────────────

def _hmm_danger_check(symbol: str, direction: str, client: httpx.Client) -> tuple[bool, str]:
    """
    Query M1+M5+M15 analysis and detect conditions dangerous for `direction`.
    Returns (is_dangerous, reason_string).
    Fails open: returns (False, "") if the endpoint is unreachable.

    Danger conditions:
      - S/R trap: near resistance when BUY, near support when SELL (conf ≥ 0.65)
      - Extreme momentum reversal risk (MOM severity=danger, action opposes direction)
      - Cross-TF divergence (always dangerous)
    """
    try:
        resp = client.post(
            f"{PYTHON_API}/python/analysis/multi-tf",
            json={"instrument": symbol, "timeframes": ["M1", "M5", "M15"]},
            timeout=10,
        )
        resp.raise_for_status()
        alerts = resp.json()

        for alert in alerts:
            tag        = alert.get("tag", "")
            action     = alert.get("action", "NEUTRAL")
            severity   = alert.get("severity", "info")
            confidence = float(alert.get("confidence", 0.0))

            # S/R: near resistance for BUY, or near support for SELL
            if tag == "S/R" and confidence >= 0.65:
                if (direction == "BUY"  and action == "SELL") or \
                   (direction == "SELL" and action == "BUY"):
                    level = "resistance" if direction == "BUY" else "support"
                    return True, f"S/R trap: near {level} (conf={confidence:.0%})"

            # Extreme momentum: severity=danger means potential reversal
            if tag == "MOM" and severity == "danger":
                if (direction == "BUY"  and action == "SELL") or \
                   (direction == "SELL" and action == "BUY"):
                    return True, f"Extreme momentum reversal risk (conf={confidence:.0%})"

            # Cross-TF divergence is always a danger signal
            if tag == "DIV":
                return True, f"Cross-TF divergence (conf={confidence:.0%})"

        return False, ""
    except Exception as exc:
        logger.warning("[AggrEngine] HMM danger check failed (fail-open): %s", exc)
        return False, ""   # fail-open: never block when analysis is unreachable


def _hmm_vote(symbol: str, client: httpx.Client) -> str:
    """
    Query M1+M5+M15 analysis and return majority direction via confidence-weighted scoring.
    Returns "BUY" | "SELL" | "NEUTRAL".

    Scoring: sum alert confidence for each action; if ≥65% weight on one side → that direction.
    Used both for cooldown-breaking votes and AUTO direction resolution.
    """
    try:
        resp = client.post(
            f"{PYTHON_API}/python/analysis/multi-tf",
            json={"instrument": symbol, "timeframes": ["M1", "M5", "M15"]},
            timeout=10,
        )
        resp.raise_for_status()
        alerts = resp.json()

        buy_score  = 0.0
        sell_score = 0.0
        for alert in alerts:
            action     = alert.get("action", "NEUTRAL")
            confidence = float(alert.get("confidence", 0.0))
            if action == "BUY":
                buy_score  += confidence
            elif action == "SELL":
                sell_score += confidence

        total = buy_score + sell_score
        if total < 0.5:
            return "NEUTRAL"   # not enough signal strength

        buy_ratio = buy_score / total
        if buy_ratio >= 0.65:
            return "BUY"
        if buy_ratio <= 0.35:
            return "SELL"
        return "NEUTRAL"
    except Exception as exc:
        logger.warning("[AggrEngine] HMM vote failed: %s", exc)
        return "NEUTRAL"


# ── Trend analysis (for trend_guided) ─────────────────────────────────────────

def _calc_ema(closes: list[float], period: int) -> float:
    """Proper EMA: seed with SMA of first `period` bars, then apply α = 2/(period+1)."""
    if len(closes) < period:
        return sum(closes) / len(closes)
    alpha = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period   # SMA seed
    for price in closes[period:]:
        ema = price * alpha + ema * (1.0 - alpha)
    return ema


def _ema_trend_vote(symbol: str, client: httpx.Client) -> str:
    """Majority vote from M1+M5+M15 EMA5/EMA10 crossover. Majority = min 2 of 3. Returns BUY/SELL/NEUTRAL."""
    votes: dict[str, int] = {"BUY": 0, "SELL": 0}
    for tf in ("M1", "M5", "M15"):
        try:
            r = client.post(
                f"{PYTHON_API}/python/mt5/ohlc",
                json={"symbol": symbol, "timeframe": tf, "bars": 20},
            )
            r.raise_for_status()
            bars = r.json().get("bars", [])
            if len(bars) < 12:
                continue
            closes = [float(b["close"]) for b in bars]
            ema5  = _calc_ema(closes, 5)
            ema10 = _calc_ema(closes, 10)
            if ema5 > ema10:
                votes["BUY"] += 1
            elif ema5 < ema10:
                votes["SELL"] += 1
        except Exception as e:
            logger.debug("[AggrEngine] ema_trend %s/%s: %s", symbol, tf, e)

    if votes["BUY"] > votes["SELL"]:
        return "BUY"
    if votes["SELL"] > votes["BUY"]:
        return "SELL"
    return "NEUTRAL"


# ── MCGuard ────────────────────────────────────────────────────────────────────

def _check_mc_guard(sess: AggressiveSession, client: httpx.Client) -> str:
    """Read shared equity snapshot and return guard level.
    Uses equity_cache for inter-session coordination (prevents parallel over-closing).
    """
    snap = _eq_cache.get_equity_snapshot()
    balance     = snap["balance"]
    equity      = snap["equity"]
    free_margin = snap["free_margin"]

    if balance <= 0:
        return "OK"   # fail-open if cache not yet populated

    mc_level        = balance * sess.mc_level_pct
    safety_floor    = mc_level * sess.safety_multiplier
    emergency_floor = mc_level * sess.emergency_multiplier

    if equity <= emergency_floor:
        return "EMERGENCY"
    if free_margin <= mc_level:
        return "DANGER"
    if free_margin <= safety_floor:
        return "WARNING"
    if free_margin <= safety_floor * 1.5:
        return "CAUTION"
    return "OK"


def _check_sl_conditions(
    sess: AggressiveSession, positions: list[dict], client: httpx.Client
) -> None:
    """
    Per-position hard SL: close immediately when floating_loss >= sl_loss_multiplier × profit_target.

    No trend condition — speed is the priority for scalping momentum.
    Position is reopened immediately after by the main loop, staying on the momentum.
    """
    threshold = sess.sl_loss_multiplier * sess.profit_target  # e.g. 3 × $0.5 = $1.50 loss

    for pos in positions:
        ticket = pos.get("ticket")
        if ticket not in sess.active_tickets:
            continue
        profit = float(pos.get("profit", 0.0))
        if profit >= 0:
            continue   # only look at losing positions

        floating_loss = abs(profit)
        if floating_loss < threshold:
            continue   # loss not large enough yet

        pos_type = str(pos.get("type", "")).upper()  # "BUY" or "SELL"

        logger.warning(
            "[AggrEngine] %s Hard SL: #%d %s loss=$%.2f >= threshold=$%.2f — closing immediately",
            sess.session_id[:8], ticket, pos_type, floating_loss, threshold,
        )

        if _close_position(sess, ticket, client):
            if ticket in sess.active_tickets:
                sess.active_tickets.remove(ticket)
            sess.total_closed_sl  += 1
            sess.total_profit     += profit   # adds the loss (negative)
            sess.last_action       = f"Hard SL #{ticket} {pos_type} -${floating_loss:.2f}"


def _check_profit_guard(
    sess: AggressiveSession, positions: list[dict]
) -> bool:
    """
    Profit Guard: two-layer session protection.
      1. Floor:    stop if total_net <= -max_session_loss_usd     (don't burn capital)
      2. Drawdown: stop if total_net < peak_profit - max_drawdown (don't give back profits)

    total_net = realized total_profit + current floating P&L of open positions.
    Returns True if guard triggered — caller must close all and stop session.
    """
    if sess.max_session_loss_usd <= 0 and sess.max_drawdown_from_peak <= 0:
        return False

    our_tickets = set(sess.active_tickets)
    floating = sum(
        float(p.get("profit", 0))
        for p in positions
        if p.get("ticket") in our_tickets
    )
    sess.floating_pnl = round(floating, 2)
    total_net = sess.total_profit + floating

    # Peak only tracks AFTER at least one realized profit exists.
    # Prevents phantom peak from momentary floating spikes before any TP hit.
    if sess.total_profit > 0 and total_net > sess.peak_profit:
        sess.peak_profit = total_net

    if sess.max_session_loss_usd > 0:
        if total_net <= -sess.max_session_loss_usd:
            sess.last_action = (
                f"PROFIT GUARD (floor): net=${total_net:.2f} ≤ -${sess.max_session_loss_usd:.2f} → stopping"
            )
            logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
            return True

    if sess.max_drawdown_from_peak > 0 and sess.peak_profit > 0:
        if total_net < sess.peak_profit - sess.max_drawdown_from_peak:
            sess.last_action = (
                f"PROFIT GUARD (drawdown): net=${total_net:.2f} dropped "
                f"${sess.peak_profit - total_net:.2f} from peak=${sess.peak_profit:.2f} → stopping"
            )
            logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
            return True

    return False


def _close_all_emergency(sess: AggressiveSession, client: httpx.Client) -> None:
    """EMERGENCY: close all positions via close-all endpoint."""
    try:
        r = client.post(f"{PYTHON_API}/python/mt5/close-all", json={"filter": "all"})
        r.raise_for_status()
        data = r.json()
        sess.total_closed_emergency += data.get("closed", 0)
        sess.total_profit           += data.get("total_profit", 0.0)
        sess.active_tickets.clear()
        sess.floating_pnl = 0.0   # positions are gone — no more floating
        logger.warning(
            "[AggrEngine] %s EMERGENCY closed %d positions",
            sess.session_id[:8], data.get("closed", 0),
        )
    except Exception as e:
        logger.error("[AggrEngine] Emergency close error: %s", e)


def _close_worst_positions(sess: AggressiveSession, n: int, client: httpx.Client) -> None:
    """DANGER: close the N most losing open positions."""
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/positions")
        r.raise_for_status()
        positions = sorted(
            [p for p in r.json() if p.get("symbol", "").upper() == sess.symbol.upper()],
            key=lambda p: float(p.get("profit", 0)),
        )
        for pos in positions[:n]:
            ticket = pos["ticket"]
            if _close_position(sess, ticket, client) and ticket in sess.active_tickets:
                sess.active_tickets.remove(ticket)
                sess.total_closed_other += 1
                logger.warning(
                    "[AggrEngine] %s DANGER closed worst #%d profit=$%.2f",
                    sess.session_id[:8], ticket, pos.get("profit", 0),
                )
    except Exception as e:
        logger.error("[AggrEngine] Close worst error: %s", e)


# ── Percentile (existing flip helper) ─────────────────────────────────────────

def _get_price_percentile(sess: AggressiveSession, client: httpx.Client) -> Optional[float]:
    try:
        r = client.post(f"{PYTHON_API}/python/mt5/ohlc", json={
            "symbol":    sess.symbol,
            "timeframe": "M1",
            "bars":      sess.lookback_bars,
        })
        r.raise_for_status()
        bars = r.json().get("bars", [])
        if not bars:
            return None
        highs     = [b["high"]  for b in bars]
        lows      = [b["low"]   for b in bars]
        range_max = max(highs)
        range_min = min(lows)
        current   = bars[-1]["close"]
        rng = range_max - range_min
        if rng == 0:
            return None
        return (current - range_min) / rng
    except Exception as e:
        logger.warning("[AggrEngine] %s percentile fetch failed: %s", sess.session_id[:8], e)
        return None


# ── Limit order helpers ────────────────────────────────────────────────────────

def _get_atr(symbol: str, client: httpx.Client, period: int = 14) -> Optional[float]:
    """ATR(period) from M1 bars. Returns None on failure."""
    try:
        r = client.post(f"{PYTHON_API}/python/mt5/ohlc", json={
            "symbol": symbol, "timeframe": "M1", "bars": period + 1,
        })
        r.raise_for_status()
        bars = r.json().get("bars", [])
        if len(bars) < period + 1:
            return None
        trs = []
        for i in range(1, len(bars)):
            h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs[-period:]) / period
    except Exception as exc:
        logger.warning("[AggrEngine] ATR fetch failed: %s", exc)
        return None


def _open_limit_position(
    sess: AggressiveSession, direction: str, client: httpx.Client
) -> Optional[int]:
    """
    Place a BUY_LIMIT / SELL_LIMIT order at current_price ± ATR × limit_atr_mult.
    BUY:  limit_price = ask - offset  (buy cheaper than current ask)
    SELL: limit_price = bid + offset  (sell higher than current bid)
    SL/TP are calculated from limit_price (the expected fill price).
    Returns the pending order ticket, or None on failure.
    """
    from services import mt5_executor

    if not mt5_executor.is_available():
        logger.warning("[AggrEngine] %s limit order skipped: MT5 executor unavailable", sess.session_id[:8])
        return None

    try:
        sym = mt5_executor.get_symbol_info(sess.symbol)
        if sym is None:
            logger.warning("[AggrEngine] %s limit order: symbol info unavailable", sess.session_id[:8])
            return None

        atr = _get_atr(sess.symbol, client)
        if atr is None:
            logger.warning("[AggrEngine] %s limit order: ATR unavailable — skipping", sess.session_id[:8])
            return None

        offset  = atr * sess.limit_atr_mult
        digits  = sym["digits"]
        point   = sym["point"]

        if direction == "BUY":
            limit_price = round(sym["ask"] - offset, digits)
            sl_price    = round(limit_price - sess.sl_pips * point, digits) if sess.sl_pips > 0 else 0.0
            tp_price    = round(limit_price + sess.tp_pips * point, digits) if sess.tp_pips > 0 else 0.0
        else:
            limit_price = round(sym["bid"] + offset, digits)
            sl_price    = round(limit_price + sess.sl_pips * point, digits) if sess.sl_pips > 0 else 0.0
            tp_price    = round(limit_price - sess.tp_pips * point, digits) if sess.tp_pips > 0 else 0.0

        result = mt5_executor.place_limit_order(
            symbol      = sess.symbol,
            action      = direction,
            volume      = sess.volume,
            limit_price = limit_price,
            sl_price    = sl_price,
            tp_price    = tp_price,
            comment     = f"AggrLmt:{sess.session_id[:8]}",
        )

        if result["success"]:
            ticket = result["order_id"]
            sess.last_action = (
                f"limit {direction} #{ticket} @{limit_price:.5f} "
                f"(ATR={atr:.5f} offset={offset:.5f})"
            )
            logger.info(
                "[AggrEngine] %s placed limit %s #%d @%.5f (ATR=%.5f × %.2f = %.5f)",
                sess.session_id[:8], direction, ticket, limit_price,
                atr, sess.limit_atr_mult, offset,
            )
            return ticket

        logger.warning(
            "[AggrEngine] %s limit order FAILED %s retcode=%s",
            sess.session_id[:8], direction, result.get("retcode"),
        )
        return None

    except Exception as exc:
        sess.last_action = f"limit order ERROR: {exc}"
        logger.error("[AggrEngine] %s _open_limit_position: %s", sess.session_id[:8], exc)
        return None


def _check_pending_orders(
    sess: AggressiveSession, open_tickets: set, client: httpx.Client
) -> None:
    """
    Called every poll cycle when pending_tickets is non-empty.
    - Detects fills: ticket disappeared from pending orders AND appears in positions → promote to active.
    - Detects expiry: ticket still pending but placed > pending_expiry_sec ago → cancel.
    - Detects external cancels: ticket gone from both pending and positions → remove silently.
    """
    from services import mt5_executor

    mt5_pending = mt5_executor.get_pending_tickets() if mt5_executor.is_available() else set()
    now = time.time()

    for ticket in list(sess.pending_tickets):
        if ticket in mt5_pending:
            # Still pending — check expiry timer
            placed_at = sess.pending_placed_at.get(ticket, now)
            if now - placed_at >= sess.pending_expiry_sec:
                _cancel_pending(sess, ticket)
        else:
            # No longer in pending orders
            if ticket in open_tickets:
                # Filled — promote to active
                sess.pending_tickets.remove(ticket)
                sess.pending_placed_at.pop(ticket, None)
                sess.active_tickets.append(ticket)
                sess.total_opened += 1
                sess.last_action = f"limit #{ticket} FILLED → active"
                logger.info("[AggrEngine] %s limit #%d filled", sess.session_id[:8], ticket)
            else:
                # Gone externally (broker reject / manual cancel)
                sess.pending_tickets.remove(ticket)
                sess.pending_placed_at.pop(ticket, None)
                logger.debug(
                    "[AggrEngine] %s limit #%d gone (not pending, not active)",
                    sess.session_id[:8], ticket,
                )


def _cancel_pending(sess: AggressiveSession, ticket: int) -> None:
    """Cancel a pending order and remove it from session tracking."""
    from services import mt5_executor

    ok = mt5_executor.cancel_order(ticket) if mt5_executor.is_available() else False
    sess.pending_tickets.remove(ticket)
    sess.pending_placed_at.pop(ticket, None)
    action = "cancelled" if ok else "cancel-failed (removed from tracking)"
    sess.last_action = f"limit #{ticket} expired ({sess.pending_expiry_sec:.0f}s) → {action}"
    logger.info("[AggrEngine] %s limit #%d expired → %s", sess.session_id[:8], ticket, action)


# ── MT5 helpers ────────────────────────────────────────────────────────────────

def _open_position(sess: AggressiveSession, direction: str, client: httpx.Client) -> Optional[int]:
    payload: dict = {
        "symbol":  sess.symbol,
        "action":  direction,
        "volume":  sess.volume,
        "comment": f"Aggr:{sess.session_id[:8]}",
    }
    if sess.sl_pips > 0:
        payload["slPips"] = sess.sl_pips
    if sess.tp_pips > 0:
        payload["tpPips"] = sess.tp_pips

    try:
        r = client.post(f"{PYTHON_API}/python/mt5/order", json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            ticket = data["order_id"]
            sess.total_opened += 1
            sess.last_action   = f"opened {direction} #{ticket}"
            logger.info("[AggrEngine] %s opened %s #%d", sess.session_id[:8], direction, ticket)
            return ticket
        desc = data.get("retcode_desc", "?")
        sess.last_action = f"order FAILED {direction}: {desc}"
        logger.warning("[AggrEngine] %s %s", sess.session_id[:8], sess.last_action)
        return None
    except Exception as e:
        sess.last_action = f"order ERROR: {e}"
        logger.error("[AggrEngine] %s open_position: %s", sess.session_id[:8], e)
        return None


def _close_position(sess: AggressiveSession, ticket: int, client: httpx.Client) -> bool:
    try:
        r = client.post(
            f"{PYTHON_API}/python/mt5/close",
            json={"ticket": ticket, "comment": "Aggr:close"},
        )
        r.raise_for_status()
        return r.json().get("success", False)
    except Exception as e:
        logger.error("[AggrEngine] %s close #%d: %s", sess.session_id[:8], ticket, e)
        return False


def _get_positions(symbol: str, client: httpx.Client) -> list[dict]:
    r = client.get(f"{PYTHON_API}/python/mt5/positions")
    r.raise_for_status()
    return [p for p in r.json() if p["symbol"].upper() == symbol.upper()]
