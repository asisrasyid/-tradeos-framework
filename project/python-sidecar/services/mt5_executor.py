"""
MT5 Executor — direct in-process order placement.

Called by signal_engine for zero-latency execution.
No HTTP hops. mt5.order_send() is called directly in the same Python process.

Latency: ~10-30ms (MT5 server round-trip only).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# ── MT5 import ───────────────────────────────────────────────────────────────
# lib_local disabled: use system-installed MetaTrader5 for Python 3.12
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False
    logger.warning("[MT5Executor] MetaTrader5 package not available")


# ── Public helpers ────────────────────────────────────────────────────────────

def is_available() -> bool:
    return _MT5_AVAILABLE


def ensure_connected() -> bool:
    """Initialize MT5 if not already running (reads env vars)."""
    if not _MT5_AVAILABLE:
        return False
    if mt5.terminal_info() is None:
        login    = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server   = os.getenv("MT5_SERVER", "")
        if login and password and server:
            return mt5.initialize(login=login, password=password, server=server)
        return mt5.initialize()
    return True


# ── Order execution ───────────────────────────────────────────────────────────

def place_order(
    symbol:    str,
    action:    str,           # "BUY" | "SELL"
    volume:    float,
    sl_price:  float = 0.0,   # absolute SL price; 0 = no SL
    tp_price:  float = 0.0,   # absolute TP price; 0 = no TP
    comment:   str   = "TradeOS",
    magic:     int   = 20260325,
    deviation: int   = 20,
) -> dict:
    """
    Send a market order directly via MT5 API. No HTTP involved.

    Returns:
        dict with keys: success, order_id, retcode, fill_price, sl, tp, volume

    Raises:
        RuntimeError — MT5 not available / not connected / order_send error
        ValueError   — invalid action
    """
    if not _MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not available")
    if not ensure_connected():
        code, msg = mt5.last_error()
        raise RuntimeError(f"MT5 not connected [{code}]: {msg}")

    action = action.upper()
    if action not in ("BUY", "SELL"):
        raise ValueError(f"Invalid action: {action!r} — must be BUY or SELL")

    # Symbol info (cached by MT5 lib after first call)
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        raise RuntimeError(f"Symbol not found: {symbol}")
    if not sym_info.visible:
        mt5.symbol_select(symbol, True)
        sym_info = mt5.symbol_info(symbol)

    # Current market price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"No tick data for {symbol}")

    is_buy = action == "BUY"
    price  = tick.ask if is_buy else tick.bid
    digits = sym_info.digits

    sl = round(sl_price, digits) if sl_price > 0 else 0.0
    tp = round(tp_price, digits) if tp_price > 0 else 0.0

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       volume,
        "type":         mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    deviation,
        "magic":        magic,
        "comment":      comment,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"order_send returned None [{code}]: {msg}")

    success = result.retcode == mt5.TRADE_RETCODE_DONE
    if not success:
        logger.warning(
            "[MT5Executor] order_send retcode=%d (%s) symbol=%s action=%s",
            result.retcode, result.comment, symbol, action,
        )

    return {
        "success":    success,
        "order_id":   result.order,
        "retcode":    result.retcode,
        "fill_price": result.price,   # actual fill price from broker
        "sl":         sl,
        "tp":         tp,
        "volume":     result.volume,
    }


def place_limit_order(
    symbol:      str,
    action:      str,          # "BUY" | "SELL"
    volume:      float,
    limit_price: float,        # price at which the order should fill
    sl_price:    float = 0.0,  # absolute SL price from limit_price; 0 = no SL
    tp_price:    float = 0.0,  # absolute TP price from limit_price; 0 = no TP
    comment:     str   = "TradeOS",
    magic:       int   = 20260325,
) -> dict:
    """
    Place a BUY_LIMIT or SELL_LIMIT pending order.
    Managed externally (tracked in session pending_tickets, cancelled via cancel_order).

    Returns:
        dict with keys: success, order_id, retcode, limit_price, sl, tp, volume
    """
    if not _MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not available")
    if not ensure_connected():
        code, msg = mt5.last_error()
        raise RuntimeError(f"MT5 not connected [{code}]: {msg}")

    action = action.upper()
    if action not in ("BUY", "SELL"):
        raise ValueError(f"Invalid action: {action!r} — must be BUY or SELL")

    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        raise RuntimeError(f"Symbol not found: {symbol}")
    if not sym_info.visible:
        mt5.symbol_select(symbol, True)
        sym_info = mt5.symbol_info(symbol)

    digits   = sym_info.digits
    is_buy   = action == "BUY"
    lp       = round(limit_price, digits)
    sl       = round(sl_price, digits) if sl_price > 0 else 0.0
    tp       = round(tp_price, digits) if tp_price > 0 else 0.0

    order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT

    request = {
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       symbol,
        "volume":       volume,
        "type":         order_type,
        "price":        lp,
        "sl":           sl,
        "tp":           tp,
        "magic":        magic,
        "comment":      comment,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    if result is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"order_send (limit) returned None [{code}]: {msg}")

    success = result.retcode == mt5.TRADE_RETCODE_DONE
    if not success:
        logger.warning(
            "[MT5Executor] limit order_send retcode=%d (%s) symbol=%s action=%s @%.5f",
            result.retcode, result.comment, symbol, action, lp,
        )

    return {
        "success":     success,
        "order_id":    result.order,
        "retcode":     result.retcode,
        "limit_price": lp,
        "sl":          sl,
        "tp":          tp,
        "volume":      volume,
    }


def cancel_order(ticket: int) -> bool:
    """Cancel a pending order by ticket. Returns True if successfully cancelled."""
    if not _MT5_AVAILABLE or not ensure_connected():
        return False
    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order":  ticket,
    }
    result = mt5.order_send(request)
    if result is None:
        code, msg = mt5.last_error()
        logger.warning("[MT5Executor] cancel_order #%d: order_send returned None [%d] %s", ticket, code, msg)
        return False
    ok = result.retcode == mt5.TRADE_RETCODE_DONE
    if not ok:
        logger.warning("[MT5Executor] cancel_order #%d retcode=%d (%s)", ticket, result.retcode, result.comment)
    return ok


def get_pending_tickets() -> set[int]:
    """Return the set of all current pending order tickets across all symbols."""
    if not _MT5_AVAILABLE or not ensure_connected():
        return set()
    orders = mt5.orders_get()
    if orders is None:
        return set()
    return {o.ticket for o in orders}


def get_symbol_info(symbol: str) -> Optional[dict]:
    """Return current tick + symbol metadata. Returns None if unavailable."""
    if not _MT5_AVAILABLE or not ensure_connected():
        return None
    tick     = mt5.symbol_info_tick(symbol)
    sym_info = mt5.symbol_info(symbol)
    if tick is None or sym_info is None:
        return None
    return {
        "ask":    tick.ask,
        "bid":    tick.bid,
        "digits": sym_info.digits,
        "point":  sym_info.point,
    }
