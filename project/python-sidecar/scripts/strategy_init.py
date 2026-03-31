"""
TradeOS — 12 Strategy Schema Init (8 SHORT + 4 LONG)
=====================================================
Flow per strategy:
  1. Map HMM state labels → semantic indices
  2. Build pattern (state sequence)
  3. Create theory + factors in DB
  4. Run backtest
  5. Evaluate: WR >= 50%, PF >= 1.2, signals >= 5
  6. If below threshold: tune (lower threshold by 2, max 3 rounds)
  7. Final report: VIABLE vs NEEDS_TUNING

Run:
  cd project/python-sidecar
  python scripts/strategy_init.py

Requirements: Python :8001, C# :5206, MT5 open
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from uuid import uuid4

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
PYTHON_API = "http://localhost:8001"
CS_API     = "http://localhost:5206"
SYMBOL     = "XAUUSDm"
DATE_TO    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DATE_FROM  = (datetime.now(timezone.utc) - timedelta(days=183)).strftime("%Y-%m-%d")
AUTH_USER  = "admin"
AUTH_PASS  = "123456"

# Viable thresholds for paper trading
MIN_WIN_RATE     = 0.50
MIN_PROFIT_FACTOR= 1.20
MIN_SIGNALS      = 5
MAX_DRAWDOWN     = 0.30
MAX_TUNE_ROUNDS  = 3

# ── Console colours ───────────────────────────────────────────────────────────
GRN="\033[92m"; RED="\033[91m"; YEL="\033[93m"; BLU="\033[94m"; CYN="\033[96m"; RST="\033[0m"; BLD="\033[1m"
def ok(m):   print(f"{GRN}✓{RST} {m}")
def err(m):  print(f"{RED}✗{RST} {m}")
def inf(m):  print(f"{BLU}…{RST} {m}")
def warn(m): print(f"{YEL}!{RST} {m}")
def hdr(m):  print(f"\n{BLD}{CYN}{m}{RST}")

# ── HTTP client ───────────────────────────────────────────────────────────────
_c = httpx.Client(timeout=900)  # 15 min — M15 backtest (11k+ bars) bisa 8-10 menit

def cs_post(path, body, token):
    r = _c.post(f"{CS_API}{path}", json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status(); return r.json()

def cs_put(path, body, token):
    r = _c.put(f"{CS_API}{path}", json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status(); return r.json()

def cs_get(path, token):
    r = _c.get(f"{CS_API}{path}", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status(); return r.json()

def py_post(path, body):
    r = _c.post(f"{PYTHON_API}{path}", json=body)
    r.raise_for_status(); return r.json()


# ── State label semantic classifier ──────────────────────────────────────────
SEMANTIC_KEYWORDS = {
    "trending_bull":  ["trending bull", "bull trend", "uptrend"],
    "trending_bear":  ["trending bear", "bear trend", "downtrend"],
    "ranging":        ["ranging", "range", "consolidat", "low vol"],
    "post_bos":       ["post-bos", "post bos", "expansion", "breakout"],
    "retest":         ["retest", "pullback", "correction"],
    "high_vol":       ["high volat", "volatil event", "spike"],
}

def build_semantic_map(state_labels: dict) -> dict[str, int]:
    """Returns e.g. {"trending_bull": 2, "post_bos": 0, "retest": 3, ...}"""
    sem = {}
    for idx_str, label in state_labels.items():
        ll = label.lower()
        for key, kws in SEMANTIC_KEYWORDS.items():
            if key not in sem and any(k in ll for k in kws):
                sem[key] = int(idx_str)
                break
    return sem


# ── Strategy definitions ──────────────────────────────────────────────────────
@dataclass
class StrategyDef:
    code:        str
    name:        str
    direction:   str   # LONG | SHORT
    timeframe:   str   # primary TF for backtest
    states:      list  # semantic keys: ["trending_bull", "post_bos", "retest"]
    description: str = ""
    tp_mult:     float = 2.0   # TP = entry ± ATR × tp_mult
    sl_mult:     float = 1.0   # SL = entry ∓ ATR × sl_mult


STRATEGIES: list[StrategyDef] = [

    # ══════════════════════════════════════════════════════
    # LONG STRATEGIES (4)
    # ══════════════════════════════════════════════════════

    StrategyDef(
        code="LONG_BNR_H1",
        name="Break & Retest Bullish — H1",
        direction="LONG", timeframe="H1",
        description="BOS bullish → retest → ekspansi naik",
        states=["trending_bull", "post_bos", "retest"],
    ),
    StrategyDef(
        code="LONG_CHOCH_H1",
        name="CHoCH Bullish — H1",
        direction="LONG", timeframe="H1",
        description="Downtrend → BOS bull → new uptrend",
        states=["trending_bear", "post_bos", "trending_bull"],
    ),
    StrategyDef(
        code="LONG_RANGE_BREAK_M15",
        name="Range Breakout Bullish — M15",
        direction="LONG", timeframe="M15",
        description="Konsolidasi → BOS bullish → retest",
        states=["ranging", "post_bos", "retest"],
    ),
    StrategyDef(
        code="LONG_OB_DISCOUNT_H1",
        name="OB Discount Zone BUY — H1",
        direction="LONG", timeframe="H1",
        description="Uptrend → pullback → ekspansi lanjutan",
        states=["trending_bull", "retest", "post_bos"],
    ),

    # ══════════════════════════════════════════════════════
    # SHORT STRATEGIES (8)
    # ══════════════════════════════════════════════════════

    StrategyDef(
        code="SHORT_BNR_H1",
        name="Break & Retest Bearish — H1",
        direction="SHORT", timeframe="H1",
        description="BOS bearish → retest → ekspansi turun",
        states=["trending_bear", "post_bos", "retest"],
    ),
    StrategyDef(
        code="SHORT_CHOCH_H1",
        name="CHoCH Bearish — H1",
        direction="SHORT", timeframe="H1",
        description="Uptrend → BOS bear → new downtrend",
        states=["trending_bull", "post_bos", "trending_bear"],
    ),
    StrategyDef(
        code="SHORT_RANGE_BREAK_M15",
        name="Range Breakdown Bearish — M15",
        direction="SHORT", timeframe="M15",
        description="Konsolidasi → BOS bearish → retest",
        states=["ranging", "post_bos", "retest"],
    ),
    StrategyDef(
        code="SHORT_EQH_SWEEP_M15",
        name="Equal Highs Sweep SELL — M15",
        direction="SHORT", timeframe="M15",
        description="Likuiditas EQH tersapu → reversal turun",
        states=["post_bos", "retest", "trending_bear"],
    ),
    StrategyDef(
        code="SHORT_FVG_FILL_H1",
        name="FVG Fill Bearish — H1",
        direction="SHORT", timeframe="H1",
        description="Retest FVG bearish → lanjut turun",
        states=["trending_bear", "retest", "post_bos"],
    ),
    StrategyDef(
        code="SHORT_OB_REJECTION_M15",
        name="OB Rejection SELL — M15",
        direction="SHORT", timeframe="M15",
        description="Supply OB rejection → ekspansi turun",
        states=["trending_bear", "retest", "trending_bear"],
    ),
    StrategyDef(
        code="SHORT_DISTRIBUTION_H1",
        name="Distribution Zone Breakdown — H1",
        direction="SHORT", timeframe="H1",
        description="High vol event → distribusi → BOS bearish",
        states=["high_vol", "trending_bear", "post_bos"],
    ),
    StrategyDef(
        code="SHORT_CONTINUATION_M15",
        name="Lower High Continuation SELL — M15",
        direction="SHORT", timeframe="M15",
        description="Downtrend → konsolidasi → BOS bearish lanjutan",
        states=["trending_bear", "ranging", "post_bos"],
    ),
]


# ── Auth ──────────────────────────────────────────────────────────────────────
def login() -> str:
    r = _c.post(f"{CS_API}/api/auth/login",
                json={"username": AUTH_USER, "password": AUTH_PASS})
    r.raise_for_status()
    return r.json()["data"]["token"]


# ── HMM Training ──────────────────────────────────────────────────────────────
def train_hmm(tf: str) -> dict:
    inf(f"Training HMM {SYMBOL} {tf}  ({DATE_FROM} → {DATE_TO})…")
    result = py_post("/python/hmm/train", {
        "instrument": SYMBOL, "timeframe": tf,
        "date_from": DATE_FROM, "date_to": DATE_TO,
    })
    ok(f"HMM {tf}: K={result['n_states']}, BIC={result['bic_score']:.1f}, "
       f"samples={result['n_samples']}")
    for idx, label in result["state_labels"].items():
        print(f"    S{idx} = {label}")
    return result


def queue_hmm_db(tf: str, token: str):
    """Queue model persist to DB via C# Hangfire job."""
    cs_post("/api/hmm/train", {
        "instrument": SYMBOL, "timeframe": tf,
        "dateFrom": f"{DATE_FROM}T00:00:00Z",
        "dateTo":   f"{DATE_TO}T23:59:59Z",
    }, token)


