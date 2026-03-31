"""
HMM Classifier — TradeOS v5.1
In-memory model cache, state classification, Viterbi sequence decoding,
and pattern match scoring via Markov transition probability.

Rules (guide_line.md):
  - Viterbi for sequence decoding (not forward algorithm)
  - Pattern = state sequence, NEVER raw candle shape
  - compute_pattern_match_score uses Markov transition probability
  - State sequence hash = SHA256 first 16 chars
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from hmmlearn.hmm import GaussianHMM  # type: ignore
from sklearn.preprocessing import StandardScaler  # type: ignore

logger = logging.getLogger(__name__)


# ─── Cached Model ────────────────────────────────────────────────────────────

@dataclass
class CachedModel:
    model: GaussianHMM
    scaler: StandardScaler
    version: str
    state_labels: dict[str, str]
    instrument: str
    timeframe: str


# ─── Output dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClassifyResult:
    state: int
    state_label: str
    model_version: str


@dataclass(frozen=True)
class SequenceResult:
    sequence: list[int]       # e.g. [0, 0, 3, 2, 4]
    repr: str                 # "S0S0S3S2S4"
    seq_hash: str             # SHA256 first 16 chars
    log_prob: float
    model_version: str


@dataclass(frozen=True)
class PatternMatchResult:
    match_score: float        # 0.0–1.0 (1.0 = perfect Markov match)
    log_prob_ratio: float     # log(live_path / template_path)
    is_match: bool            # True if match_score >= threshold


# ─── Classifier ──────────────────────────────────────────────────────────────

class HmmClassifier:
    """
    Thread-safe (read-only after load) in-memory model cache.
    One instance per process — shared across requests.
    """

    def __init__(self) -> None:
        # key: (instrument, timeframe) → CachedModel
        self._cache: dict[tuple[str, str], CachedModel] = {}

    def load_model(
        self,
        instrument: str,
        timeframe: str,
        model: GaussianHMM,
        scaler: StandardScaler,
        version: str,
        state_labels: dict[str, str],
    ) -> None:
        """Load (or replace) model for an instrument/timeframe pair."""
        key = (instrument.upper(), timeframe.upper())
        self._cache[key] = CachedModel(
            model=model,
            scaler=scaler,
            version=version,
            state_labels=state_labels,
            instrument=instrument,
            timeframe=timeframe,
        )
        logger.info(f"Model loaded into cache: {instrument}/{timeframe} [{version}]")

    def is_loaded(self, instrument: str, timeframe: str) -> bool:
        return (instrument.upper(), timeframe.upper()) in self._cache

    def get_cached(self, instrument: str, timeframe: str) -> Optional[CachedModel]:
        return self._cache.get((instrument.upper(), timeframe.upper()))

    # ── Classification ───────────────────────────────────────────────────────

    def classify_current_state(
        self,
        feature_matrix: np.ndarray,   # shape (N, 6) — recent candles
        instrument: str,
        timeframe: str,
    ) -> ClassifyResult:
        """
        Classify the market state of the LAST candle.
        Uses model.predict() on the full feature matrix for context.
        """
        cm = self._get_or_raise(instrument, timeframe)
        X = cm.scaler.transform(feature_matrix)
        states = cm.model.predict(X)
        last_state = int(states[-1])
        label = cm.state_labels.get(str(last_state), f"S{last_state}")
        return ClassifyResult(
            state=last_state,
            state_label=label,
            model_version=cm.version,
        )

    # ── Sequence (Viterbi) ───────────────────────────────────────────────────

    def get_state_sequence(
        self,
        feature_matrix: np.ndarray,   # shape (N, 6)
        instrument: str,
        timeframe: str,
        seq_length: int = 5,
    ) -> SequenceResult:
        """
        Decode the most probable state sequence via Viterbi.
        Returns the last `seq_length` states.

        Per guide_line.md: Viterbi = more interpretable than forward algorithm.
        """
        cm = self._get_or_raise(instrument, timeframe)
        X = cm.scaler.transform(feature_matrix)

        # Viterbi decoding
        log_prob, state_array = cm.model.decode(X, algorithm="viterbi")
        full_seq = state_array.tolist()

        # Take last seq_length states
        seq = full_seq[-seq_length:]
        seq_repr = "".join(f"S{s}" for s in seq)
        seq_hash = _compute_hash(seq_repr)

        return SequenceResult(
            sequence=seq,
            repr=seq_repr,
            seq_hash=seq_hash,
            log_prob=float(log_prob),
            model_version=cm.version,
        )

    # ── Pattern Match Score ──────────────────────────────────────────────────

    def compute_pattern_match_score(
        self,
        live_sequence: list[int],
        template_sequence: list[int],
        instrument: str,
        timeframe: str,
        match_threshold: float = 0.6,
    ) -> PatternMatchResult:
        """
        Score how well a live state sequence matches a template pattern.

        Method: Markov transition probability product.
        For each consecutive pair (s_i → s_{i+1}) in both sequences,
        compute the ratio of actual transition probabilities.

        Intuition:
          - If the live sequence follows the SAME transitions as the template,
            score → 1.0
          - If transitions are different, score → 0.0
          - NEVER uses cosine similarity on raw prices (forbidden per guide_line.md)

        Args:
            live_sequence:     Current decoded state sequence.
            template_sequence: Pattern template to match against (from patterns table).
            match_threshold:   Minimum score to consider a match.

        Returns:
            PatternMatchResult with match_score [0.0-1.0].
        """
        cm = self._get_or_raise(instrument, timeframe)
        transmat = cm.model.transmat_  # shape (K, K)

        # Align sequences — compare only overlapping tail
        n = min(len(live_sequence), len(template_sequence))
        if n < 2:
            return PatternMatchResult(match_score=0.0, log_prob_ratio=0.0, is_match=False)

        live     = live_sequence[-n:]
        template = template_sequence[-n:]

        # Compute log-probability of live path through transmat
        log_prob_live     = _sequence_log_prob(live,     transmat)
        log_prob_template = _sequence_log_prob(template, transmat)

        if log_prob_template < -1e9 or np.isnan(log_prob_template):
            # Template itself is not reachable — degenerate case
            return PatternMatchResult(match_score=0.5, log_prob_ratio=0.0, is_match=False)

        log_prob_ratio = log_prob_live - log_prob_template

        # Convert to similarity score:
        # When ratio = 0 (same path), score = 1.0
        # When ratio << 0, score → 0
        match_score = float(np.exp(np.clip(log_prob_ratio / n, -10.0, 0.0)))

        # Bonus: exact state matches increase score
        exact_matches = sum(1 for a, b in zip(live, template) if a == b)
        exact_ratio   = exact_matches / n
        # Blend Markov-based score with exact match ratio
        final_score   = float(0.7 * match_score + 0.3 * exact_ratio)

        return PatternMatchResult(
            match_score=round(final_score, 4),
            log_prob_ratio=round(log_prob_ratio, 4),
            is_match=final_score >= match_threshold,
        )

    # ── Internal ─────────────────────────────────────────────────────────────

    def _get_or_raise(self, instrument: str, timeframe: str) -> CachedModel:
        cm = self.get_cached(instrument, timeframe)
        if cm is None:
            raise ValueError(
                f"No HMM model loaded for {instrument}/{timeframe}. "
                f"Train and load a model first via /python/hmm/train."
            )
        return cm


# ─── Module-level singleton ───────────────────────────────────────────────────

_classifier = HmmClassifier()


def get_classifier() -> HmmClassifier:
    """Return the module-level singleton classifier (shared across FastAPI requests)."""
    return _classifier


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _compute_hash(seq_repr: str) -> str:
    """SHA256 first 16 chars of state sequence repr string."""
    return hashlib.sha256(seq_repr.encode("utf-8")).hexdigest()[:16]


def _sequence_log_prob(sequence: list[int], transmat: np.ndarray) -> float:
    """
    Compute log-probability of a state sequence given a transition matrix.
    P(seq) = Π transmat[s_i → s_{i+1}]
    """
    log_p = 0.0
    for i in range(len(sequence) - 1):
        s_from = sequence[i]
        s_to   = sequence[i + 1]
        if s_from >= transmat.shape[0] or s_to >= transmat.shape[1]:
            return -1e10
        prob = transmat[s_from, s_to]
        log_p += np.log(prob + 1e-10)  # ε prevents log(0)
    return float(log_p)
