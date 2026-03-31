"""OHLC Data management router — status sync + manual trigger."""

import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ManualSyncRequest(BaseModel):
    instrument: Optional[str] = None
    timeframe:  Optional[str] = None


@router.get("/status")
async def sync_status() -> dict:
    """
    Return status sync OHLC semua instrument/timeframe dari ohlc_sync_log.
    """
    from services.ohlc_store import get_all_sync_status
    rows = await get_all_sync_status()
    return {"syncs": rows, "count": len(rows)}


@router.post("/sync")
async def manual_sync(req: ManualSyncRequest = ManualSyncRequest()) -> dict:
    """
    Trigger manual sync.
    - Tanpa body → sync semua TF untuk target symbol (XAUUSDc)
    - instrument saja → sync semua TF untuk instrument tersebut
    - instrument + timeframe → sync satu TF spesifik
    """
    from services.ohlc_syncer import trigger_manual_sync
    results = await trigger_manual_sync(req.instrument, req.timeframe)
    total_added = sum(r.get("bars_added", 0) for r in results)
    return {
        "results": results,
        "total_bars_added": total_added,
    }
