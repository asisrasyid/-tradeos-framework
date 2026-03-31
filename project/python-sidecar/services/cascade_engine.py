"""
Cascade Engine — Dynamic layered trading with MCGuard.

Strategy:
  - M15 trend analysis untuk initial direction
  - Open initial_batch positions
  - Every eval_interval detik: cek M1+M5+M15 trend (majority vote, min 2 of 3)
    - Trend sama   → topup batch ke arah yg sama
    - Trend flip   → buka batch baru arah sebaliknya (posisi lama tetap jalan)
    - Trend NEUTRAL → gunakan last_tp_direction sebagai fallback
  - Hard SL per posisi: floating_loss >= sl_loss_multiplier × profit_target (no trend condition)
  - MCGuard: 4 level proteksi — CAUTION / WARNING / DANGER / EMERGENCY

MCGuard levels:
  CAUTION   free_margin < safety_floor * 1.5   → batch dikurangi jadi 2
  WARNING   free_margin < safety_floor          → blok topup
  DANGER    free_margin < mc_level              → tutup 3 posisi terburuk
  EMERGENCY equity < emergency_floor            → tutup SEMUA, stop session
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from services import equity_cache as _eq_cache

PYTHON_API = "http://localhost:8001"
logger = logging.getLogger(__name__)

_sessions: dict[str, "CascadeSession"] = {}
_lock = threading.Lock()


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class DirectionBatch:
    batch_id:   str
    direction:  str
    tickets:    list[int] = field(default_factory=list)
    opened_at:  str = ""
    closed_tp:  int = 0
    closed_sl:  int = 0


@dataclass
class CascadeSession:
    session_id:           str
    symbol:               str
    initial_batch:        int     # posisi pembuka
    topup_batch:          int     # tambahan tiap interval
    volume:               float
    profit_target:        float   # USD per posisi (utk SL threshold)
    hard_sl_pips:         float   # SL keras per posisi via broker (0 = disabled)
    sl_loss_multiplier:   float   # Hard SL: close when loss >= multiplier × profit_target (0 = disabled)
    max_positions:        int     # hard cap total posisi
    eval_interval:        int     # detik antar evaluasi

    # MCGuard params
    mc_level_pct:         float = 0.10
    safety_multiplier:    float = 3.0
    emergency_multiplier: float = 1.5

    # Profit Guard
    max_session_loss_usd:   float = 0.0  # 0 = disabled
    max_drawdown_from_peak: float = 0.0  # 0 = disabled

    # State
    active:               bool = True
    batches:              list[DirectionBatch] = field(default_factory=list)
    current_direction:    str = "NONE"
    last_tp_direction:    str = ""
    mc_status:            str = "OK"

    # Profit Guard runtime
    peak_profit:          float = 0.0
    floating_pnl:         float = 0.0
    next_recommendation:  str   = ""

    # Connection failure watchdog
    consecutive_connection_failures: int = 0

    # Stats
    total_opened:         int = 0
    total_closed_tp:      int = 0
    total_closed_sl:      int = 0
    total_closed_emergency: int = 0
    total_profit:         float = 0.0
    last_eval:            str = ""
    last_action:          str = "Initialized"
    error:                Optional[str] = None
    started_at:           str = ""
    uptime_s:             int = 0
    stopped_at:           float = 0.0   # timestamp for registry cleanup


# ── Public API ─────────────────────────────────────────────────────────────────

_CLEANUP_INTERVAL_S = 300
_CLEANUP_RETAIN_S   = 1800


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
        if expired:
            logger.info("[Cascade] Cleaned up %d expired sessions", len(expired))


_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True, name="cascade-cleanup")
_cleanup_thread.start()


def start_session(
    symbol:               str,
    initial_batch:        int,
    topup_batch:          int,
    volume:               float,
    profit_target:        float,
    hard_sl_pips:         float,
    sl_loss_multiplier:   float,
    max_positions:        int,
    eval_interval:        int,
    mc_level_pct:           float,
    safety_multiplier:      float,
    emergency_multiplier:   float,
    max_session_loss_usd:   float = 0.0,
    max_drawdown_from_peak: float = 0.0,
) -> str:
    sid = str(uuid.uuid4())
    sess = CascadeSession(
        session_id           = sid,
        symbol               = symbol,
        initial_batch        = initial_batch,
        topup_batch          = topup_batch,
        volume               = volume,
        profit_target        = profit_target,
        hard_sl_pips         = hard_sl_pips,
        sl_loss_multiplier   = sl_loss_multiplier,
        max_positions        = max_positions,
        eval_interval        = eval_interval,
        mc_level_pct         = mc_level_pct,
        safety_multiplier    = safety_multiplier,
        emergency_multiplier    = emergency_multiplier,
        max_session_loss_usd    = max_session_loss_usd,
        max_drawdown_from_peak  = max_drawdown_from_peak,
        started_at              = datetime.now(timezone.utc).isoformat(),
    )
    with _lock:
        _sessions[sid] = sess
    threading.Thread(target=_run_session, args=(sid,), daemon=True).start()
    return sid


def stop_session(session_id: str) -> bool:
    sess = _sessions.get(session_id)
    if not sess:
        return False
    sess.active = False
    return True


def get_all_status() -> list[dict]:
    result = []
    with _lock:
        items = list(_sessions.values())
    for s in items:
        all_tickets = [t for b in s.batches for t in b.tickets]
        result.append({
            "session_id":            s.session_id,
            "symbol":                s.symbol,
            "initial_batch":         s.initial_batch,
            "topup_batch":           s.topup_batch,
            "volume":                s.volume,
            "profit_target":         s.profit_target,
            "hard_sl_pips":          s.hard_sl_pips,
            "sl_loss_multiplier":     s.sl_loss_multiplier,
            "max_session_loss_usd":   s.max_session_loss_usd,
            "max_drawdown_from_peak": s.max_drawdown_from_peak,
            "peak_profit":            round(s.peak_profit, 2),
            "floating_pnl":           round(s.floating_pnl, 2),
            "total_net":              round(s.total_profit + s.floating_pnl, 2),
            "next_recommendation":    s.next_recommendation,
            "max_positions":          s.max_positions,
            "eval_interval":         s.eval_interval,
            "mc_level_pct":          s.mc_level_pct,
            "safety_multiplier":     s.safety_multiplier,
            "emergency_multiplier":  s.emergency_multiplier,
            "active":                s.active,
            "mc_status":             s.mc_status,
            "current_direction":     s.current_direction,
            "open_positions":        len(all_tickets),
            "total_opened":          s.total_opened,
            "total_closed_tp":       s.total_closed_tp,
            "total_closed_sl":       s.total_closed_sl,
            "total_closed_emergency": s.total_closed_emergency,
            "total_profit":          s.total_profit,
            "last_eval":             s.last_eval,
            "last_action":           s.last_action,
            "error":                 s.error,
            "uptime_s":              s.uptime_s,
            "batches": [
                {
                    "batch_id":   b.batch_id,
                    "direction":  b.direction,
                    "open":       len(b.tickets),
                    "closed_tp":  b.closed_tp,
                    "closed_sl":  b.closed_sl,
                    "opened_at":  b.opened_at,
                }
                for b in s.batches
            ],
        })
    return result


# ── Session loop ───────────────────────────────────────────────────────────────

def _run_session(session_id: str):
    sess = _sessions[session_id]
    client = httpx.Client(timeout=15)
    start_t = time.time()

    try:
        # ── Step 1: Determine initial direction from M1+M5+M15 majority vote ────
        sess.last_action = "Analyzing M1+M5+M15 trend..."
        direction = _analyze_trend_multi(sess.symbol, client)

        if direction == "NEUTRAL":
            # Retry for up to 2 minutes
            for _ in range(24):
                time.sleep(5)
                if not sess.active:
                    return
                direction = _analyze_trend_multi(sess.symbol, client)
                if direction != "NEUTRAL":
                    break

        if direction == "NEUTRAL":
            sess.error = "No clear M1+M5+M15 trend after 2 minutes — session stopped"
            sess.active = False
            return

        # ── Step 2: MCGuard check before initial batch ────────────────────────
        mc = _check_mc_guard(sess, client)
        sess.mc_status = mc
        if mc in ("DANGER", "EMERGENCY"):
            sess.error = f"MCGuard blocked start: {mc}"
            sess.active = False
            return

        # ── Step 3: Open initial batch ────────────────────────────────────────
        sess.current_direction = direction
        n_opened = _open_batch(sess, direction, sess.initial_batch, client)
        sess.last_action = f"Initial batch: {n_opened}x {direction} @ M1+M5+M15"

        # ── Step 4: Main eval loop ────────────────────────────────────────────
        while sess.active:
            time.sleep(sess.eval_interval)
            if not sess.active:
                break

            sess.uptime_s = int(time.time() - start_t)
            sess.last_eval = datetime.now(timezone.utc).isoformat()

            # MCGuard — highest priority
            mc = _check_mc_guard(sess, client)
            sess.mc_status = mc
            logger.info("[Cascade:%s] MCGuard=%s", session_id[:8], mc)

            if mc == "EMERGENCY":
                if _eq_cache.claim_emergency_action():
                    sess.last_action = "EMERGENCY: Closing ALL positions — MCGuard"
                    _close_all_positions(sess, client)
                else:
                    sess.last_action = "EMERGENCY: Another session already acting — stopping"
                sess.active = False
                break

            if mc == "DANGER":
                sess.last_action = "DANGER: Closing 3 worst positions — MCGuard"
                _close_worst_positions(sess, 3, client)
                continue  # skip topup this cycle

            # Profit Guard — protect session net P&L
            if _check_profit_guard(sess, client):
                _close_all_positions(sess, client)
                sess.active = False
                break

            # Sync closed positions (TP hit by MT5)
            _sync_positions(sess, client)

            # Multi-TF trend vote (M1 + M5)
            trend = _analyze_trend_multi(sess.symbol, client)
            logger.info("[Cascade:%s] Trend vote=%s", session_id[:8], trend)

            # SL conditions: loss > 3× target AND trend against position
            _check_sl_conditions(sess, client, trend)

            # Topup gating
            if mc == "WARNING":
                sess.last_action = f"WARNING: Topup blocked by MCGuard (free_margin low)"
                continue

            all_tickets = [t for b in sess.batches for t in b.tickets]
            if len(all_tickets) >= sess.max_positions:
                sess.last_action = f"Max positions ({sess.max_positions}) reached"
                continue

            if trend == "NEUTRAL":
                if sess.last_tp_direction:
                    # Use last TP direction as fallback — stay on momentum
                    trend = sess.last_tp_direction
                    logger.info(
                        "[Cascade:%s] Trend NEUTRAL → using last_tp_direction=%s",
                        session_id[:8], trend,
                    )
                else:
                    sess.last_action = "Trend NEUTRAL — holding, no topup"
                    continue

            topup_size = 2 if mc == "CAUTION" else sess.topup_batch
            available = sess.max_positions - len(all_tickets)
            topup_size = min(topup_size, available)

            if trend == sess.current_direction:
                # Pyramiding — same direction
                n = _open_batch(sess, trend, topup_size, client)
                sess.last_action = f"Topup {n}x {trend} (pyramiding)"
            else:
                # Direction flip — new batch opposite direction
                sess.current_direction = trend
                n = _open_batch(sess, trend, topup_size, client)
                sess.last_action = f"Flip to {trend}: opened {n} positions"

    except Exception as exc:
        sess.error = str(exc)
        logger.exception("[Cascade:%s] Crashed: %s", session_id[:8], exc)
    finally:
        sess.active     = False
        sess.stopped_at = time.time()
        try:
            sess.next_recommendation = _analyze_trend_multi(sess.symbol, client)
        except Exception:
            sess.next_recommendation = "NEUTRAL"
        client.close()


# ── MCGuard ────────────────────────────────────────────────────────────────────

def _check_mc_guard(sess: CascadeSession, client: httpx.Client) -> str:
    """Read shared equity snapshot and return guard level."""
    snap = _eq_cache.get_equity_snapshot()
    balance     = snap["balance"]
    equity      = snap["equity"]
    free_margin = snap["free_margin"]

    if balance <= 0:
        return "OK"

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


# ── Trend analysis ─────────────────────────────────────────────────────────────

def _analyze_m15(symbol: str, client: httpx.Client) -> str:
    """EMA5/EMA10 crossover on M15 for initial direction."""
    return _ema_trend(symbol, "M15", client)


def _analyze_trend_multi(symbol: str, client: httpx.Client) -> str:
    """Majority vote: M1 + M5 + M15. Majority = min 2 of 3. Returns BUY / SELL / NEUTRAL."""
    votes: dict[str, int] = {"BUY": 0, "SELL": 0}
    for tf in ("M1", "M5", "M15"):
        v = _ema_trend(symbol, tf, client)
        if v in votes:
            votes[v] += 1
    if votes["BUY"] > votes["SELL"]:
        return "BUY"
    if votes["SELL"] > votes["BUY"]:
        return "SELL"
    return "NEUTRAL"


def _calc_ema(closes: list[float], period: int) -> float:
    """Proper EMA: seed with SMA of first `period` bars, then apply α = 2/(period+1)."""
    if len(closes) < period:
        return sum(closes) / len(closes)
    alpha = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period   # SMA seed
    for price in closes[period:]:
        ema = price * alpha + ema * (1.0 - alpha)
    return ema


def _ema_trend(symbol: str, tf: str, client: httpx.Client) -> str:
    try:
        r = client.post(
            f"{PYTHON_API}/python/mt5/ohlc",
            json={"symbol": symbol, "timeframe": tf, "bars": 20},
        )
        r.raise_for_status()
        bars = r.json().get("bars", [])
        if len(bars) < 12:
            return "NEUTRAL"
        closes = [float(b["close"]) for b in bars]
        ema5  = _calc_ema(closes, 5)
        ema10 = _calc_ema(closes, 10)
        if ema5 > ema10:
            return "BUY"
        if ema5 < ema10:
            return "SELL"
        return "NEUTRAL"
    except Exception as exc:
        logger.error("[Cascade] EMA trend %s/%s error: %s", symbol, tf, exc)
        return "NEUTRAL"


# ── Position management ────────────────────────────────────────────────────────

def _open_batch(sess: CascadeSession, direction: str, count: int, client: httpx.Client) -> int:
    """Open up to `count` positions; check MCGuard before each. Returns opened count."""
    batch = DirectionBatch(
        batch_id  = str(uuid.uuid4())[:8],
        direction = direction,
        opened_at = datetime.now(timezone.utc).isoformat(),
    )
    opened = 0
    for _ in range(count):
        # Per-order MCGuard re-check
        mc = _check_mc_guard(sess, client)
        if mc in ("WARNING", "DANGER", "EMERGENCY"):
            logger.warning("[Cascade:%s] MCGuard=%s blocked order", sess.session_id[:8], mc)
            break
        ticket = _place_order(sess, direction, client)
        if ticket:
            batch.tickets.append(ticket)
            sess.total_opened += 1
            opened += 1

    if batch.tickets:
        sess.batches.append(batch)
    return opened


def _place_order(sess: CascadeSession, direction: str, client: httpx.Client) -> Optional[int]:
    try:
        payload: dict = {
            "symbol":  sess.symbol,
            "action":  direction,
            "volume":  sess.volume,
            "comment": f"Cascade:{sess.session_id[:8]}",
        }
        if sess.hard_sl_pips > 0:
            payload["sl_pips"] = sess.hard_sl_pips

        r = client.post(f"{PYTHON_API}/python/mt5/order", json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            return data.get("order_id") or data.get("ticket")
        logger.error("[Cascade] Order rejected: %s", data)
        return None
    except Exception as exc:
        logger.error("[Cascade] Place order error: %s", exc)
        return None


_MAX_CONNECTION_FAILURES = 5   # stop session after this many consecutive MT5 connection failures

def _sync_positions(sess: CascadeSession, client: httpx.Client):
    """Remove tickets no longer open in MT5 — assume TP hit."""
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/positions")
        r.raise_for_status()
        sess.consecutive_connection_failures = 0   # reset on success
        open_tickets = {
            int(p["ticket"])
            for p in r.json()
            if p.get("symbol", "").upper() == sess.symbol.upper()
        }
        for batch in sess.batches:
            to_remove = [t for t in batch.tickets if t not in open_tickets]
            for t in to_remove:
                batch.tickets.remove(t)
                batch.closed_tp      += 1
                sess.total_closed_tp += 1
                sess.last_tp_direction = batch.direction   # track for NEUTRAL fallback
    except Exception as exc:
        sess.consecutive_connection_failures += 1
        logger.error(
            "[Cascade] Sync error (%d/%d): %s",
            sess.consecutive_connection_failures, _MAX_CONNECTION_FAILURES, exc,
        )
        if sess.consecutive_connection_failures >= _MAX_CONNECTION_FAILURES:
            sess.error = (
                f"MT5 connection lost: {sess.consecutive_connection_failures} consecutive failures — session stopped"
            )
            sess.active = False


def _check_sl_conditions(sess: CascadeSession, client: httpx.Client, trend: str = ""):
    """Hard SL: close immediately when floating_loss >= sl_loss_multiplier × profit_target.
    No trend condition — speed is the priority for scalping momentum."""
    if sess.sl_loss_multiplier <= 0:
        return
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/positions")
        r.raise_for_status()
        positions = {
            int(p["ticket"]): p
            for p in r.json()
            if p.get("symbol", "").upper() == sess.symbol.upper()
        }
        threshold = sess.sl_loss_multiplier * abs(sess.profit_target)
        for batch in sess.batches:
            for ticket in list(batch.tickets):
                pos = positions.get(ticket)
                if not pos:
                    continue
                pos_profit = float(pos.get("profit", 0))
                if pos_profit >= 0:
                    continue
                floating_loss = abs(pos_profit)
                if floating_loss >= threshold:
                    logger.warning(
                        "[Cascade:%s] Hard SL #%d loss=$%.2f >= threshold=$%.2f — closing",
                        sess.session_id[:8], ticket, floating_loss, threshold,
                    )
                    _close_ticket(sess, ticket, batch, client, reason="sl")
                    sess.last_action = (
                        f"Hard SL #{ticket}: -${floating_loss:.2f} "
                        f"(threshold=${threshold:.2f})"
                    )
    except Exception as exc:
        logger.error("[Cascade] SL check error: %s", exc)


def _close_ticket(
    sess: CascadeSession,
    ticket: int,
    batch: DirectionBatch,
    client: httpx.Client,
    reason: str,
):
    try:
        r = client.post(
            f"{PYTHON_API}/python/mt5/close",
            json={"ticket": ticket, "comment": f"Cascade:{reason}"},
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success") and ticket in batch.tickets:
            batch.tickets.remove(ticket)
            sess.total_profit += float(data.get("profit", 0))
            if reason == "sl":
                batch.closed_sl    += 1
                sess.total_closed_sl += 1
    except Exception as exc:
        logger.error("[Cascade] Close #%d error: %s", ticket, exc)


def _close_worst_positions(sess: CascadeSession, n: int, client: httpx.Client):
    """Close the N most losing positions for DANGER mitigation."""
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/positions")
        r.raise_for_status()
        all_open = sorted(
            [p for p in r.json() if p.get("symbol", "").upper() == sess.symbol.upper()],
            key=lambda p: float(p.get("profit", 0)),
        )
        ticket_to_batch = {t: b for b in sess.batches for t in b.tickets}
        for pos in all_open[:n]:
            ticket = int(pos["ticket"])
            batch  = ticket_to_batch.get(ticket)
            if batch:
                _close_ticket(sess, ticket, batch, client, reason="danger")
    except Exception as exc:
        logger.error("[Cascade] Close worst error: %s", exc)


def _check_profit_guard(sess: CascadeSession, client: httpx.Client) -> bool:
    """
    Profit Guard: two-layer session protection.
      1. Floor:    stop if total_net <= -max_session_loss_usd
      2. Drawdown: stop if total_net < peak_profit - max_drawdown_from_peak
    Returns True if triggered.
    """
    if sess.max_session_loss_usd <= 0 and sess.max_drawdown_from_peak <= 0:
        return False
    try:
        r = client.get(f"{PYTHON_API}/python/mt5/positions")
        r.raise_for_status()
        all_tickets = {t for b in sess.batches for t in b.tickets}
        floating = sum(
            float(p.get("profit", 0))
            for p in r.json()
            if p.get("symbol", "").upper() == sess.symbol.upper()
            and int(p.get("ticket", 0)) in all_tickets
        )
        sess.floating_pnl = round(floating, 2)
    except Exception as exc:
        logger.error("[Cascade] Profit guard fetch error: %s", exc)
        return False

    total_net = sess.total_profit + sess.floating_pnl

    # Peak only tracks AFTER at least one realized profit exists.
    # Prevents phantom peak from momentary floating spikes before any TP hit.
    if sess.total_profit > 0 and total_net > sess.peak_profit:
        sess.peak_profit = total_net

    if sess.max_session_loss_usd > 0:
        if total_net <= -sess.max_session_loss_usd:
            sess.last_action = (
                f"PROFIT GUARD (floor): net=${total_net:.2f} ≤ -${sess.max_session_loss_usd:.2f} → stopping"
            )
            logger.warning("[Cascade:%s] %s", sess.session_id[:8], sess.last_action)
            return True

    if sess.max_drawdown_from_peak > 0 and sess.peak_profit > 0:
        if total_net < sess.peak_profit - sess.max_drawdown_from_peak:
            sess.last_action = (
                f"PROFIT GUARD (drawdown): net=${total_net:.2f} dropped "
                f"${sess.peak_profit - total_net:.2f} from peak=${sess.peak_profit:.2f} → stopping"
            )
            logger.warning("[Cascade:%s] %s", sess.session_id[:8], sess.last_action)
            return True

    return False


def _close_all_positions(sess: CascadeSession, client: httpx.Client):
    """Emergency: close everything via close-all endpoint."""
    try:
        r = client.post(f"{PYTHON_API}/python/mt5/close-all", json={"filter": "all"})
        r.raise_for_status()
        data = r.json()
        sess.total_closed_emergency += data.get("closed", 0)
        sess.total_profit           += data.get("total_profit", 0.0)
        sess.floating_pnl = 0.0   # positions are gone — no more floating
        for batch in sess.batches:
            batch.tickets.clear()
    except Exception as exc:
        logger.error("[Cascade] Emergency close error: %s", exc)
