"""MetaTrader 5 router — account management, OHLC history, live order execution."""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from services import mt5_executor

logger = logging.getLogger(__name__)
router = APIRouter()

# ── MT5 import ───────────────────────────────────────────────────────────────
# lib_local disabled: use system-installed MetaTrader5 for Python 3.12
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False
    logger.warning("[MT5] MetaTrader5 package not available")


def _require_mt5():
    if not _MT5_AVAILABLE:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not installed")


def _ensure_connected() -> bool:
    return mt5_executor.ensure_connected()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MT5LoginRequest(BaseModel):
    login: int
    password: str
    server: str


class MT5AccountInfo(BaseModel):
    login: int
    name: str
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    leverage: int
    trade_allowed: bool


class OHLCRequest(BaseModel):
    symbol: str       # e.g. "XAUUSD"
    timeframe: str    # "M1","M5","M15","H1","H4","D1"
    bars: int = 500


class OHLCBar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


class OHLCResponse(BaseModel):
    symbol: str
    timeframe: str
    bars: list[OHLCBar]


class OrderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    symbol: str
    action: str
    volume: float = 0.01
    sl_pips:  Optional[float] = Field(None, alias="slPips")
    tp_pips:  Optional[float] = Field(None, alias="tpPips")
    sl_price: Optional[float] = None   # absolute SL price (takes precedence over sl_pips)
    tp_price: Optional[float] = None   # absolute TP price (takes precedence over tp_pips)
    comment: str = "TradeOS"
    magic: int = 20260325


class OrderResult(BaseModel):
    success: bool
    order_id: int
    retcode: int
    retcode_desc: str
    symbol: str
    action: str
    volume: float
    price: float
    sl: float
    tp: float
    comment: str


class CloseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ticket: int
    volume: Optional[float] = None
    comment: str = "TradeOS close"


class CloseResult(BaseModel):
    success: bool
    ticket: int
    retcode: int
    retcode_desc: str
    profit: float


class CloseAllRequest(BaseModel):
    filter: str = "all"   # "all" | "profit" | "loss"


class CloseAllResult(BaseModel):
    closed: int
    failed: int
    total_profit: float


class PositionInfo(BaseModel):
    ticket: int
    symbol: str
    type: str          # "BUY" | "SELL"
    volume: float
    open_price: float
    sl: float
    tp: float
    profit: float
    swap: float
    comment: str
    open_time: str


# ── Timeframe map ─────────────────────────────────────────────────────────────

TF_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "H8": 16392,
    "D1": 16408, "W1": 32769, "MN1": 49153,
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/connect", response_model=MT5AccountInfo)
async def connect(req: MT5LoginRequest) -> MT5AccountInfo:
    """Login to MT5 with credentials and return account info."""
    _require_mt5()
    ok = mt5.initialize(login=req.login, password=req.password, server=req.server)
    if not ok:
        code, msg = mt5.last_error()
        raise HTTPException(status_code=401, detail=f"MT5 login failed [{code}]: {msg}")
    return _get_account_info()


@router.get("/account", response_model=MT5AccountInfo)
async def get_account() -> MT5AccountInfo:
    """Get current account info (must be connected first)."""
    _require_mt5()
    if not _ensure_connected():
        code, msg = mt5.last_error()
        raise HTTPException(status_code=503, detail=f"MT5 not connected [{code}]: {msg}")
    return _get_account_info()


@router.post("/ohlc", response_model=OHLCResponse)
async def get_ohlc(req: OHLCRequest) -> OHLCResponse:
    """Fetch OHLC bars from MT5 for a given symbol and timeframe."""
    _require_mt5()
    if not _ensure_connected():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    tf_int = TF_MAP.get(req.timeframe.upper())
    if tf_int is None:
        raise HTTPException(status_code=400, detail=f"Unknown timeframe: {req.timeframe}")

    rates = mt5.copy_rates_from_pos(req.symbol, tf_int, 0, req.bars)
    if rates is None or len(rates) == 0:
        code, msg = mt5.last_error()
        raise HTTPException(status_code=404, detail=f"No data for {req.symbol} [{code}]: {msg}")

    bars = [
        OHLCBar(
            time=datetime.fromtimestamp(r["time"], tz=timezone.utc).isoformat(),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            tick_volume=int(r["tick_volume"]),
        )
        for r in rates
    ]
    return OHLCResponse(symbol=req.symbol, timeframe=req.timeframe.upper(), bars=bars)


