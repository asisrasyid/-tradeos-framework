# HMM + BAYESIAN MATH SPECIFICATION
## TradeOS v5.1 — Pattern Intelligence Engine

---

## Part 1: Feature Extraction

### Why these 6 features?

All 6 features are **scale-invariant** (do not depend on absolute price level)
and **noise-tolerant** (computed from statistical distributions, not raw values).

```python
import pandas as pd
import numpy as np
from scipy import stats
import pandas_ta as ta
from smartmoneyconcepts import smc

def extract_features(ohlc: pd.DataFrame, window: int = 100) -> np.ndarray:
    """
    Extract 6 scale-invariant features from OHLC data.
    Returns shape: (len(ohlc), 6)
    """
    features = pd.DataFrame(index=ohlc.index)

    # f0: ATR percentile — where is current volatility vs recent history?
    atr = ta.atr(ohlc.high, ohlc.low, ohlc.close, length=14)
    features['atr_pct'] = atr.rolling(window).apply(
        lambda x: stats.percentileofscore(x[:-1], x[-1]) / 100
    )

    # f1: Price momentum z-score — normalized return
    returns = ohlc.close.pct_change(5)  # 5-candle return
    features['momentum_z'] = (returns - returns.rolling(window).mean()) / \
                              (returns.rolling(window).std() + 1e-8)
    features['momentum_z'] = features['momentum_z'].clip(-3, 3)  # cap outliers

    # f2: Swing proximity ratio — distance to nearest swing / ATR
    swing_data = smc.swing_highs_lows(ohlc, swing_length=5)
    swing_highs = ohlc.high[swing_data['HighLow'] == 1]
    swing_lows  = ohlc.low[swing_data['HighLow'] == -1]
    # Distance to nearest swing level, normalized by ATR
    nearest_swing = pd.concat([
        abs(ohlc.close - swing_highs.reindex(ohlc.index, method='ffill')),
        abs(ohlc.close - swing_lows.reindex(ohlc.index, method='ffill'))
    ], axis=1).min(axis=1)
    features['swing_prox'] = (nearest_swing / (atr + 1e-8)).clip(0, 5) / 5

    # f3: Body dominance — candle body vs full range
    body = abs(ohlc.close - ohlc.open)
    full_range = (ohlc.high - ohlc.low).replace(0, 1e-8)
    features['body_dom'] = (body / full_range).clip(0, 1)

    # f4: HTF trend slope — linear regression slope on H4 (approximated)
    # Use 20-period linear regression slope, normalized by ATR
    close_arr = ohlc.close.values
    slopes = np.full(len(close_arr), np.nan)
    for i in range(20, len(close_arr)):
        y = close_arr[i-20:i]
        x = np.arange(20)
        slope = np.polyfit(x, y, 1)[0]
        slopes[i] = slope
    features['htf_slope'] = pd.Series(slopes, index=ohlc.index)
    features['htf_slope'] = (features['htf_slope'] / (atr + 1e-8)).clip(-3, 3) / 3

    # f5: Liquidity proximity — how close to EQH/EQL
    liq_data = smc.liquidity(ohlc, swing_data)
    liq_levels = liq_data['Level'].dropna()
    if len(liq_levels) > 0:
        nearest_liq = liq_levels.reindex(ohlc.index, method='ffill')
        liq_dist = abs(ohlc.close - nearest_liq) / (atr + 1e-8)
        features['liq_prox'] = (1 - liq_dist.clip(0, 3) / 3).clip(0, 1)
    else:
        features['liq_prox'] = 0.0

    return features.fillna(0).values  # shape: (N, 6)
```

---

## Part 2: HMM Training

### Model Selection via BIC

