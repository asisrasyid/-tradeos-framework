"""Aggressive Layer Trading Engine — start/stop/status endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services import aggressive_engine as eng

router = APIRouter()


class StartAggressiveRequest(BaseModel):
    symbol:               str   = "XAUUSDm"
    direction:            str   = "BUY"        # BUY | SELL | BOTH
    layers:               int   = Field(10, ge=1, le=50)
    volume:               float = Field(0.01, gt=0)
    profit_target:        float = Field(0.5, gt=0)   # USD profit per position to trigger close
    sl_pips:              float = Field(0.0,  ge=0)  # 0 = no SL (engine monitors profit instead)
    tp_pips:              float = Field(0.0,  ge=0)  # 0 = use profit_target monitoring only
    # Anti-trap / flip settings
    flip_mode:            str   = "none"       # none | percentile | counter | hybrid
    flip_percentile:      float = Field(0.80, ge=0.5, le=1.0)  # price range threshold to flip
    flip_after:           int   = Field(3, ge=1, le=20)        # consecutive TPs before flip
    lookback_bars:        int   = Field(20, ge=5, le=200)      # M1 bars for range calc
    # Cascade merge: trend-guided re-open (EMA M1+M5+M15 — primary direction filter)
    trend_guided:         bool  = True         # default ON: EMA trend as tactical filter
    # MCGuard — equity protection
    mc_guard:             bool  = False
    mc_level_pct:         float = Field(0.10, ge=0.01, le=0.5)
    safety_multiplier:    float = Field(3.0,  ge=1.0)
    emergency_multiplier: float = Field(1.5,  ge=1.0)
    # Per-position SL — close bleeding positions immediately
    sl_loss_multiplier:     float = Field(1.0, ge=0)   # 0=disabled; 1.0=break-even at 50% winrate (recommended)
    # SL Cooldown — pause before reopen after SL (avoid revenge trades)
    sl_cooldown_sec:        float = Field(0.0, ge=0)   # 0=disabled; e.g. 30 = wait 30s after SL before reopen
    # Profit Guard — session-level net protection
    max_session_loss_usd:   float = Field(0.0, ge=0)   # 0 = disabled; stop if net loss exceeds this
    max_drawdown_from_peak: float = Field(0.0, ge=0)   # 0 = disabled; stop if profit drops this much from peak
    # HMM Gate — danger detection + cooldown (default OFF)
    hmm_gate_enabled:       bool  = False              # enable HMM danger gate
    hmm_cooldown_sec:       float = Field(60.0, ge=0)  # cooldown duration in seconds on danger
    # Auto Direction via HMM (default OFF)
    auto_direction_hmm:     bool  = False              # use HMM vote instead of EMA for AUTO direction
    # Limit Order — place pending BUY_LIMIT/SELL_LIMIT instead of market order (default OFF)
    limit_atr_mult:         float = Field(0.0, ge=0)   # 0 = disabled; e.g. 0.1 = 10% ATR offset
    pending_expiry_sec:     float = Field(15.0, ge=1)  # cancel pending if not filled within N seconds


class StopAggressiveRequest(BaseModel):
    session_id: str


@router.post("/start")
async def start(req: StartAggressiveRequest):
    direction = req.direction.upper()
    if direction not in ("BUY", "SELL", "BOTH", "AUTO"):
        raise HTTPException(status_code=400, detail="direction must be BUY, SELL, BOTH, or AUTO")

    flip_mode = req.flip_mode.lower()
    if flip_mode not in ("none", "percentile", "counter", "hybrid"):
        raise HTTPException(status_code=400, detail="flip_mode must be none, percentile, counter, or hybrid")

    session_id = eng.start_session(
        symbol               = req.symbol,
        direction            = direction,
        layers               = req.layers,
        volume               = req.volume,
        profit_target        = req.profit_target,
        sl_pips              = req.sl_pips,
        tp_pips              = req.tp_pips,
        flip_mode            = flip_mode,
        flip_percentile      = req.flip_percentile,
        flip_after           = req.flip_after,
        lookback_bars        = req.lookback_bars,
        trend_guided         = req.trend_guided,
        mc_guard             = req.mc_guard,
        mc_level_pct         = req.mc_level_pct,
        safety_multiplier    = req.safety_multiplier,
        emergency_multiplier = req.emergency_multiplier,
        sl_loss_multiplier      = req.sl_loss_multiplier,
        sl_cooldown_sec         = req.sl_cooldown_sec,
        max_session_loss_usd    = req.max_session_loss_usd,
        max_drawdown_from_peak  = req.max_drawdown_from_peak,
        hmm_gate_enabled        = req.hmm_gate_enabled,
        hmm_cooldown_sec        = req.hmm_cooldown_sec,
        auto_direction_hmm      = req.auto_direction_hmm,
        limit_atr_mult          = req.limit_atr_mult,
        pending_expiry_sec      = req.pending_expiry_sec,
    )
    return {
        "session_id":          session_id,
        "symbol":              req.symbol,
        "direction":           direction,
        "layers":              req.layers,
        "volume":              req.volume,
        "profit_target":       req.profit_target,
        "flip_mode":           flip_mode,
        "flip_percentile":     req.flip_percentile,
        "flip_after":          req.flip_after,
        "lookback_bars":       req.lookback_bars,
        "trend_guided":        req.trend_guided,
        "mc_guard":            req.mc_guard,
        "mc_level_pct":        req.mc_level_pct,
        "safety_multiplier":   req.safety_multiplier,
        "emergency_multiplier": req.emergency_multiplier,
        "sl_loss_multiplier":  req.sl_loss_multiplier,
        "status":              "started",
    }


@router.post("/stop")
async def stop(req: StopAggressiveRequest):
    ok = eng.stop_session(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": req.session_id, "status": "stopped"}


@router.get("/status")
async def status():
    return {"sessions": eng.get_all_status()}