@router.post("/order", response_model=OrderResult)
async def send_order(req: OrderRequest) -> OrderResult:
    """Send a market order (BUY or SELL) to MT5 via mt5_executor."""
    _require_mt5()

    action = req.action.upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="action must be BUY or SELL")

    # Resolve pip-based SL/TP to absolute prices when needed
    sl_price = req.sl_price or 0.0
    tp_price = req.tp_price or 0.0

    if (not sl_price or not tp_price) and (req.sl_pips or req.tp_pips):
        # Need current price + point to compute pip-based levels
        if not _ensure_connected():
            raise HTTPException(status_code=503, detail="MT5 not connected")
        sym_info = mt5.symbol_info(req.symbol)
        tick     = mt5.symbol_info_tick(req.symbol)
        if sym_info is None or tick is None:
            raise HTTPException(status_code=404, detail=f"Symbol info unavailable: {req.symbol}")
        is_buy = action == "BUY"
        price  = tick.ask if is_buy else tick.bid
        point  = sym_info.point
        if not sl_price and req.sl_pips and req.sl_pips > 0:
            sl_price = price - req.sl_pips * point if is_buy else price + req.sl_pips * point
        if not tp_price and req.tp_pips and req.tp_pips > 0:
            tp_price = price + req.tp_pips * point if is_buy else price - req.tp_pips * point

    try:
        res = mt5_executor.place_order(
            symbol   = req.symbol,
            action   = action,
            volume   = req.volume,
            sl_price = sl_price,
            tp_price = tp_price,
            comment  = req.comment,
            magic    = req.magic,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return OrderResult(
        success      = res["success"],
        order_id     = res["order_id"],
        retcode      = res["retcode"],
        retcode_desc = _retcode_desc(res["retcode"]),
        symbol       = req.symbol,
        action       = action,
        volume       = res["volume"],
        price        = res["fill_price"],
        sl           = res["sl"],
        tp           = res["tp"],
        comment      = req.comment,
    )


@router.post("/close", response_model=CloseResult)
async def close_position(req: CloseRequest) -> CloseResult:
    """Close or partially close an open position by ticket."""
    _require_mt5()
    if not _ensure_connected():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    positions = mt5.positions_get(ticket=req.ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position {req.ticket} not found")

    pos = positions[0]
    symbol = pos.symbol
    is_buy = pos.type == mt5.ORDER_TYPE_BUY  # closing buy = sell
    close_vol = req.volume if req.volume else pos.volume

    tick = mt5.symbol_info_tick(symbol)
    price = tick.bid if is_buy else tick.ask

    request = {
        "action":     mt5.TRADE_ACTION_DEAL,
        "symbol":     symbol,
        "volume":     close_vol,
        "type":       mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
        "position":   req.ticket,
        "price":      price,
        "deviation":  20,
        "magic":      pos.magic,
        "comment":    req.comment,
        "type_time":  mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        code, msg = mt5.last_error()
        raise HTTPException(status_code=500, detail=f"close failed [{code}]: {msg}")

    return CloseResult(
        success=result.retcode == mt5.TRADE_RETCODE_DONE,
        ticket=req.ticket,
        retcode=result.retcode,
        retcode_desc=_retcode_desc(result.retcode),
        profit=pos.profit,
    )


@router.get("/positions", response_model=list[PositionInfo])
async def get_positions() -> list[PositionInfo]:
    """Get all open positions."""
    _require_mt5()
    if not _ensure_connected():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    positions = mt5.positions_get()
    if positions is None:
        return []

    return [
        PositionInfo(
            ticket=p.ticket,
            symbol=p.symbol,
            type="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            volume=p.volume,
            open_price=p.price_open,
            sl=p.sl,
            tp=p.tp,
            profit=p.profit,
            swap=p.swap,
            comment=p.comment,
            open_time=datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
        )
        for p in positions
    ]


class ClosedDealInfo(BaseModel):
    ticket:      int
    position_id: int
    symbol:      str
    type:        str      # "BUY" | "SELL"
    volume:      float
    price:       float
    profit:      float
    swap:        float
    commission:  float
    time:        str


@router.get("/deal-history", response_model=Optional[ClosedDealInfo])
async def get_deal_history(ticket: int) -> Optional[ClosedDealInfo]:
    """
    Fetch the closing deal for a given position ticket from MT5 history.
    Returns None if position is still open or not found in history.
    Used by OutcomePoller to determine WIN/LOSS outcome.
    """
    _require_mt5()
    if not _ensure_connected():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    from datetime import timedelta

    # Search recent history (last 30 days)
    dt_from = datetime.now(timezone.utc) - timedelta(days=30)
    dt_to   = datetime.now(timezone.utc)

    # Get all deals for this position
    deals = mt5.history_deals_get(dt_from, dt_to, position=ticket)
    if not deals:
        return None

    # Find the exit deal (DEAL_ENTRY_OUT = 1)
    DEAL_ENTRY_OUT = 1
    exit_deals = [d for d in deals if d.entry == DEAL_ENTRY_OUT]
    if not exit_deals:
        return None

    d = exit_deals[-1]  # last exit deal
    return ClosedDealInfo(
        ticket      = d.ticket,
        position_id = d.position_id,
        symbol      = d.symbol,
        type        = "BUY" if d.type == mt5.ORDER_TYPE_BUY else "SELL",
        volume      = d.volume,
        price       = d.price,
        profit      = d.profit,
        swap        = d.swap,
        commission  = d.commission,
        time        = datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
    )


@router.post("/close-all", response_model=CloseAllResult)
async def close_all(req: CloseAllRequest) -> CloseAllResult:
    """Close all open positions filtered by profit/loss/all."""
    _require_mt5()
    if not _ensure_connected():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    filter_type = req.filter.lower()
    if filter_type not in ("all", "profit", "loss"):
        raise HTTPException(status_code=400, detail="filter must be all, profit, or loss")

    positions = mt5.positions_get()
    if not positions:
        return CloseAllResult(closed=0, failed=0, total_profit=0.0)

    if filter_type == "profit":
        to_close = [p for p in positions if p.profit > 0]
    elif filter_type == "loss":
        to_close = [p for p in positions if p.profit < 0]
    else:
        to_close = list(positions)

    closed = 0
    failed = 0
    total_profit = 0.0

    for pos in to_close:
        symbol = pos.symbol
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            failed += 1
            continue
        price = tick.bid if is_buy else tick.ask
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       pos.volume,
            "type":         mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position":     pos.ticket,
            "price":        price,
            "deviation":    20,
            "magic":        pos.magic,
            "comment":      f"TradeOS close-{filter_type}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            total_profit += pos.profit
        else:
            failed += 1

    return CloseAllResult(closed=closed, failed=failed, total_profit=total_profit)


@router.delete("/disconnect")
async def disconnect():
    """Shutdown MT5 connection."""
    _require_mt5()
    mt5.shutdown()
    return {"status": "disconnected"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_account_info() -> MT5AccountInfo:
    acc = mt5.account_info()
    if acc is None:
        raise HTTPException(status_code=503, detail="Cannot get account info")
    return MT5AccountInfo(
        login=acc.login,
        name=acc.name,
        server=acc.server,
        currency=acc.currency,
        balance=acc.balance,
        equity=acc.equity,
        margin=acc.margin,
        free_margin=acc.margin_free,
        profit=acc.profit,
        leverage=acc.leverage,
        trade_allowed=bool(acc.trade_allowed),
    )


_RETCODE_MAP = {
    10004: "Requote", 10006: "Request rejected", 10007: "Request cancelled",
    10008: "Order placed", 10009: "Request completed", 10010: "Only part of request completed",
    10011: "Request processing error", 10012: "Request cancelled by timeout",
    10013: "Invalid request", 10014: "Invalid volume", 10015: "Invalid price",
    10016: "Invalid stops", 10017: "Trade disabled", 10018: "Market closed",
    10019: "Not enough money", 10020: "Prices changed", 10021: "No quotes",
    10022: "Invalid order expiration", 10023: "Order state changed",
    10024: "Too many requests", 10025: "No changes", 10026: "Autotrading disabled",
    10027: "Agent blocked", 10028: "Locked", 10029: "Frozen",
    10030: "Invalid fill type", 10031: "Connection lost", 10032: "Allowed only for real",
    10033: "Limit orders exceeded", 10034: "Volume limit exceeded",
    10035: "Invalid order type", 10036: "Position already closed",
}

def _retcode_desc(code: int) -> str:
    return _RETCODE_MAP.get(code, f"Code {code}")
