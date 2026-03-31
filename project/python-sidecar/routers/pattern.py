"""Pattern mining router — discovers profitable state sequences from WIN trades."""

import logging
from collections import defaultdict
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from models.schemas import PatternMineRequest, PatternMineResponse, MinedPattern

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/mine-from-wins", response_model=PatternMineResponse)
async def mine_from_wins(req: PatternMineRequest) -> PatternMineResponse:
    """
    Mine high-performance state sequences from existing WIN trades in the DB.
    Groups trades by state_seq_repr, computes win_rate, filters by threshold.
    """
    try:
        import asyncpg  # type: ignore
        import os
        import json

        conn_str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:P%40ss1234@localhost:5432/tradeos"
        )
        conn = await asyncpg.connect(conn_str)

        rows = await conn.fetch(
            """
            SELECT
                state_sequence->>'repr' AS seq_repr,
                COUNT(*) FILTER (WHERE outcome = 'WIN')  AS wins,
                COUNT(*) FILTER (WHERE outcome = 'LOSS') AS losses,
                COUNT(*) AS total,
                AVG((state_sequence->>'log_prob')::float) AS avg_log_prob
            FROM trade_log
            WHERE instrument = $1
              AND timeframe  = $2
              AND outcome IS NOT NULL
              AND state_sequence IS NOT NULL
            GROUP BY state_sequence->>'repr'
            HAVING COUNT(*) >= $3
            """,
            req.instrument, req.timeframe, req.min_occurrences
        )
        await conn.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")

    patterns: list[MinedPattern] = []
    for row in rows:
        wins  = row["wins"]  or 0
        total = row["total"] or 0
        win_rate = (wins + 1) / (total + 2)  # Laplace smoothed

        if win_rate >= req.min_win_rate:
            patterns.append(MinedPattern(
                state_seq_repr=row["seq_repr"] or "",
                win_rate=round(float(win_rate), 4),
                occurrences=int(total),
                avg_log_prob=round(float(row["avg_log_prob"] or 0.0), 4),
            ))

    # Sort by win_rate DESC
    patterns.sort(key=lambda p: p.win_rate, reverse=True)

    return PatternMineResponse(
        instrument=req.instrument,
        timeframe=req.timeframe,
        patterns=patterns,
    )


# ─── Pattern Match Score ──────────────────────────────────────────────────────

class PatternMatchRequest(BaseModel):
    instrument: str
    timeframe: str
    live_repr: str           # e.g. "S0S3S4"
    theory_id: Optional[str] = None


class PatternMatchResponse(BaseModel):
    match_score: float       # 0.0 – 1.0
    log_prob_ratio: float
    is_match: bool
    matched_pattern: Optional[str] = None


@router.post("/match", response_model=PatternMatchResponse)
async def match_pattern(req: PatternMatchRequest) -> PatternMatchResponse:
    """
    Compare live state sequence against patterns registered in the DB for this theory.
    Uses HMM classifier's compute_pattern_match_score (Markov transition probability).
    Falls back to exact string match if HMM model not loaded.
    """
    from services.hmm_classifier import get_classifier

    clf = get_classifier()

    # Query DB for patterns associated with this theory (or all patterns for instrument/tf)
    try:
        import asyncpg  # type: ignore
        import os, json, uuid

        conn_str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:P%40ss1234@localhost:5432/tradeos"
        )
        conn = await asyncpg.connect(conn_str)

        if req.theory_id:
            # Get patterns linked via theory_factors.pattern_id
            try:
                theory_uuid = uuid.UUID(req.theory_id)
                rows = await conn.fetch(
                    """
                    SELECT p.state_sequence, p.state_seq_repr
                    FROM patterns p
                    JOIN theory_factors tf ON tf.pattern_id = p.id
                    WHERE tf.theory_id = $1
                      AND p.is_active = TRUE
                      AND p.pattern_type = 'state_sequence'
                      AND p.deleted_at IS NULL
                    """,
                    theory_uuid,
                )
            except (ValueError, Exception):
                rows = []
        else:
            rows = []

        if not rows:
            # Fallback: all active state_sequence patterns for this timeframe
            rows = await conn.fetch(
                """
                SELECT state_sequence, state_seq_repr
                FROM patterns
                WHERE is_active = TRUE
                  AND pattern_type = 'state_sequence'
                  AND deleted_at IS NULL
                  AND (timeframe = $1 OR timeframe IS NULL)
                LIMIT 20
                """,
                req.timeframe.upper(),
            )

        await conn.close()

    except Exception as e:
        logger.warning(f"[pattern/match] DB query failed: {e}")
        rows = []

    if not rows:
        return PatternMatchResponse(match_score=0.0, log_prob_ratio=0.0, is_match=False)

    # Parse live repr into state list: "S0S3S4" → [0, 3, 4]
    import re
    live_states = [int(m.group(1)) for m in re.finditer(r"S(\d+)", req.live_repr)]

    best_score      = 0.0
    best_log_ratio  = 0.0
    best_repr       = None

    for row in rows:
        template_repr = row.get("state_seq_repr") or ""
        template_seq_json = row.get("state_sequence")

        # Try Markov-based match via classifier
        try:
            if clf.is_loaded(req.instrument, req.timeframe) and template_seq_json:
                template_states = json.loads(template_seq_json)
                score = clf.compute_pattern_match_score(live_states, template_states, req.instrument, req.timeframe)
                if score > best_score:
                    best_score     = score
                    best_repr      = template_repr
            else:
                # Exact repr match fallback
                if template_repr and template_repr == req.live_repr:
                    best_score = 1.0
                    best_repr  = template_repr
        except Exception as e:
            logger.debug(f"[pattern/match] score error: {e}")
            # Exact match fallback
            if template_repr == req.live_repr:
                best_score = 1.0
                best_repr  = template_repr

    return PatternMatchResponse(
        match_score=round(best_score, 4),
        log_prob_ratio=best_log_ratio,
        is_match=best_score >= 0.6,
        matched_pattern=best_repr,
    )
