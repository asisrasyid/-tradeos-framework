"""Signal Engine router — START / STOP / STATUS endpoints."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.signal_engine import (
    EngineSession,
    start_session,
    stop_session,
    get_all_status,
    get_last_signal_for_symbol,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Default C# callback URL — can be overridden per request
_DEFAULT_CALLBACK = "http://localhost:5184/api/signals/ingest"


# ── Request / Response models ─────────────────────────────────────────────────

class StartEngineRequest(BaseModel):
    session_id:           Optional[str]  = None
    theory_id:            str
    instrument:           str
    timeframe:            str
    pattern_states:       list[int]
    similarity_threshold: float          = 0.60
    direction:            str            = "LONG"
    tp_mult:              float          = 2.0
    sl_mult:              float          = 1.0
    auto_execute:         bool           = False   # True → place real MT5 order
    volume:               float          = 0.01    # lot size (only used when auto_execute=True)
    callback_url:         Optional[str]  = None


class StopEngineRequest(BaseModel):
    session_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start(req: StartEngineRequest) -> dict:
    """
    Start a live signal engine session for a theory.
    The engine will evaluate on every bar close and POST a signal to callback_url
    whenever pattern similarity >= similarity_threshold.
    """
    if not req.pattern_states:
        raise HTTPException(status_code=400, detail="pattern_states must not be empty")

    session_id   = req.session_id or str(uuid.uuid4())
    callback_url = req.callback_url or _DEFAULT_CALLBACK

    sess = EngineSession(
        session_id           = session_id,
        theory_id            = req.theory_id,
        instrument           = req.instrument.upper(),
        timeframe            = req.timeframe.upper(),
        pattern_states       = req.pattern_states,
        similarity_threshold = req.similarity_threshold,
        direction            = req.direction.upper(),
        tp_mult              = req.tp_mult,
        sl_mult              = req.sl_mult,
        auto_execute         = req.auto_execute,
        volume               = req.volume,
        callback_url         = callback_url,
    )

    start_session(sess)

    return {
        "session_id":  session_id,
        "status":      "started",
        "instrument":  sess.instrument,
        "timeframe":   sess.timeframe,
        "callback_url": callback_url,
    }


@router.post("/stop")
async def stop(req: StopEngineRequest) -> dict:
    """Stop a running engine session by session_id."""
    was_running = stop_session(req.session_id)
    if not was_running:
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found or already stopped")
    return {
        "session_id": req.session_id,
        "status":     "stopped",
    }


@router.get("/status")
async def status() -> dict:
    """List all engine sessions (running, stopped, error) with diagnostics."""
    return {"sessions": get_all_status()}


@router.get("/last-signal")
async def last_signal(symbol: str) -> dict:
    """Return the most recent fired HMM signal for a symbol.
    Used by AGGR/CASCADE HMM filter to gate position opens.
    Returns: { found, symbol, direction (LONG|SHORT), similarity, age_s, timeframe }
    """
    return get_last_signal_for_symbol(symbol.upper())