```python
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler
import numpy as np
import pickle

def train_hmm(features: np.ndarray, instrument: str, timeframe: str) -> dict:
    """
    Train Gaussian HMM with optimal K selected by BIC.
    Returns model, scaler, metadata.
    """
    # Standardize features (zero mean, unit variance)
    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    # BIC model selection
    best = {"k": None, "model": None, "bic": float('inf')}
    for k in range(4, 9):  # try K = 4, 5, 6, 7, 8
        try:
            model = GaussianHMM(
                n_components=k,
                covariance_type="full",
                n_iter=200,
                random_state=42,
                tol=1e-4
            )
            model.fit(X)
            log_likelihood = model.score(X)
            # BIC = -2 * log_likelihood + n_params * log(n_samples)
            n_params = k * k + k * 6 + k * 6 * 6  # transitions + means + covars
            bic = -2 * log_likelihood + n_params * np.log(len(X))
            if bic < best["bic"]:
                best = {"k": k, "model": model, "bic": bic}
        except Exception:
            continue

    # Serialize model and scaler
    model_pickle = pickle.dumps(best["model"])
    scaler_pickle = pickle.dumps(scaler)

    return {
        "model": best["model"],
        "scaler": scaler,
        "n_states": best["k"],
        "bic": best["bic"],
        "model_pickle": model_pickle,
        "scaler_pickle": scaler_pickle,
        "version": f"{instrument}_{timeframe}_v{int(time.time())}"
    }
```

### State Label Assignment (post-training)

```python
def label_states(model: GaussianHMM, scaler: StandardScaler) -> dict:
    """
    Assign human-readable labels to each state based on mean feature values.
    States are labeled by their characteristic feature patterns.
    """
    # Get mean feature values per state (in original scale)
    means = scaler.inverse_transform(model.means_)
    # means shape: (K, 6) — [atr_pct, momentum_z, swing_prox, body_dom, htf_slope, liq_prox]

    labels = {}
    for k in range(model.n_components):
        atr, mom, swing, body, slope, liq = means[k]

        if slope > 0.3 and mom > 0.3:
            labels[k] = f"S{k}_TRENDING_BULL"
        elif slope < -0.3 and mom < -0.3:
            labels[k] = f"S{k}_TRENDING_BEAR"
        elif atr > 0.7:
            labels[k] = f"S{k}_HIGH_VOLATILITY"
        elif atr < 0.25 and abs(mom) < 0.2:
            labels[k] = f"S{k}_RANGING"
        elif swing < 0.2 and body > 0.5:
            labels[k] = f"S{k}_RETEST_ZONE"
        else:
            labels[k] = f"S{k}_POST_BOS"

    return labels
```

---

## Part 3: State Sequence (Pattern)

### Viterbi Decoding

```python
def get_state_sequence(
    recent_features: np.ndarray,  # shape: (N, 6) — last N candles
    model: GaussianHMM,
    scaler: StandardScaler,
    seq_length: int = 5
) -> dict:
    """
    Decode state sequence from recent OHLC features.
    Uses Viterbi algorithm for most probable path.
    """
    X = scaler.transform(recent_features[-seq_length:])
    log_prob, state_seq = model.decode(X, algorithm="viterbi")

    seq_list = state_seq.tolist()
    seq_repr = "".join(f"S{s}" for s in seq_list)   # "S0S0S3S2S4"
    seq_hash = hashlib.sha256(seq_repr.encode()).hexdigest()[:16]

    return {
        "seq": seq_list,
        "repr": seq_repr,
        "hash": seq_hash,
        "log_prob": round(log_prob, 4),
        "length": seq_length
    }
```

### Pattern Match Score

```python
def compute_pattern_match_score(
    live_seq: list[int],
    template_seq: list[int],
    model: GaussianHMM
) -> float:
    """
    Compute how well live state sequence matches a template pattern.
    Uses transition probability product (Markov chain).
    
    score = Π P(s_t+1 | s_t) for all consecutive pairs
    Returns 0.0–1.0
    """
    if len(live_seq) != len(template_seq):
        return 0.0

    # Exact sequence match: high score
    if live_seq == template_seq:
        return 1.0

    # Partial match: product of transition probabilities
    trans_matrix = model.transmat_  # shape: (K, K)
    score = 1.0
    for i in range(len(live_seq) - 1):
        live_trans = trans_matrix[live_seq[i], live_seq[i+1]]
        tmpl_trans = trans_matrix[template_seq[i], template_seq[i+1]]
        # How close is live transition probability to template transition?
        ratio = min(live_trans, tmpl_trans) / (max(live_trans, tmpl_trans) + 1e-8)
        score *= ratio

    # Normalize: 0.0 (no match) to 1.0 (perfect match)
    # But apply partial credit: even if sequence differs, common states score higher
    state_overlap = sum(1 for l, t in zip(live_seq, template_seq) if l == t)
    overlap_bonus = state_overlap / len(template_seq) * 0.4

    final_score = score * 0.6 + overlap_bonus
    return round(min(final_score, 1.0), 4)
```

---

## Part 4: Bayesian Probability

