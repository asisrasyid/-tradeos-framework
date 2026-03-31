"""
TradeOS — Initial HMM Training + Pattern Initialization
========================================================
Trains HMM for XAUUSDm M15 + H1 (last 6 months via MT5),
auto-creates standard patterns, creates a basic theory,
and runs initial backtest for scoring.

Requirements:
  - Python sidecar running on :8001
  - C# API running on :5206
  - MT5 terminal open + connected

Run:
  cd project/python-sidecar
  python scripts/init_training.py
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
PYTHON_API  = "http://localhost:8001"
CS_API      = "http://localhost:5206"
SYMBOL      = "XAUUSDm"
TFS         = ["M15", "H1"]
DATE_TO     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DATE_FROM   = (datetime.now(timezone.utc) - timedelta(days=183)).strftime("%Y-%m-%d")  # ~6 months
AUTH_USER   = "admin"
AUTH_PASS   = "123456"

# ── Colour helpers ─────────────────────────────────────────────────────────────
GRN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BLU = "\033[94m"; RST = "\033[0m"
def ok(msg):  print(f"{GRN}[OK]{RST} {msg}")
def err(msg): print(f"{RED}[ERR]{RST} {msg}")
def inf(msg): print(f"{BLU}[..]{RST} {msg}")
def warn(msg):print(f"{YEL}[!]{RST} {msg}")

# ── Helpers ────────────────────────────────────────────────────────────────────

_client = httpx.Client(timeout=300)

def cs_post(path: str, body: dict, token: str) -> dict:
    r = _client.post(f"{CS_API}{path}", json=body,
                     headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()

def cs_get(path: str, token: str) -> dict:
    r = _client.get(f"{CS_API}{path}",
                    headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()

def py_post(path: str, body: dict) -> dict:
    r = _client.post(f"{PYTHON_API}{path}", json=body)
    r.raise_for_status()
    return r.json()

def poll_job(job_id: str, token: str, label: str, interval: int = 5, max_wait: int = 300) -> bool:
    """Poll Hangfire job via backtest sessions or hmm models until job appears done."""
    inf(f"Waiting for job {job_id[:8]}… ({label})")
    waited = 0
    while waited < max_wait:
        time.sleep(interval)
        waited += interval
        print(f"  {waited}s elapsed…", end="\r")
    print()
    return True  # Hangfire jobs are fire-and-forget; we check results separately


# ── Step 1: Login ─────────────────────────────────────────────────────────────

def login() -> str:
    inf("Logging in to C# API…")
    r = _client.post(f"{CS_API}/api/auth/login",
                     json={"username": AUTH_USER, "password": AUTH_PASS})
    r.raise_for_status()
    token = r.json()["data"]["token"]
    ok(f"Authenticated as {AUTH_USER}")
    return token


# ── Step 2: HMM Training via Python sidecar directly ─────────────────────────

def train_hmm(tf: str) -> dict:
    """
    Call Python sidecar /python/hmm/train directly.
    Returns HmmTrainResponse with state_labels dict.
    """
    inf(f"Training HMM {SYMBOL} {tf}  ({DATE_FROM} → {DATE_TO})…")
    body = {
        "instrument": SYMBOL,
        "timeframe":  tf,
        "date_from":  DATE_FROM,
        "date_to":    DATE_TO,
    }
    result = py_post("/python/hmm/train", body)
    ok(f"HMM {tf}: K={result['n_states']}, BIC={result['bic_score']:.1f}, "
       f"n_samples={result['n_samples']}")
    print(f"  State labels:")
    for idx, label in result["state_labels"].items():
        print(f"    S{idx} = {label}")
    return result


# ── Step 3: Save HMM model to DB via C# API ──────────────────────────────────

def queue_hmm_save(tf: str, token: str) -> str:
    """
    Queue HMM training via C# (saves to DB).
    We call this AFTER Python has already trained and cached the model.
    The C# job will retrain (or use cache) and persist to DB.
    """
    inf(f"Queuing HMM model save to DB ({SYMBOL} {tf})…")
    body = {
        "instrument": SYMBOL,
        "timeframe":  tf,
        "dateFrom":   f"{DATE_FROM}T00:00:00Z",
        "dateTo":     f"{DATE_TO}T23:59:59Z",
    }
    result = cs_post("/api/hmm/train", body, token)
    job_id = result["data"]
    ok(f"HMM save queued: job {job_id[:8]}…")
    return job_id


# ── Step 4: Build pattern map from state labels ───────────────────────────────

# Standard label substrings to match
_LABEL_MAP = {
    "bull":      "trending_bull",
    "bear":      "trending_bear",
    "ranging":   "ranging",
    "post-bos":  "post_bos",
    "expansion": "post_bos",
    "retest":    "retest",
    "pullback":  "retest",
    "volatil":   "high_vol",
    "mixed":     None,  # skip
}

def classify_labels(state_labels: dict[str, str]) -> dict[str, int | None]:
    """
    Map each state label string to a semantic key.
    Returns e.g. {"trending_bull": 0, "post_bos": 3, "retest": 4, ...}
    """
    semantic: dict[str, int | None] = {}
    for idx_str, label in state_labels.items():
        idx = int(idx_str)
        label_lower = label.lower()
        matched = None
        for keyword, sem_key in _LABEL_MAP.items():
            if keyword in label_lower:
                matched = sem_key
                break
        if matched and matched not in semantic:
            semantic[matched] = idx
    return semantic


def build_pattern_defs(sem: dict, tf: str, model_version: str) -> list[dict]:
    """
    Build pattern definitions based on available semantic state indices.
    Each pattern = list of state indices + human label.
    Only creates patterns where ALL required states exist.
    """
    bull  = sem.get("trending_bull")
    bear  = sem.get("trending_bear")
    bos   = sem.get("post_bos")
    ret   = sem.get("retest")
    rng   = sem.get("ranging")

    patterns = []

    def make(code, name, desc, states: list):
        if any(s is None for s in states):
            return None
        seq_repr = "".join(f"S{s}" for s in states)
        return {
            "code":          f"{code}_{tf}",
            "name":          f"{name} — {SYMBOL} {tf}",
            "description":   desc,
            "pattern_type":  "state_sequence",
            "timeframe":     tf,
            "state_sequence": json.dumps(states),
            "state_seq_repr": seq_repr,
            "hmm_model_version": model_version,
        }

    # ── BUY patterns ──────────────────────────────────────────────────────────
    p = make(
        "BNR_BULL", "Break & Retest Bullish",
        "Trending Bull → Post-BOS Expansion → Retest/Pullback. Classic BUY setup.",
        [bull, bos, ret],
    )
    if p: patterns.append(p)

    p = make(
        "CONT_BULL", "Continuation Bullish",
        "Trending Bull → Retest/Pullback → Post-BOS Expansion. Trend continuation BUY.",
        [bull, ret, bos],
    )
    if p: patterns.append(p)

    p = make(
        "CHOCH_BULL", "CHoCH Bullish",
        "Trending Bear → Post-BOS Expansion → Trending Bull. Change of character — BUY.",
        [bear, bos, bull],
    )
    if p: patterns.append(p)

    p = make(
        "RANGE_BREAK_BULL", "Range Breakout Bullish",
        "Ranging Low Vol → Post-BOS Expansion → Retest. Range breakout BUY.",
        [rng, bos, ret],
    )
    if p: patterns.append(p)

    # ── SELL patterns ─────────────────────────────────────────────────────────
    p = make(
        "BNR_BEAR", "Break & Retest Bearish",
        "Trending Bear → Post-BOS Expansion → Retest/Pullback. Classic SELL setup.",
        [bear, bos, ret],
    )
    if p: patterns.append(p)

    p = make(
        "CONT_BEAR", "Continuation Bearish",
        "Trending Bear → Retest/Pullback → Post-BOS Expansion. Trend continuation SELL.",
        [bear, ret, bos],
    )
    if p: patterns.append(p)

    p = make(
        "CHOCH_BEAR", "CHoCH Bearish",
        "Trending Bull → Post-BOS Expansion → Trending Bear. Change of character — SELL.",
        [bull, bos, bear],
    )
    if p: patterns.append(p)

    p = make(
        "RANGE_BREAK_BEAR", "Range Breakout Bearish",
        "Ranging Low Vol → Post-BOS Expansion → Trending Bear. Range breakdown SELL.",
        [rng, bos, bear],
    )
    if p: patterns.append(p)

    return patterns


# ── Step 5: Create patterns in DB ─────────────────────────────────────────────

def create_patterns(pattern_defs: list[dict], token: str) -> list[dict]:
    created = []
    for p in pattern_defs:
        try:
            body = {
                "code":          p["code"],
                "name":          p["name"],
                "description":   p["description"],
                "patternType":   p["pattern_type"],
                "timeframe":     p["timeframe"],
                "stateSequence": p["state_sequence"],
                "stateSeqRepr":  p["state_seq_repr"],
            }
            result = cs_post("/api/patterns", body, token)
            pat = result["data"]
            ok(f"Pattern created: {p['code']}  ({p['state_seq_repr']})")
            created.append(pat)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                warn(f"Pattern {p['code']} already exists — skipping")
            else:
                err(f"Pattern {p['code']} failed: {e}")
    return created


# ── Step 6: Create basic theory ───────────────────────────────────────────────

def create_theory(token: str, buy_patterns: list[dict], sell_patterns: list[dict]) -> tuple[dict, dict]:
    """Create one BUY and one SELL theory for XAUUSDm."""
    theories = []
    for direction, pats in [("LONG", buy_patterns), ("SHORT", sell_patterns)]:
        label = "Bullish" if direction == "LONG" else "Bearish"
        body = {
            "name":           f"XAUUSDm {label} H1+M15 — Initial",
            "description":    f"Auto-generated initial {label} theory using HMM state sequences. Tune factors before live use.",
            "instrument":     SYMBOL,
            "direction":      direction,
            "threshold":      10,
            "minConfidence":  0.55,
            "isActive":       False,
        }
        try:
            result = cs_post("/api/theories", body, token)
            theory = result["data"]
            ok(f"Theory created: {theory['name']}  id={theory['id'][:8]}…")
            theories.append(theory)
        except Exception as e:
            err(f"Theory {direction} failed: {e}")
            theories.append(None)
    return tuple(theories)  # type: ignore


def add_factors(theory_id: str, direction: str, best_pattern: dict | None, token: str):
    """Add standard C-Code factors to a theory."""
    is_buy = direction == "LONG"

    factors = []

    # Pattern match factor (most important)
    if best_pattern:
        factors.append({
            "factorCode":    "HMM_STATE_SEQ_MATCH",
            "factorType":    "state_sequence_match",
            "decisionPoint": 5,
            "isRequired":    True,
            "timeframe":     "H1",
            "sortOrder":     1,
        })

    # HTF Bias
    factors.append({
        "factorCode":    "HTF_BIAS_BULLISH" if is_buy else "HTF_BIAS_BEARISH",
        "factorType":    "c_code_condition",
        "decisionPoint": 3,
        "isRequired":    False,
        "timeframe":     "H4",
        "sortOrder":     2,
    })

    # Retest state active
    factors.append({
        "factorCode":    "HMM_STATE_IS_RETEST",
        "factorType":    "c_code_condition",
        "decisionPoint": 2,
        "isRequired":    False,
        "timeframe":     "H1",
        "sortOrder":     3,
    })

    # Order block
    factors.append({
        "factorCode":    "PRICE_IN_OB_BULL" if is_buy else "PRICE_IN_OB_BEAR",
        "factorType":    "c_code_condition",
        "decisionPoint": 2,
        "isRequired":    False,
        "timeframe":     "M15",
        "sortOrder":     4,
    })

    # Momentum candle
    factors.append({
        "factorCode":    "CANDLE_MOMENTUM_BULL" if is_buy else "CANDLE_MOMENTUM_BEAR",
        "factorType":    "c_code_condition",
        "decisionPoint": 1,
        "isRequired":    False,
        "timeframe":     "M15",
        "sortOrder":     5,
    })

    # VETO: opposite trend (negative decisionPoint)
    factors.append({
        "factorCode":    "HMM_STATE_IS_BEAR_TREND" if is_buy else "HMM_STATE_IS_BULL_TREND",
        "factorType":    "c_code_condition",
        "decisionPoint": -5,
        "isRequired":    False,
        "timeframe":     "H1",
        "sortOrder":     6,
    })

    for f in factors:
        try:
            cs_post(f"/api/theories/{theory_id}/factors", f, token)
        except Exception as e:
            warn(f"  Factor {f['factorCode']} failed: {e}")

    ok(f"Added {len(factors)} factors to theory {theory_id[:8]}…")


# ── Step 7: Queue backtest ─────────────────────────────────────────────────────

def queue_backtest(theory_id: str, tf: str, token: str) -> str:
    inf(f"Queuing backtest for theory {theory_id[:8]}… ({SYMBOL} {tf} {DATE_FROM}→{DATE_TO})")
    body = {
        "theoryId":   theory_id,
        "instrument": SYMBOL,
        "timeframe":  tf,
        "dateFrom":   f"{DATE_FROM}T00:00:00Z",
        "dateTo":     f"{DATE_TO}T23:59:59Z",
    }
    result = cs_post("/api/backtest/run", body, token)
    job_id = result["data"]
    ok(f"Backtest queued: job {job_id[:8]}…")
    return job_id


# ── Step 8: Wait and print backtest results ────────────────────────────────────

def wait_and_print_results(theory_id: str, token: str, wait_sec: int = 60):
    inf(f"Waiting {wait_sec}s for backtest to complete…")
    for i in range(wait_sec, 0, -5):
        print(f"  {i}s remaining…", end="\r")
        time.sleep(5)
    print()

    try:
        sessions = cs_get(f"/api/backtest/sessions?theoryId={theory_id}", token)
        sess_list = sessions.get("data", [])
        if not sess_list:
            warn("No backtest sessions found yet — check Backtest page in UI")
            return

        # Get latest session
        latest = sorted(sess_list, key=lambda s: s.get("createdAt", ""), reverse=True)[0]
        sess_id = latest["id"]
        status  = latest.get("status", "unknown")
        inf(f"Latest session: {sess_id[:8]}…  status={status}")

        if status == "completed":
            res = cs_get(f"/api/backtest/sessions/{sess_id}/results", token)
            r = res.get("data", {})
            print()
            print(f"{'─'*50}")
            print(f"  BACKTEST RESULTS — {SYMBOL}")
            print(f"{'─'*50}")
            print(f"  Total signals : {r.get('total_signals', 'N/A')}")
            print(f"  Win Rate      : {r.get('win_rate', 0)*100:.1f}%")
            print(f"  Profit Factor : {r.get('profit_factor', 'N/A')}")
            print(f"  Sharpe Ratio  : {r.get('sharpe_ratio', 'N/A')}")
            print(f"  Max Drawdown  : {r.get('max_drawdown', 0)*100:.1f}%")
            print(f"  Total Pips    : {r.get('total_pips', 'N/A')}")
            print(f"{'─'*50}")
        else:
            warn(f"Backtest status: {status} — check UI or wait longer")

    except Exception as e:
        warn(f"Could not fetch results: {e}")
        warn("Check Backtest Runner page in UI for results")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print(f"{'═'*60}")
    print(f"  TradeOS — HMM Training & Pattern Init")
    print(f"  Symbol  : {SYMBOL}")
    print(f"  TFs     : {', '.join(TFS)}")
    print(f"  Range   : {DATE_FROM}  →  {DATE_TO}  (~6 months)")
    print(f"{'═'*60}")
    print()

    # ── Verify services ────────────────────────────────────────────────────────
    for url, label in [(f"{PYTHON_API}/health", "Python sidecar"), (f"{CS_API}/swagger/index.html", "C# API")]:
        try:
            r = _client.get(url, timeout=5)
            r.raise_for_status()
            ok(f"{label} reachable")
        except Exception:
            err(f"{label} not reachable at {url} — start it first!")
            sys.exit(1)

    print()

    # ── Login ──────────────────────────────────────────────────────────────────
    token = login()
    print()

    # ── Train HMM for each TF ─────────────────────────────────────────────────
    hmm_results: dict[str, dict] = {}
    for tf in TFS:
        print(f"{'─'*50}")
        try:
            result = train_hmm(tf)
            hmm_results[tf] = result
        except Exception as e:
            err(f"HMM training {tf} failed: {e}")
            continue
        print()

    if not hmm_results:
        err("All HMM training failed — check MT5 connection and sidecar logs")
        sys.exit(1)

    # ── Queue C# saves (persist to DB) ────────────────────────────────────────
    print(f"{'─'*50}")
    inf("Persisting models to DB via C# (background jobs)…")
    for tf in hmm_results:
        try:
            queue_hmm_save(tf, token)
        except Exception as e:
            warn(f"Model DB save queued failed for {tf}: {e} (model still in memory cache)")
    print()

    # ── Build + create patterns ───────────────────────────────────────────────
    # Use H1 state labels as primary (more reliable), M15 as secondary
    primary_tf   = "H1"   if "H1"  in hmm_results else TFS[0]
    secondary_tf = "M15"  if "M15" in hmm_results else None

    all_pattern_ids: dict[str, list[dict]] = {"H1": [], "M15": []}

    for tf, result in hmm_results.items():
        print(f"{'─'*50}")
        inf(f"Building patterns for {tf}…")
        sem = classify_labels(result["state_labels"])
        inf(f"Semantic map: {sem}")

        pattern_defs = build_pattern_defs(sem, tf, result["version"])
        if not pattern_defs:
            warn(f"No patterns could be built for {tf} — state labels may not match expected keywords")
            # Print raw labels for diagnostics
            for k, v in result["state_labels"].items():
                print(f"    S{k} = {v}")
            continue

        inf(f"Creating {len(pattern_defs)} patterns for {tf}…")
        created = create_patterns(pattern_defs, token)
        all_pattern_ids[tf] = created
        print()

    # ── Create theories ───────────────────────────────────────────────────────
    print(f"{'─'*50}")
    inf("Creating initial theories…")

    h1_patterns = all_pattern_ids.get("H1", [])
    m15_patterns = all_pattern_ids.get("M15", [])

    # Pick first BUY/SELL pattern for factor references
    buy_pats  = [p for p in h1_patterns if p and "BULL" in p.get("code", "") or "BNR" in p.get("code", "")]
    sell_pats = [p for p in h1_patterns if p and "BEAR" in p.get("code", "")]

    buy_theory, sell_theory = create_theory(token, buy_pats, sell_pats)
    print()

    # ── Add factors ───────────────────────────────────────────────────────────
    if buy_theory:
        inf(f"Adding factors to LONG theory…")
        best_buy = buy_pats[0] if buy_pats else None
        add_factors(buy_theory["id"], "LONG", best_buy, token)

    if sell_theory:
        inf(f"Adding factors to SHORT theory…")
        best_sell = sell_pats[0] if sell_pats else None
        add_factors(sell_theory["id"], "SHORT", best_sell, token)
    print()

    # ── Queue backtests ───────────────────────────────────────────────────────
    print(f"{'─'*50}")
    backtest_theory = buy_theory or sell_theory
    if backtest_theory:
        queue_backtest(backtest_theory["id"], primary_tf, token)
        wait_and_print_results(backtest_theory["id"], token, wait_sec=90)
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"{'═'*60}")
    print(f"  DONE")
    print(f"{'═'*60}")
    print(f"  Models trained : {', '.join(hmm_results.keys())}")
    print(f"  Patterns total : {sum(len(v) for v in all_pattern_ids.values())}")
    if buy_theory:
        print(f"  LONG theory    : {buy_theory['id'][:8]}… (inactive — activate after review)")
    if sell_theory:
        print(f"  SHORT theory   : {sell_theory['id'][:8]}… (inactive — activate after review)")
    print()
    print(f"  Next steps:")
    print(f"  1. Open http://localhost:3000/hmm     → verify state labels make sense")
    print(f"  2. Open http://localhost:3000/patterns → review created patterns")
    print(f"  3. Open http://localhost:3000/backtest → check backtest scores")
    print(f"  4. Open Theory Builder → tune factors → activate best theory")
    print(f"{'═'*60}")
    print()


if __name__ == "__main__":
    main()