# ── Pattern creation ──────────────────────────────────────────────────────────
def create_pattern(strat: StrategyDef, sem: dict, model_version: str, token: str) -> dict | None:
    indices = [sem.get(s) for s in strat.states]
    if any(i is None for i in indices):
        missing = [s for s in strat.states if sem.get(s) is None]
        warn(f"  {strat.code}: states not found in model → {missing}. Skipping pattern.")
        return None

    seq_repr = "".join(f"S{i}" for i in indices)
    body = {
        "code":          strat.code,
        "name":          strat.name,
        "description":   strat.description,
        "patternType":   "state_sequence",
        "timeframe":     strat.timeframe,
        "stateSequence": json.dumps(indices),
        "stateSeqRepr":  seq_repr,
    }
    try:
        result = cs_post("/api/patterns", body, token)
        pat = result["data"]
        ok(f"  Pattern {strat.code}: {seq_repr}  id={pat['id'][:8]}…")
        return pat
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (409, 400):
            warn(f"  Pattern {strat.code} already exists — skipping")
        else:
            err(f"  Pattern {strat.code}: {e}")
        return None


# ── Theory creation ───────────────────────────────────────────────────────────
def create_theory(strat: StrategyDef, threshold: int, token: str) -> dict | None:
    body = {
        "name":          f"{strat.name} [{DATE_FROM[:7]}]",
        "description":   strat.description,
        "instrument":    SYMBOL,
        "direction":     strat.direction,
        "threshold":     threshold,
        "minConfidence": 0.50,
    }
    try:
        result = cs_post("/api/theories", body, token)
        return result["data"]
    except Exception as e:
        err(f"  Theory create failed: {e}")
        return None


