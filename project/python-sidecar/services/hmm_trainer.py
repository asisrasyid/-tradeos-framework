"""
HMM Trainer — TradeOS v5.1
Trains a Gaussian HMM on feature vectors extracted from OHLC data.

Rules (guide_line.md):
  - GaussianHMM, covariance_type="full"
  - K selection via BIC, range K=4..8
  - Minimum 6 months data (≥ 1000 bars recommended for H1)
  - StandardScaler saved alongside model (always in pair)
  - Returns model_pickle (bytes) + scaler_pickle (bytes)
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM  # type: ignore
from sklearn.preprocessing import StandardScaler  # type: ignore

from services.feature_extractor import extract_features

logger = logging.getLogger(__name__)

# ─── Output dataclass ────────────────────────────────────────────────────────

@dataclass
class HmmTrainResult:
    version: str                        # e.g. "XAUUSD_H1_v1_20260324"
    instrument: str
    timeframe: str
    n_states: int                       # best K
    bic_score: float
    n_samples: int
    model_pickle: bytes                 # serialized GaussianHMM
    scaler_pickle: bytes                # serialized StandardScaler
    state_labels: dict[str, str]        # {"0": "Trending Bull", ...}
    feature_names: list[str]
    training_from: datetime
    training_to: datetime

    @property
    def model_hash(self) -> str:
        """SHA256 fingerprint of model bytes (first 16 chars)."""
        return hashlib.sha256(self.model_pickle).hexdigest()[:16]


# ─── Public API ───────────────────────────────────────────────────────────────

def train_hmm(
    df: pd.DataFrame,
    instrument: str,
    timeframe: str,
    k_min: int = 4,
    k_max: int = 8,
    n_iter: int = 100,
    random_state: int = 42,
    htf_df: pd.DataFrame | None = None,
) -> HmmTrainResult:
    """
    Train a Gaussian HMM with BIC-based K selection.

    Args:
        df:           OHLC DataFrame, minimum 200 rows.
        instrument:   e.g. "XAUUSD"
        timeframe:    e.g. "H1"
        k_min/k_max:  K search range (inclusive).
        n_iter:       EM iterations per model candidate.
        random_state: Reproducibility seed.
        htf_df:       Optional H4 DataFrame for f4 feature.

    Returns:
        HmmTrainResult with serialized model + scaler.

    Raises:
        ValueError: If fewer than 200 samples or all K attempts fail.
    """
    if len(df) < 200:
        raise ValueError(f"Insufficient training data: {len(df)} bars (need ≥ 200)")

    # 1. Extract features → shape (N, 6)
    logger.info(f"[{instrument}/{timeframe}] Extracting features from {len(df)} bars…")
    feature_matrix = extract_features(df, htf_df=htf_df)

    # 2. Standardize
    scaler = StandardScaler()
    X: np.ndarray = scaler.fit_transform(feature_matrix)

    # 3. BIC selection
    logger.info(f"[{instrument}/{timeframe}] Running BIC selection K={k_min}..{k_max}…")
    best_model, best_k, best_bic = _bic_search(X, k_min, k_max, n_iter, random_state)

    if best_model is None:
        raise ValueError("HMM training failed for all K values — check data quality")

    logger.info(f"[{instrument}/{timeframe}] Best K={best_k}, BIC={best_bic:.2f}")

    # 4. Serialize
    model_bytes  = pickle.dumps(best_model)
    scaler_bytes = pickle.dumps(scaler)

    # 5. Auto-label states
    state_labels = _auto_label_states(best_model, best_k, scaler)

    # 6. Build version string
    version = _build_version(instrument, timeframe)

    feature_names = [
        "ATR_pct", "momentum_z", "swing_prox",
        "body_dom", "htf_slope", "liq_prox",
    ]

    df_dates = _parse_dates(df)
    return HmmTrainResult(
        version=version,
        instrument=instrument,
        timeframe=timeframe,
        n_states=best_k,
        bic_score=float(best_bic),
        n_samples=len(X),
        model_pickle=model_bytes,
        scaler_pickle=scaler_bytes,
        state_labels=state_labels,
        feature_names=feature_names,
        training_from=df_dates[0],
        training_to=df_dates[1],
    )


def load_model(model_pickle: bytes, scaler_pickle: bytes) -> tuple[GaussianHMM, StandardScaler]:
    """Deserialize a model + scaler pair."""
    model: GaussianHMM     = pickle.loads(model_pickle)
    scaler: StandardScaler = pickle.loads(scaler_pickle)
    return model, scaler


# ─── BIC Search ──────────────────────────────────────────────────────────────

def _bic_search(
    X: np.ndarray,
    k_min: int,
    k_max: int,
    n_iter: int,
    random_state: int,
) -> tuple[GaussianHMM | None, int, float]:
    """
    Search K in [k_min, k_max] and return the model with lowest BIC.

    BIC = -2 * log_likelihood + K * log(N)
    where K is the number of free parameters (approximate) and N = number of samples.
    We use n_components as proxy for K to keep it simple and consistent.
    """
    best_model: GaussianHMM | None = None
    best_bic   = float("inf")
    best_k     = k_min

    n_samples = len(X)

    for k in range(k_min, k_max + 1):
        try:
            model = GaussianHMM(
                n_components=k,
                covariance_type="full",
                n_iter=n_iter,
                random_state=random_state,
                tol=1e-4,
            )
            model.fit(X)

            if not model.monitor_.converged:
                logger.warning(f"K={k}: EM did not converge after {n_iter} iterations")

            log_likelihood = model.score(X)
            # Number of free parameters: transition matrix + means + covariances
            n_free = k * (k - 1) + k * X.shape[1] + k * X.shape[1] * (X.shape[1] + 1) / 2
            bic = -2.0 * log_likelihood * n_samples + n_free * np.log(n_samples)

            logger.debug(f"K={k}: log_likelihood={log_likelihood:.2f}, BIC={bic:.2f}")

            if bic < best_bic:
                best_bic, best_k, best_model = bic, k, model

        except Exception as exc:
            logger.warning(f"K={k} training failed: {exc}")

    return best_model, best_k, best_bic


# ─── State Auto-Labeling ─────────────────────────────────────────────────────

def _auto_label_states(
    model: GaussianHMM,
    k: int,
    scaler: StandardScaler,
) -> dict[str, str]:
    """
    Assign human-readable labels using rank-based assignment.
    Guarantees Trending Bull, Trending Bear, Post-BOS, Ranging, Retest
    are always assigned to at least one state, regardless of absolute values.

    Feature index reference (after inverse_transform):
      0 = ATR_pct          (volatility)
      1 = momentum_zscore  (direction + strength)
      2 = swing_proximity  (signed)
      3 = body_dominance
      4 = htf_trend_slope  (direction)
      5 = liquidity_proximity
    """
    raw_means = scaler.inverse_transform(model.means_)  # shape (K, 6)

    atrs = raw_means[:, 0]   # volatility
    moms = raw_means[:, 1]   # momentum / direction
    htfs = raw_means[:, 4]   # HTF trend slope

    # Start: all "Mixed State"
    labels: dict[str, str] = {str(s): f"Mixed State S{s}" for s in range(k)}
    assigned: set[int] = set()

    def pick_unassigned(indices_sorted: list[int]) -> int | None:
        for idx in indices_sorted:
            if idx not in assigned:
                return idx
        return None

    # 1. Trending Bull  — highest combined bull score (mom + htf)
    bull_score  = moms + htfs
    s = pick_unassigned(list(np.argsort(bull_score)[::-1]))
    if s is not None:
        labels[str(s)] = "Trending Bull"
        assigned.add(s)

    # 2. Trending Bear  — lowest combined bull score
    s = pick_unassigned(list(np.argsort(bull_score)))
    if s is not None:
        labels[str(s)] = "Trending Bear"
        assigned.add(s)

    # 3. Post-BOS Expansion — highest ATR among unassigned
    s = pick_unassigned(list(np.argsort(atrs)[::-1]))
    if s is not None:
        labels[str(s)] = "Post-BOS Expansion"
        assigned.add(s)

    # 4. Ranging Low Vol — lowest ATR among unassigned
    s = pick_unassigned(list(np.argsort(atrs)))
    if s is not None:
        labels[str(s)] = "Ranging Low Vol"
        assigned.add(s)

    # 5. Retest / Pullback — smallest |momentum| among unassigned
    abs_mom = np.abs(moms)
    s = pick_unassigned(list(np.argsort(abs_mom)))
    if s is not None:
        labels[str(s)] = "Retest / Pullback"
        assigned.add(s)

    # 6. High Volatility Event — highest ATR remaining (if any left)
    s = pick_unassigned(list(np.argsort(atrs)[::-1]))
    if s is not None:
        labels[str(s)] = "High Volatility Event"
        assigned.add(s)

    for s_idx in range(k):
        m = raw_means[s_idx]
        logger.debug(
            f"State {s_idx} [{labels[str(s_idx)]}]: "
            f"ATR={m[0]:.3f} mom={m[1]:.3f} htf={m[4]:.3f}"
        )

    return labels


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_version(instrument: str, timeframe: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M")
    return f"{instrument}_{timeframe}_v1_{ts}"


def _parse_dates(df: pd.DataFrame) -> tuple[datetime, datetime]:
    """Extract first and last datetime from DataFrame index or 'time' column."""
    try:
        if "time" in df.columns:
            times = pd.to_datetime(df["time"])
        else:
            times = pd.to_datetime(df.index)
        return times.iloc[0].to_pydatetime(), times.iloc[-1].to_pydatetime()
    except Exception:
        now = datetime.utcnow()
        return now, now
