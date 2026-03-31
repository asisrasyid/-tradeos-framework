"""Smart Aggressive Engine — start/stop/status/resume endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services import smart_aggressive_engine as eng

router = APIRouter()


class StartSmartRequest(BaseModel):
    symbol:              str   = "XAUUSDm"
    timeframe:           str   = "M15"
    max_layers:          int   = Field(10, ge=1, le=50)
    open_per_interval:   int   = Field(1, ge=1, le=10)
    eval_interval_s:     int   = Field(30, ge=5, le=3600)
    volume:              float = Field(0.01, gt=0)
    tp_atr_mult:         float = Field(1.5, gt=0)
    sl_atr_mult:         float = Field(0.5, gt=0)
    min_atr:             float = Field(0.5, ge=0)
    max_atr:             float = Field(15.0, gt=0)
    min_confidence:      float = Field(0.70, ge=0, le=1)
    callback_url:        str   = ""
    # AI params
    ai_enabled:          bool  = False
    entries_per_decision:int   = Field(5, ge=1, le=20)
    max_calls_per_hour:  int   = Field(6, ge=1, le=60)


class StopSmartRequest(BaseModel):
    session_id: str


class ResumeAIRequest(BaseModel):
    session_id: str


@router.post("/start")
async def start(req: StartSmartRequest):
    session_id = eng.start_session(
        symbol               = req.symbol,
        timeframe            = req.timeframe,
        max_layers           = req.max_layers,
        open_per_interval    = req.open_per_interval,
        eval_interval_s      = req.eval_interval_s,
        volume               = req.volume,
        tp_atr_mult          = req.tp_atr_mult,
        sl_atr_mult          = req.sl_atr_mult,
        min_atr              = req.min_atr,
        max_atr              = req.max_atr,
        min_confidence       = req.min_confidence,
        callback_url         = req.callback_url,
        ai_enabled           = req.ai_enabled,
        entries_per_decision = req.entries_per_decision,
        max_calls_per_hour   = req.max_calls_per_hour,
    )
    return {"session_id": session_id, "status": "started", "ai_enabled": req.ai_enabled}


@router.post("/stop")
async def stop(req: StopSmartRequest):
    ok = eng.stop_session(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": req.session_id, "status": "stopped"}


@router.post("/resume-ai")
async def resume_ai(req: ResumeAIRequest):
    ok = eng.resume_ai(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": req.session_id, "status": "ai_resumed"}


@router.get("/status")
async def status():
    return {"sessions": eng.get_all_status()}
