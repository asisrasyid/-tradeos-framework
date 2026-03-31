"""Backtest execution router — delegates to services/backtest_runner.py."""

import json
import logging
import pandas as pd
from fastapi import APIRouter, HTTPException
from models.schemas import BacktestRunRequest, BacktestRunResponse
from services.backtest_runner import run_backtest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest_endpoint(req: BacktestRunRequest) -> BacktestRunResponse:
    """
    Execute full candle-by-candle backtest for a theory snapshot.
    Delegates all computation to services/backtest_runner.py.
    """
    # Parse theory config
    try:
        theory_config = json.loads(req.theory_snapshot)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid theory_snapshot JSON: {e}")

    # Ensure HMM model loaded into classifier cache
    from routers.hmm import _fetch_historical, _fetch_historical_mt5, _ensure_model_loaded
    try:
        await _ensure_model_loaded(req.instrument, req.timeframe)
    except Exception as e:
        logger.warning(f"[Backtest] HMM model not loaded (will run without HMM): {e}")

    # Determine data source: "db" (default) atau "mt5" (direct fetch)
    data_source = str(req.params.get("data_source", "db")).lower()

    if data_source == "mt5":
        # Langsung fetch dari MT5, bypass DB cache
        logger.info(f"[Backtest] data_source=mt5 — fetch langsung dari MT5")
        try:
            import asyncio
            df_mt5 = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_historical_mt5,
                req.instrument, req.timeframe, req.date_from, req.date_to,
            )
            if df_mt5 is None or len(df_mt5) < 10:
                raise ValueError("MT5 returned insufficient data")
            df = df_mt5
            # Simpan ke DB sebagai cache setelah fetch MT5
            from services.ohlc_store import save_ohlc
            await save_ohlc(df, req.instrument, req.timeframe)
        except Exception as e:
            logger.warning(f"[Backtest] MT5 direct fetch failed ({e}), fallback ke DB")
            df = await _fetch_historical(req.instrument, req.timeframe, req.date_from, req.date_to)
    else:
        # Default: DB first, MT5 fallback (existing behaviour)
        df = await _fetch_historical(
            req.instrument, req.timeframe,
            req.date_from, req.date_to
        )

    if len(df) < 70:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical data: {len(df)} bars (need ≥ 70)"
        )

    # Extract SL/TP config from params
    backtest_config = {
        "sl_type":       req.params.get("sl_type",       "atr"),
        "sl_value":      float(req.params.get("sl_value",    1.0)),
        "tp_type":       req.params.get("tp_type",       "atr"),
        "tp_value":      float(req.params.get("tp_value",    2.0)),
        "max_hold_bars": int(req.params.get("max_hold_bars", 20)),
    }

    # Run backtest via service
    try:
        result = run_backtest(
            df              = df,
            theory_config   = theory_config,
            instrument      = req.instrument,
            timeframe       = req.timeframe,
            backtest_config = backtest_config,
        )
    except Exception as e:
        logger.exception(f"[Backtest] Runner failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}")

    from models.schemas import BacktestTradeSchema
    return BacktestRunResponse(
        session_id         = req.session_id,
        total_signals      = result.total_signals,
        wins               = result.wins,
        losses             = result.losses,
        breakeven          = result.breakeven,
        win_rate           = result.win_rate,
        profit_factor      = result.profit_factor,
        sharpe_ratio       = result.sharpe_ratio,
        sortino_ratio      = result.sortino_ratio,
        max_drawdown       = result.max_drawdown,
        avg_rr             = result.avg_rr,
        total_pips         = result.total_pips,
        equity_curve       = result.equity_curve,
        state_distribution = result.state_distribution,
        best_seq_repr      = result.best_seq_repr,
        worst_seq_repr     = result.worst_seq_repr,
        trades             = [BacktestTradeSchema(**t.__dict__) for t in result.trades],
        sl_type            = result.sl_type,
        sl_value           = result.sl_value,
        tp_type            = result.tp_type,
        tp_value           = result.tp_value,
        max_hold_bars      = result.max_hold_bars,
    )
