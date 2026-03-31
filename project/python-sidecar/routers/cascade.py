"""Cascade Engine router — /python/cascade/*"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services import cascade_engine as eng

router = APIRouter()


class StartCascadeRequest(BaseModel):
    symbol:               str   = "XAUUSDm"
    initial_batch:        int   = Field(10,  ge=1, le=50)
    topup_batch:          int   = Field(5,   ge=1, le=20)
    volume:               float = Field(0.01, ge=0.01, le=10.0)
    profit_target:        float = Field(2.0,  ge=0.1)    # USD — base for SL threshold
    hard_sl_pips:         float = Field(0.0,  ge=0.0)    # broker-level SL pips (0 = disabled)
    sl_loss_multiplier:   float = Field(1.0,  ge=0.0)    # hard SL: close when loss >= N × profit_target; 1.0 = break-even at 50% winrate
    max_positions:        int   = Field(30,   ge=1, le=200)
    eval_interval:        int   = Field(300,  ge=30, le=3600)  # seconds

    # MCGuard
    mc_level_pct:           float = Field(0.10, ge=0.05, le=0.50)
    safety_multiplier:      float = Field(3.0,  ge=1.5,  le=10.0)
    emergency_multiplier:   float = Field(1.5,  ge=1.0,  le=5.0)
    # Profit Guard
    max_session_loss_usd:   float = Field(0.0,  ge=0.0)
    max_drawdown_from_peak: float = Field(0.0,  ge=0.0)


class StopCascadeRequest(BaseModel):
    session_id: str


@router.post("/start")
async def start(req: StartCascadeRequest):
    sid = eng.start_session(
        symbol               = req.symbol,
        initial_batch        = req.initial_batch,
        topup_batch          = req.topup_batch,
        volume               = req.volume,
        profit_target        = req.profit_target,
        hard_sl_pips         = req.hard_sl_pips,
        sl_loss_multiplier   = req.sl_loss_multiplier,
        max_positions        = req.max_positions,
        eval_interval        = req.eval_interval,
        mc_level_pct         = req.mc_level_pct,
        safety_multiplier    = req.safety_multiplier,
        emergency_multiplier    = req.emergency_multiplier,
        max_session_loss_usd    = req.max_session_loss_usd,
        max_drawdown_from_peak  = req.max_drawdown_from_peak,
    )
    return {"session_id": sid, "status": "started"}


@router.post("/stop")
async def stop(req: StopCascadeRequest):
    ok = eng.stop_session(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": req.session_id, "status": "stopped"}


@router.get("/status")
async def status():
    return {"sessions": eng.get_all_status()}
