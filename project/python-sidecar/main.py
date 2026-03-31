"""
TradeOS Python Sidecar
FastAPI computation engine — called by C# backend only.
NOT exposed to the internet (internal port 8001).
"""

import sys, os
# lib_local disabled: numpy/pandas are installed for Python 3.12 system-wide
# _lib_local = os.path.join(os.path.dirname(__file__), "lib_local")
# if _lib_local not in sys.path:
#     sys.path.insert(0, _lib_local)

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    ohlc, features, hmm, ccode, backtest, pattern,
    mt5 as mt5_router,
    signal_engine as signal_engine_router,
    aggressive as aggressive_router,
    smart_aggressive as smart_aggressive_router,
    cascade as cascade_router,
    ohlc_data as ohlc_data_router,
    analysis as analysis_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tradeos-sidecar")


# ── Lifespan: startup / shutdown ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    logger.info("[startup] Inisialisasi schema DB…")
    try:
        from services.ohlc_store import init_schema
        await init_schema()
    except Exception as e:
        logger.error("[startup] init_schema gagal: %s", e)

    logger.info("[startup] Memulai OHLC background sync…")
    try:
        from services.ohlc_syncer import start_background_sync
        start_background_sync()
    except Exception as e:
        logger.error("[startup] start_background_sync gagal: %s", e)

    logger.info("[startup] TradeOS sidecar siap.")
    yield
    # ── SHUTDOWN ──
    logger.info("[shutdown] TradeOS sidecar berhenti.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TradeOS Python Sidecar",
    description="HMM + Bayesian computation engine. Internal use only.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Internal-only: allow C# API container
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://tradeos-api:5000", "http://localhost:5000", "http://localhost:5184"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(ohlc.router,                    prefix="/python/ohlc",             tags=["OHLC"])
app.include_router(features.router,                prefix="/python/features",          tags=["Features"])
app.include_router(hmm.router,                     prefix="/python/hmm",               tags=["HMM"])
app.include_router(ccode.router,                   prefix="/python/ccode",             tags=["C-Code"])
app.include_router(backtest.router,                prefix="/python/backtest",          tags=["Backtest"])
app.include_router(pattern.router,                 prefix="/python/pattern",           tags=["Pattern"])
app.include_router(mt5_router.router,              prefix="/python/mt5",               tags=["MT5"])
app.include_router(signal_engine_router.router,    prefix="/python/signal-engine",     tags=["Signal Engine"])
app.include_router(aggressive_router.router,       prefix="/python/aggressive",        tags=["Aggressive Engine"])
app.include_router(smart_aggressive_router.router, prefix="/python/smart-aggressive",  tags=["Smart Aggressive Engine"])
app.include_router(cascade_router.router,          prefix="/python/cascade",           tags=["Cascade Engine"])
app.include_router(ohlc_data_router.router,        prefix="/python/ohlc-data",         tags=["OHLC Data"])
app.include_router(analysis_router.router,             prefix="/python/analysis",          tags=["Analysis"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tradeos-python-sidecar"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