def add_factors(theory_id: str, factors: list[dict], pattern_id: str | None,
                sort_start: int, token: str):
    for i, f in enumerate(factors):
        body = dict(f)
        body["sortOrder"] = sort_start + i
        if "SEQ" in f["factorCode"] and pattern_id:
            body["patternId"] = pattern_id
        try:
            cs_post(f"/api/theories/{theory_id}/factors", body, token)
        except Exception as e:
            warn(f"    Factor {f['factorCode']}: {e}")


# ── Backtest execution (direct Python — bypasses Hangfire) ─────────────────────
def run_backtest_direct(theory_id: str, strat: "StrategyDef",
                        pattern_states: list[int],
                        similarity_threshold: float = 0.60) -> dict | None:
    """
    Call Python /python/backtest/run directly — synchronous, no polling.
    Uses pure pattern similarity (Opsi A) — no C-code factor evaluation.

    pattern_states: actual HMM state indices resolved from semantic map,
                    e.g. [3, 0, 5] for [trending_bull, post_bos, retest]
    similarity_threshold: minimum similarity to trigger signal (default 0.60)
    """
    theory_snapshot = json.dumps({
        "theory_id":           theory_id,
        "theory_name":         strat.name,
        "instrument":          SYMBOL,
        "direction":           strat.direction,
        "pattern_states":      pattern_states,
        "similarity_threshold": similarity_threshold,
    })

    try:
        result = py_post("/python/backtest/run", {
            "session_id":      str(uuid4()),
            "theory_snapshot": theory_snapshot,
            "instrument":      SYMBOL,
            "timeframe":       strat.timeframe,
            "date_from":       DATE_FROM,
            "date_to":         DATE_TO,
            "params":          {},
        })
        return result
    except Exception as e:
        err(f"  Direct backtest failed: {e}")
        return None


# ── Score evaluation ──────────────────────────────────────────────────────────
@dataclass
class StrategyResult:
    code:          str
    name:          str
    direction:     str
    theory_id:     str
    pattern_repr:  str
    timeframe:     str
    threshold:     int
    tune_rounds:   int     = 0
    total_signals: int     = 0
    win_rate:      float   = 0.0
    profit_factor: float   = 0.0
    sharpe:        float   = 0.0
    max_drawdown:  float   = 0.0
    total_pips:    float   = 0.0
    viable:        bool    = False
    skip_reason:   str     = ""


