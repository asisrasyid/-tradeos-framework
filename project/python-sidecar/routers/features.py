"""Feature extraction router — delegates to services/feature_extractor.py."""

import logging
import pandas as pd
from fastapi import APIRouter, HTTPException
from models.schemas import FeatureExtractRequest, FeatureExtractResponse, FeatureVector
from services.feature_extractor import extract_features as _extract

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract", response_model=FeatureExtractResponse)
async def extract_features(req: FeatureExtractRequest) -> FeatureExtractResponse:
    """Convert OHLC JSON → 6 scale-invariant feature vectors (one per candle)."""
    try:
        df = pd.read_json(req.ohlc_json)
        df.columns = [c.lower() for c in df.columns]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ohlc_json: {e}")

    matrix = _extract(df)

    vectors = [
        FeatureVector(
            f0_atr_percentile=float(row[0]),
            f1_momentum_zscore=float(row[1]),
            f2_swing_proximity=float(row[2]),
            f3_body_dominance=float(row[3]),
            f4_htf_trend_slope=float(row[4]),
            f5_liquidity_proximity=float(row[5]),
        )
        for row in matrix
    ]

    return FeatureExtractResponse(
        instrument=req.instrument,
        timeframe=req.timeframe,
        features=vectors,
    )
