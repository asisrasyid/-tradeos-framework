"""
Multi-timeframe HMM live analysis router.
Called every ~30s by the frontend for the live alert log panel.

Flow:
  1. Each TF analyzed independently (asyncio.gather, per-TF errors swallowed).
  2. Raw alerts tagged with group_key for deduplication.
  3. Alerts with same group_key merged → single entry with combined TF list.
  4. Confidence = base signal strength + TF-agreement bonus.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from services.feature_extractor import extract_features
from services.hmm_classifier import get_classifier

logger = logging.getLogger(__name__)
router = APIRouter()

# Bars to fetch per timeframe
BARS_PER_TF: dict[str, int] = {
    "M1": 60, "M5": 60, "M15": 80, "M30": 80, "H1": 100, "H4": 100,
}

# Canonical TF sort order for display
TF_ORDER = ["M1", "M5", "M15", "M30", "H1", "H4"]

# Feature indices (must match services/feature_extractor.py)
F_ATR, F_MOM, F_SWING, F_BODY, F_SLOPE, F_LIQ = 0, 1, 2, 3, 4, 5


# ── Internal raw alert (not serialized) ──────────────────────────────────────

@dataclass
class _Raw:
    tf:         str     # single TF, e.g. "H1"
    tag:        str     # STATE | S/R | LIQ | VOL | MOM | DIV
    msg:        str
    severity:   str     # info | warning | danger | divergence | system
    confidence: float   # 0.0–1.0
    group_key:  str     # used for cross-TF deduplication
    action:     str     # BUY | SELL | NEUTRAL


# ── Public response model ─────────────────────────────────────────────────────

class MultiTfRequest(BaseModel):
    instrument: str
    timeframes: List[str]


class AlertItem(BaseModel):
    tf:         str     # "M1,M5,H1" (merged) or "--" (cross-TF)
    tag:        str
    msg:        str
    severity:   str
    confidence: float   # 0.0–1.0
    action:     str     # BUY | SELL | NEUTRAL


# ── Confidence helpers ────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 0.97) -> float:
    return max(lo, min(hi, v))


def _conf_state(mom_z: float, htf_slope: float, direction: str) -> float:
    """
    Base confidence for an HMM state signal.
    direction: 'bull' | 'bear' | 'neutral'
    """
    base = 0.35
    mom_strength = min(abs(mom_z) / 3.0, 1.0) * 0.25
    alignment = 0.10 if (
        (direction == "bull" and htf_slope > 0) or
        (direction == "bear" and htf_slope < 0)
    ) else 0.0
    return _clamp(base + mom_strength + alignment)


def _conf_proximity(val: float, lo: float = 0.75) -> float:
    """Proximity confidence: linearly maps [lo, 1.0] → [0.45, 0.95]."""
    return _clamp(0.45 + (val - lo) / (1.0 - lo) * 0.50)


def _conf_vol_high(atr_val: float) -> float:
    return _clamp(0.55 + (atr_val - 0.85) / 0.15 * 0.35)


def _conf_mom(mom_abs: float, extreme: bool) -> float:
    if extreme:
        return _clamp(0.50 + min(mom_abs / 3.5, 1.0) * 0.45)
    return _clamp(0.40 + (mom_abs - 1.8) / 0.7 * 0.30)


def _conf_divergence(avg_ltf: float, avg_htf: float) -> float:
    magnitude = (abs(avg_ltf) + abs(avg_htf)) / 4.0
    return _clamp(0.40 + magnitude * 0.55)


# ── Merge group of raw alerts into one AlertItem ──────────────────────────────

def _merge(group: list[_Raw]) -> AlertItem:
    """
    Merge alerts with the same group_key.
    - tf:         sorted comma-joined list of TFs
    - msg:        from the highest-confidence item
    - confidence: max(individual) + agreement bonus
    - action:     from the highest-confidence item
    """
    tfs = sorted(
        {r.tf for r in group if r.tf != "--"},
        key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99,
    )
    n = len(tfs)
    base = max(r.confidence for r in group)
    # Each additional agreeing TF adds up to 4% (max +20% at n=6)
    bonus = (n - 1) / 5 * 0.20 if n > 1 else 0.0
    best = max(group, key=lambda r: r.confidence)
    return AlertItem(
        tf=",".join(tfs) if tfs else "--",
        tag=best.tag,
        msg=best.msg,
        severity=best.severity,
        confidence=round(_clamp(base + bonus), 2),
        action=best.action,
    )


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/multi-tf", response_model=List[AlertItem])
async def multi_tf_analysis(req: MultiTfRequest) -> List[AlertItem]:
    tf_momentum: dict[str, float] = {}
    tf_slope:    dict[str, float] = {}
    raw_pool:    list[_Raw]       = []

    async def analyze_tf(tf: str) -> list[_Raw]:
        result: list[_Raw] = []
        bars = BARS_PER_TF.get(tf.upper(), 80)
        try:
            from routers.ohlc import _fetch_from_mt5, _fetch_from_yfinance
            try:
                bl = await _fetch_from_mt5(req.instrument, tf, bars)
            except Exception:
                bl = await _fetch_from_yfinance(req.instrument, tf, bars)

            if not bl or len(bl) < 20:
                return []

            df     = pd.DataFrame([b.model_dump() for b in bl])
            matrix = extract_features(df)
            if matrix is None or len(matrix) == 0:
                return []

            feat      = matrix[-1]
            mom_val   = float(feat[F_MOM])
            swing_val = float(feat[F_SWING])
            liq_val   = float(feat[F_LIQ])
            atr_val   = float(feat[F_ATR])
            slope_val = float(feat[F_SLOPE])

            tf_momentum[tf.upper()] = mom_val
            tf_slope[tf.upper()]    = slope_val

            # ── 1. HMM STATE ──────────────────────────────────────────────
            clf = get_classifier()
            if clf.is_loaded(req.instrument, tf):
                clf_result = clf.classify_current_state(matrix, req.instrument, tf)
                lbl = clf_result.state_label.lower()
                bull_kw = ["bull", "up", "buy", "long", "breakout", "bullish"]
                bear_kw = ["bear", "down", "sell", "short", "breakdown", "bearish"]
                if any(k in lbl for k in bull_kw):
                    direction, sev, arrow, gkey, act = "bull",    "info",    "↑ Bullish", "STATE_BULL", "BUY"
                elif any(k in lbl for k in bear_kw):
                    direction, sev, arrow, gkey, act = "bear",    "warning", "↓ Bearish", "STATE_BEAR", "SELL"
                else:
                    direction, sev, arrow, gkey, act = "neutral", "info",    "→ Netral",  "STATE_NEUT", "NEUTRAL"
                result.append(_Raw(
                    tf=tf, tag="STATE",
                    msg=f"S{clf_result.state} ({clf_result.state_label}) · {arrow}",
                    severity=sev,
                    confidence=_conf_state(mom_val, slope_val, direction),
                    group_key=gkey,
                    action=act,
                ))

            # ── 2. S/R PROXIMITY ─────────────────────────────────────────
            if swing_val > 0.75:
                is_res = mom_val > 0
                level  = "resistance" if is_res else "support"
                hint   = "siapkan SELL / waspada pullback" if is_res else "siapkan BUY / waspada bounce"
                result.append(_Raw(
                    tf=tf, tag="S/R",
                    msg=f"Mendekati {level} (skor {swing_val:.2f}) — {hint}",
                    severity="warning",
                    confidence=_conf_proximity(swing_val),
                    group_key="SR_RES" if is_res else "SR_SUP",
                    action="SELL" if is_res else "BUY",
                ))

            # ── 3. LIQUIDITY PROXIMITY ────────────────────────────────────
            if liq_val > 0.75:
                result.append(_Raw(
                    tf=tf, tag="LIQ",
                    msg=f"Mendekati liquidity pool (skor {liq_val:.2f}) — potensi spike/reversal mendadak",
                    severity="warning",
                    confidence=_conf_proximity(liq_val),
                    group_key="LIQ",
                    action="NEUTRAL",
                ))

            # ── 4. VOLATILITY ─────────────────────────────────────────────
            if atr_val > 0.85:
                result.append(_Raw(
                    tf=tf, tag="VOL",
                    msg=f"Volatilitas tinggi (ATR pctile {atr_val:.2f}) — spread melebar, hindari entry",
                    severity="danger",
                    confidence=_conf_vol_high(atr_val),
                    group_key="VOL_HIGH",
                    action="NEUTRAL",
                ))
            elif atr_val < 0.10:
                result.append(_Raw(
                    tf=tf, tag="VOL",
                    msg=f"Volatilitas sangat rendah ({atr_val:.2f}) — pasar konsolidasi/choppy",
                    severity="info",
                    confidence=0.50,
                    group_key="VOL_LOW",
                    action="NEUTRAL",
                ))

            # ── 5. MOMENTUM EXTREME ───────────────────────────────────────
            mom_abs = abs(mom_val)
            if mom_abs > 2.5:
                cond = "overbought" if mom_val > 0 else "oversold"
                gkey = "MOM_OB" if mom_val > 0 else "MOM_OS"
                # Extreme overbought → contrarian SELL; extreme oversold → contrarian BUY
                act  = "SELL" if mom_val > 0 else "BUY"
                result.append(_Raw(
                    tf=tf, tag="MOM",
                    msg=f"Momentum ekstrem {cond} (z={mom_val:.2f}) — potensi koreksi kuat",
                    severity="danger",
                    confidence=_conf_mom(mom_abs, extreme=True),
                    group_key=gkey,
                    action=act,
                ))
            elif mom_abs > 1.8:
                cond = "bullish kuat" if mom_val > 0 else "bearish kuat"
                gkey = "MOM_BULL" if mom_val > 0 else "MOM_BEAR"
                act  = "BUY" if mom_val > 0 else "SELL"
                result.append(_Raw(
                    tf=tf, tag="MOM",
                    msg=f"Momentum {cond} (z={mom_val:.2f})",
                    severity="warning",
                    confidence=_conf_mom(mom_abs, extreme=False),
                    group_key=gkey,
                    action=act,
                ))

        except Exception as e:
            logger.warning("[analysis] TF %s failed: %s", tf, e)
        return result

    # Run all TFs concurrently
    gather_results = await asyncio.gather(
        *[analyze_tf(tf.upper()) for tf in req.timeframes],
        return_exceptions=True,
    )
    for res in gather_results:
        if isinstance(res, list):
            raw_pool.extend(res)

    # ── CROSS-TF DIVERGENCE ───────────────────────────────────────────────────
    ltf = [tf_momentum[t] for t in ["M1", "M5", "M15"] if t in tf_momentum]
    htf = [tf_momentum[t] for t in ["H1", "H4"]        if t in tf_momentum]
    if ltf and htf:
        avg_ltf = float(np.mean(ltf))
        avg_htf = float(np.mean(htf))
        if avg_ltf > 0.5 and avg_htf < -0.5:
            raw_pool.append(_Raw(
                tf="--", tag="DIV",
                msg=f"Divergensi bias: LTF bullish (z={avg_ltf:.2f}) vs HTF bearish (z={avg_htf:.2f}) — risiko bull trap",
                severity="divergence",
                confidence=_conf_divergence(avg_ltf, avg_htf),
                group_key="DIV_BULL",
                action="SELL",   # HTF bias wins → fade the LTF rally
            ))
        elif avg_ltf < -0.5 and avg_htf > 0.5:
            raw_pool.append(_Raw(
                tf="--", tag="DIV",
                msg=f"Divergensi bias: LTF bearish (z={avg_ltf:.2f}) vs HTF bullish (z={avg_htf:.2f}) — risiko bear trap",
                severity="divergence",
                confidence=_conf_divergence(avg_ltf, avg_htf),
                group_key="DIV_BEAR",
                action="BUY",    # HTF bias wins → fade the LTF drop
            ))

    # ── GROUP & MERGE by group_key ────────────────────────────────────────────
    groups: dict[str, list[_Raw]] = {}
    for r in raw_pool:
        groups.setdefault(r.group_key, []).append(r)

    return [_merge(group) for group in groups.values()]