def is_viable(r: StrategyResult) -> bool:
    return (r.total_signals >= MIN_SIGNALS and
            r.win_rate      >= MIN_WIN_RATE and
            r.profit_factor >= MIN_PROFIT_FACTOR and
            r.max_drawdown  <= MAX_DRAWDOWN)


def update_theory_threshold(theory_id: str, new_threshold: int,
                             strat: StrategyDef, token: str):
    """Lower threshold via PUT /api/theories/{id}."""
    body = {
        "name":          f"{strat.name} [{DATE_FROM[:7]}]",
        "description":   strat.description,
        "instrument":    SYMBOL,
        "direction":     strat.direction,
        "threshold":     new_threshold,
        "minConfidence": 0.50,
    }
    try:
        cs_put(f"/api/theories/{theory_id}", body, token)
    except Exception as e:
        warn(f"    Threshold update failed: {e}")


# ── Per-strategy loop ─────────────────────────────────────────────────────────
def run_strategy(strat: StrategyDef, sem_m15: dict, sem_h1: dict,
                 ver_m15: str, ver_h1: str, token: str) -> StrategyResult:

    hdr(f"[{strat.direction}] {strat.code}")
    print(f"  {strat.description}")

    sem = sem_m15 if strat.timeframe == "M15" else sem_h1
    ver = ver_m15 if strat.timeframe == "M15" else ver_h1

    # 1. Pattern — resolve semantic keys → actual HMM state indices
    indices = [sem.get(s) for s in strat.states]
    if any(i is None for i in indices):
        missing = [s for s in strat.states if sem.get(s) is None]
        warn(f"  {strat.code}: states not found in model → {missing}. Skipping.")
        return StrategyResult(strat.code, strat.name, strat.direction,
                              "", "NO_PATTERN", strat.timeframe, 60,
                              skip_reason=f"States not in HMM: {missing}")

    pattern_states = [int(i) for i in indices]
    pat = create_pattern(strat, sem, ver, token)
    pat_id   = pat["id"]   if pat else None
    pat_repr = pat.get("stateSeqRepr", "S" + "S".join(str(i) for i in pattern_states)) if pat \
               else "S" + "S".join(str(i) for i in pattern_states)

    # 2. Theory (metadata in DB — no factors needed for backtest)
    theory = create_theory(strat, 60, token)
    if not theory:
        return StrategyResult(strat.code, strat.name, strat.direction,
                              "", pat_repr, strat.timeframe, 60,
                              skip_reason="Theory creation failed")

    theory_id = theory["id"]
    ok(f"  Theory {theory_id[:8]}… | pattern={pat_repr} | states={pattern_states}")

    # 3. Backtest — pure pattern similarity, no tuning rounds needed
    # Tune similarity threshold: start at 0.60, relax to 0.50 if too few signals
    sim_threshold = 0.60
    tune_rounds   = 0
    result_data   = None

    for round_n in range(MAX_TUNE_ROUNDS + 1):
        inf(f"  Backtest round {round_n+1}  (similarity≥{sim_threshold:.0%})…")
        try:
            result_data = run_backtest_direct(theory_id, strat, pattern_states, sim_threshold)
        except Exception as e:
            err(f"  Backtest error: {e}")
            break

        if not result_data:
            warn("  No result data — skipping tune")
            break

        # backtest_runner returns win_rate/max_drawdown as 0-100 scale → normalize to 0-1
        wr  = float(result_data.get("win_rate")      or 0) / 100.0
        pf  = float(result_data.get("profit_factor") or 0)
        sig = int(result_data.get("total_signals")   or 0)
        dd  = float(result_data.get("max_drawdown")  or 0) / 100.0

        print(f"    signals={sig}  WR={wr*100:.1f}%  PF={pf:.2f}  DD={dd*100:.1f}%")

        tune_rounds = round_n

        # Check if viable
        if sig >= MIN_SIGNALS and wr >= MIN_WIN_RATE and pf >= MIN_PROFIT_FACTOR:
            break  # good enough

        # Not viable yet — relax similarity threshold if too few signals
        if round_n < MAX_TUNE_ROUNDS:
            if sig < MIN_SIGNALS and sim_threshold > 0.40:
                sim_threshold = round(sim_threshold - 0.10, 2)
                warn(f"  Insufficient signals ({sig}) → relax similarity to {sim_threshold:.0%}")
            else:
                break  # WR/PF issue — similarity relaxation won't help

    # 4. Build result
    res = StrategyResult(
        code=strat.code, name=strat.name, direction=strat.direction,
        theory_id=theory_id, pattern_repr=pat_repr,
        timeframe=strat.timeframe, threshold=int(sim_threshold * 100),
        tune_rounds=tune_rounds,
    )

    if result_data:
        res.total_signals = int(result_data.get("total_signals") or 0)
        res.win_rate      = float(result_data.get("win_rate")      or 0) / 100.0
        res.profit_factor = float(result_data.get("profit_factor") or 0)
        res.sharpe        = float(result_data.get("sharpe_ratio")  or 0)
        res.max_drawdown  = float(result_data.get("max_drawdown")  or 0) / 100.0
        res.total_pips    = float(result_data.get("total_pips")    or 0)
        res.viable        = is_viable(res)

        if not res.viable:
            if res.total_signals < MIN_SIGNALS:
                res.skip_reason = f"only {res.total_signals} signals (min {MIN_SIGNALS})"
            elif res.win_rate < MIN_WIN_RATE:
                res.skip_reason = f"WR {res.win_rate*100:.1f}% < {MIN_WIN_RATE*100:.0f}%"
            elif res.profit_factor < MIN_PROFIT_FACTOR:
                res.skip_reason = f"PF {res.profit_factor:.2f} < {MIN_PROFIT_FACTOR}"
            else:
                res.skip_reason = f"DD {res.max_drawdown*100:.1f}% > {MAX_DRAWDOWN*100:.0f}%"
    else:
        res.skip_reason = "No backtest result"

    if res.viable:
        ok(f"  VIABLE ✓  WR={res.win_rate*100:.1f}%  PF={res.profit_factor:.2f}  "
           f"signals={res.total_signals}  pips={res.total_pips:.0f}")
    else:
        warn(f"  NEEDS TUNING — {res.skip_reason}")

    return res


