"""
equity_cache.py — Shared MT5 equity snapshot for all trading engines.

Problem solved:
  If multiple sessions (e.g. 3 Aggressive + 1 Cascade) each query MT5 equity
  independently, they can all trigger DANGER/EMERGENCY simultaneously and
  close many positions at once (over-closing race condition).

Solution:
  - One background thread refreshes equity every REFRESH_INTERVAL_S seconds.
  - All engines read from the cache (get_equity_snapshot()).
  - Emergency coordination: once one engine acts on EMERGENCY, it sets a lock
    for EMERGENCY_LOCK_S seconds so others skip the action.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

PYTHON_API         = "http://localhost:8001"
REFRESH_INTERVAL_S = 3      # refresh equity every 3 seconds
EMERGENCY_LOCK_S   = 30     # hold emergency lock for 30 seconds after first trigger
STALE_THRESHOLD_S  = 10     # snapshot older than 10s is considered stale (fail-open)

_lock    = threading.Lock()
_cache: dict = {
    "balance":      0.0,
    "equity":       0.0,
    "free_margin":  0.0,
    "last_updated": 0.0,   # unix timestamp
}
_emergency_lock_until: float = 0.0   # timestamp until which emergency action is locked


def get_equity_snapshot() -> dict:
    """Return the most recent cached equity data.
    Returns a copy — safe to read without holding the lock.
    If stale (>10s), returns last known values (fail-open — don't block engines).
    """
    with _lock:
        return dict(_cache)


def is_snapshot_fresh() -> bool:
    """True if snapshot was updated within STALE_THRESHOLD_S seconds."""
    with _lock:
        return (time.time() - _cache["last_updated"]) < STALE_THRESHOLD_S


def claim_emergency_action() -> bool:
    """Try to claim the right to act on EMERGENCY.
    Returns True if this caller should act (lock acquired).
    Returns False if another engine already claimed it (skip action).
    """
    global _emergency_lock_until
    now = time.time()
    with _lock:
        if now < _emergency_lock_until:
            return False   # already claimed by another engine
        _emergency_lock_until = now + EMERGENCY_LOCK_S
        return True


def release_emergency_lock() -> None:
    """Explicitly release the emergency lock (call after action completes)."""
    global _emergency_lock_until
    with _lock:
        _emergency_lock_until = 0.0


def _refresh_loop() -> None:
    """Background thread: continuously refresh equity snapshot from MT5."""
    client = httpx.Client(timeout=5)
    while True:
        try:
            r = client.get(f"{PYTHON_API}/python/mt5/account")
            r.raise_for_status()
            acc = r.json()
            with _lock:
                _cache["balance"]      = float(acc.get("balance",     0))
                _cache["equity"]       = float(acc.get("equity",      0))
                _cache["free_margin"]  = float(acc.get("free_margin", 0))
                _cache["last_updated"] = time.time()
        except Exception as exc:
            logger.debug("[EquityCache] Refresh failed: %s", exc)
            # Do not update last_updated — callers will see stale data and fail-open
        time.sleep(REFRESH_INTERVAL_S)


_refresh_thread = threading.Thread(
    target=_refresh_loop, daemon=True, name="equity-cache-refresh"
)
_refresh_thread.start()