### Self-Learning Counter

```python
import hashlib
from dataclasses import dataclass

@dataclass
class BayesianCounter:
    theory_id: str
    state_seq_repr: str
    instrument: str
    timeframe: str
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    total: int = 0

    @property
    def state_seq_hash(self) -> str:
        return hashlib.sha256(self.state_seq_repr.encode()).hexdigest()[:16]

    def p_win(self, alpha: float = 1.0) -> float:
        """Laplace-smoothed P(WIN)"""
        return (self.wins + alpha) / (self.total + 2 * alpha)

    def confidence_tier(self) -> str:
        if self.total < 10:   return "insufficient"
        if self.total < 30:   return "developing"
        if self.total < 100:  return "reliable"
        return "strong"

    def update(self, outcome: str) -> None:
        self.total += 1
        if outcome == "WIN":         self.wins += 1
        elif outcome == "LOSS":      self.losses += 1
        elif outcome == "BREAK_EVEN": self.breakeven += 1

    def to_signal_annotation(self) -> dict:
        return {
            "p_win": round(self.p_win(), 4),
            "p_win_pct": round(self.p_win() * 100, 1),
            "wins": self.wins,
            "losses": self.losses,
            "total": self.total,
            "tier": self.confidence_tier()
        }
```

### Decision Gate

```python
def make_decision(
    composite_score: float,
    theory_threshold: float,
    bayes: BayesianCounter,
    min_confidence: float = 0.55,
    required_factors_met: bool = True
) -> dict:
    """
    Final decision combining composite score + Bayesian probability.
    """
    score_passed = composite_score >= theory_threshold
    p_win = bayes.p_win()
    prob_passed = p_win >= min_confidence
    factors_ok = required_factors_met

    if score_passed and prob_passed and factors_ok:
        decision = "SIGNAL"
    elif score_passed and not prob_passed:
        decision = "WATCH"   # setup ada tapi historis belum mendukung
    elif not score_passed and p_win > 0.65 and bayes.total >= 20:
        decision = "WATCH"   # historis bagus tapi setup tidak lengkap
    else:
        decision = "SKIP"

    return {
        "decision": decision,
        "composite_score": composite_score,
        "threshold": theory_threshold,
        "p_win": round(p_win, 4),
        "p_win_pct": round(p_win * 100, 1),
        "confidence_tier": bayes.confidence_tier(),
        "score_passed": score_passed,
        "prob_passed": prob_passed,
        "reason": _build_reason(score_passed, prob_passed, p_win, bayes.total)
    }

def _build_reason(score_ok, prob_ok, p_win, n) -> str:
    if score_ok and prob_ok:
        return f"All conditions met. P(WIN)={p_win:.1%} (n={n})"
    if score_ok and not prob_ok:
        return f"Setup valid but P(WIN)={p_win:.1%} below threshold (n={n})"
    if not score_ok:
        return f"Composite score below threshold"
    return "Insufficient conditions"
```

---

## Part 5: Complexity & Performance Notes

### HMM Training
- **Time**: ~30 seconds per instrument/TF pair on 1 year data
- **Memory**: ~50MB per model (6 states, full covariance)
- **Frequency**: Retrain monthly (scheduled Hangfire job)
- **Storage**: ~200KB serialized pickle per model in PostgreSQL BYTEA

### State Classification (Live)
- **Time**: < 1ms per candle
- **Cache**: State cached in Redis (TTL = candle duration)
- **Batch**: Process all active TFs in parallel in Python

### Bayesian Lookup
- **Time**: < 1ms (single indexed DB query)
- **No computation** — just lookup + Laplace formula
- **Self-updates** synchronously after every outcome recording

### Scale Invariance Proof
```
XAUUSD price moves from 2000 to 3000 over 1 year.
Same "Break & Retest" pattern occurs at both price levels.

Old approach (cosine similarity on OHLC):
  Pattern template at 2000 → matrix normalized to [2000-range]
  Live pattern at 3000    → matrix normalized to [3000-range]
  Similarity: LOW — different absolute values → pattern not found ✗

New approach (HMM state sequence):
  Pattern at 2000 → features (ATR%, momentum_z, swing_ratio, ...) → S0→S3→S4
  Pattern at 3000 → features (same structure, different absolute) → S0→S3→S4
  Sequence match: HIGH — same state sequence → pattern found ✓
```

This is why HMM state sequences are the correct representation for trading patterns.