# ── Final report ──────────────────────────────────────────────────────────────
def print_report(results: list[StrategyResult]):
    viable  = [r for r in results if r.viable]
    weak    = [r for r in results if not r.viable and r.total_signals > 0]
    failed  = [r for r in results if r.total_signals == 0 and not r.viable]

    print(f"\n{'═'*70}")
    print(f"{BLD}  FINAL REPORT — {SYMBOL}  {DATE_FROM} → {DATE_TO}{RST}")
    print(f"{'═'*70}")

    print(f"\n{GRN}{BLD}  VIABLE FOR PAPER TRADING ({len(viable)}/{len(results)}){RST}")
    print(f"  {'Code':<30} {'Dir':<6} {'TF':<5} {'WR':>6} {'PF':>5} {'Sig':>5} {'Pips':>7}")
    print(f"  {'─'*62}")
    for r in sorted(viable, key=lambda x: x.win_rate, reverse=True):
        wr  = f"{r.win_rate*100:.1f}%"
        pf  = f"{r.profit_factor:.2f}"
        pip = f"{r.total_pips:.0f}"
        print(f"  {GRN}{r.code:<30}{RST} {r.direction:<6} {r.timeframe:<5} "
              f"{wr:>6} {pf:>5} {r.total_signals:>5} {pip:>7}")

    if weak:
        print(f"\n{YEL}{BLD}  NEEDS TUNING ({len(weak)}){RST}")
        print(f"  {'Code':<30} {'Reason'}")
        print(f"  {'─'*60}")
        for r in weak:
            print(f"  {YEL}{r.code:<30}{RST} {r.skip_reason}")

    if failed:
        print(f"\n{RED}{BLD}  FAILED / NO DATA ({len(failed)}){RST}")
        for r in failed:
            print(f"  {RED}{r.code}{RST}  — {r.skip_reason or 'unknown'}")

    print(f"\n{'─'*70}")
    print(f"  Theory IDs untuk paper trading:")
    for r in viable:
        print(f"  {r.theory_id}  ← {r.code}")
    print(f"{'═'*70}\n")

    if viable:
        print(f"{GRN}  → Activate teori ini di UI: localhost:3000/theories{RST}")
        print(f"{GRN}  → Pantau signal di: localhost:3000{RST}")
    else:
        print(f"{YEL}  → Tidak ada strategi yang viable dengan data 6 bulan.")
        print(f"  → Coba tambah range data atau adjust MIN_WIN_RATE di config.{RST}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'═'*70}")
    print(f"{BLD}  TradeOS — 12 Strategy Init  (8 SHORT + 4 LONG){RST}")
    print(f"  Symbol : {SYMBOL}   Range : {DATE_FROM} → {DATE_TO}")
    print(f"  Viable criteria : WR≥{MIN_WIN_RATE*100:.0f}%  PF≥{MIN_PROFIT_FACTOR}  "
          f"Signals≥{MIN_SIGNALS}  DD≤{MAX_DRAWDOWN*100:.0f}%")
    print(f"{'═'*70}\n")

    # Service check (warning only — don't block if already confirmed running)
    for url, lbl in [
        (f"{PYTHON_API}/openapi.json",   "Python sidecar :8001"),
        (f"{CS_API}/swagger/index.html", "C# API :5206"),
    ]:
        try:
            r = _c.get(url, timeout=10)
            if r.status_code < 500:
                ok(lbl)
            else:
                warn(f"{lbl} returned {r.status_code} — continuing anyway")
        except Exception as e:
            warn(f"{lbl} check failed ({e}) — continuing anyway")

    print()
    token = login()
    ok("Authenticated")
    print()

    # ── Pre-cache OHLC (fetch once → store DB → all backtests read local) ─────
    hdr("STEP 1 — OHLC Cache")
    for tf in ["M15", "H1"]:
        inf(f"Caching {SYMBOL} {tf} ({DATE_FROM} → {DATE_TO})…")
        try:
            r = py_post("/python/ohlc/cache", {
                "instrument": SYMBOL, "timeframe": tf,
                "date_from": DATE_FROM, "date_to": DATE_TO,
            })
            ok(f"  {tf}: {r['bars_saved']} bars saved → {r['total_cached']} total in cache")
        except Exception as e:
            warn(f"  {tf} cache failed ({e}) — will fetch from MT5 per backtest")

    # ── Train HMM ─────────────────────────────────────────────────────────────
    hdr("STEP 2 — HMM Training")
    hmm_m15 = hmm_h1 = None

    for tf in ["M15", "H1"]:
        try:
            result = train_hmm(tf)
            if tf == "M15": hmm_m15 = result
            else:           hmm_h1  = result
            try: queue_hmm_db(tf, token)
            except Exception as e: warn(f"DB save queue failed ({tf}): {e}")
        except Exception as e:
            err(f"HMM training {tf} failed: {e}")

    if not hmm_m15 and not hmm_h1:
        err("Both HMM trainings failed. Check MT5 connection.")
        sys.exit(1)

    # Use fallback if one TF fails
    if not hmm_m15: hmm_m15 = hmm_h1
    if not hmm_h1:  hmm_h1  = hmm_m15

    sem_m15 = build_semantic_map(hmm_m15["state_labels"])
    sem_h1  = build_semantic_map(hmm_h1["state_labels"])
    ver_m15 = hmm_m15["version"]
    ver_h1  = hmm_h1["version"]

    print(f"\n  Semantic map M15: {sem_m15}")
    print(f"  Semantic map H1 : {sem_h1}")

    # ── Run strategies ────────────────────────────────────────────────────────
    hdr("STEP 3 — Strategy Init + Backtest Loop")
    print(f"  Running {len(STRATEGIES)} strategies…\n")

    results: list[StrategyResult] = []

    for i, strat in enumerate(STRATEGIES):
        print(f"\n[{i+1}/{len(STRATEGIES)}]", end=" ")
        try:
            res = run_strategy(strat, sem_m15, sem_h1, ver_m15, ver_h1, token)
            results.append(res)
        except Exception as e:
            err(f"{strat.code} crashed: {e}")
            results.append(StrategyResult(
                strat.code, strat.name, strat.direction,
                "", "N/A", strat.timeframe, 60,
                skip_reason=str(e),
            ))

    # ── Report ────────────────────────────────────────────────────────────────
    hdr("STEP 4 — Results")
    print_report(results)


if __name__ == "__main__":
    main()
