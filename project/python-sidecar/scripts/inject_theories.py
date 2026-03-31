"""
inject_theories.py — TradeOS Theory Injector
=============================================
Injects all 12 strategy theories + patterns into DB WITHOUT running backtest.
Reads HMM state labels from trained model to resolve semantic → state index mapping.

Run:
    cd project/python-sidecar
    python scripts/inject_theories.py

Requirements: Python :8001, C# :5206, HMM model trained for XAUUSDm/H1 (and M15 if needed)
"""

import json
import sys
import httpx

# ── Config ────────────────────────────────────────────────────────────────────

PYTHON_API = "http://localhost:8001"
CS_API     = "http://localhost:5206"
SYMBOL     = "XAUUSDm"
AUTH_USER  = "admin"
AUTH_PASS  = "123456"

# ── Console colours ───────────────────────────────────────────────────────────
GRN="\033[92m"; RED="\033[91m"; YEL="\033[93m"; BLU="\033[94m"; RST="\033[0m"; BLD="\033[1m"
def ok(m):   print(f"{GRN}✓{RST} {m}")
def err(m):  print(f"{RED}✗{RST} {m}");
def inf(m):  print(f"{BLU}…{RST} {m}")
def warn(m): print(f"{YEL}!{RST} {m}")
def hdr(m):  print(f"\n{BLD}{m}{RST}")

_c = httpx.Client(timeout=30)

# ── Strategy definitions ──────────────────────────────────────────────────────

STRATEGIES = [
    # LONG
    dict(code="LONG_BNR_H1",          name="Break & Retest Bullish — H1",        direction="LONG",  timeframe="H1",  states=["trending_bull", "post_bos", "retest"],          tp=2.0, sl=1.0),
    dict(code="LONG_CHOCH_H1",        name="CHoCH Bullish — H1",                 direction="LONG",  timeframe="H1",  states=["trending_bear", "post_bos", "trending_bull"],    tp=2.0, sl=1.0),
    dict(code="LONG_RANGE_BREAK_M15", name="Range Breakout Bullish — M15",       direction="LONG",  timeframe="M15", states=["ranging", "post_bos", "retest"],                 tp=1.5, sl=1.0),
    dict(code="LONG_OB_DISCOUNT_H1",  name="OB Discount Zone BUY — H1",          direction="LONG",  timeframe="H1",  states=["trending_bull", "retest", "post_bos"],           tp=2.0, sl=1.0),
    # SHORT
    dict(code="SHORT_BNR_H1",         name="Break & Retest Bearish — H1",        direction="SHORT", timeframe="H1",  states=["trending_bear", "post_bos", "retest"],           tp=2.0, sl=1.0),
    dict(code="SHORT_CHOCH_H1",       name="CHoCH Bearish — H1",                 direction="SHORT", timeframe="H1",  states=["trending_bull", "post_bos", "trending_bear"],    tp=2.0, sl=1.0),
    dict(code="SHORT_RANGE_BREAK_M15",name="Range Breakdown Bearish — M15",      direction="SHORT", timeframe="M15", states=["ranging", "post_bos", "retest"],                 tp=1.5, sl=1.0),
    dict(code="SHORT_EQH_SWEEP_M15",  name="Equal Highs Sweep SELL — M15",       direction="SHORT", timeframe="M15", states=["post_bos", "retest", "trending_bear"],           tp=1.5, sl=1.0),
    dict(code="SHORT_FVG_FILL_H1",    name="FVG Fill Bearish — H1",              direction="SHORT", timeframe="H1",  states=["trending_bear", "retest", "post_bos"],           tp=2.0, sl=1.0),
    dict(code="SHORT_OB_REJECTION_M15",name="OB Rejection SELL — M15",           direction="SHORT", timeframe="M15", states=["trending_bear", "retest", "trending_bear"],      tp=1.5, sl=1.0),
    dict(code="SHORT_DISTRIBUTION_H1",name="Distribution Zone Breakdown — H1",   direction="SHORT", timeframe="H1",  states=["high_vol", "trending_bear", "post_bos"],         tp=2.0, sl=1.0),
    dict(code="SHORT_CONTINUATION_M15",name="Lower High Continuation SELL — M15",direction="SHORT", timeframe="M15", states=["trending_bear", "post_bos", "retest"],           tp=1.5, sl=1.0),
]

# Semantic keyword map (same as strategy_init.py)
SEMANTIC_KEYWORDS = {
    "trending_bull": ["trending bull", "bull trend", "uptrend"],
    "trending_bear": ["trending bear", "bear trend", "downtrend"],
    "ranging":       ["ranging", "range", "consolidat", "low vol"],
    "post_bos":      ["post-bos", "post bos", "expansion", "breakout"],
    "retest":        ["retest", "pullback", "correction"],
    "high_vol":      ["high volat", "volatil event", "spike"],
}

def build_semantic_map(state_labels: dict) -> dict[str, int]:
    """Map semantic key → HMM state index from model's state_labels."""
    sem = {}
    for idx_str, label in state_labels.items():
        ll = label.lower()
        for key, kws in SEMANTIC_KEYWORDS.items():
            if key not in sem and any(k in ll for k in kws):
                sem[key] = int(idx_str)
                break
    return sem

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def cs_get(path, token):
    r = _c.get(f"{CS_API}{path}", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()

def cs_post(path, body, token):
    r = _c.post(f"{CS_API}{path}", json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()

def py_get(path):
    r = _c.get(f"{PYTHON_API}{path}")
    r.raise_for_status()
    return r.json()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Auth
    hdr("Step 1 — Login")
    try:
        r = _c.post(f"{CS_API}/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASS})
        r.raise_for_status()
        token = r.json()["data"]["token"]
        ok(f"Logged in as {AUTH_USER}")
    except Exception as e:
        err(f"Login failed: {e}"); sys.exit(1)

    # 2. Get HMM models and build semantic maps per TF
    hdr("Step 2 — Load HMM State Labels")
    models_resp = cs_get("/api/hmm/models", token)
    models = models_resp.get("data", [])

    sem_maps: dict[str, dict[str, int]] = {}  # keyed by timeframe

    for tf in ("H1", "M15"):
        model = next(
            (m for m in models
             if m["instrument"].upper() == SYMBOL.upper()
             and m["timeframe"].upper() == tf
             and m.get("isActive", True)),
            None
        )
        if model is None:
            warn(f"No trained HMM model for {SYMBOL}/{tf} — strategies on {tf} will use fallback indices")
            # Fallback: generic sequential indices
            sem_maps[tf] = {"trending_bull": 0, "trending_bear": 1, "ranging": 2,
                            "post_bos": 3, "retest": 4, "high_vol": 5}
            continue

        # Fetch state labels
        states_resp = cs_get(f"/api/hmm/models/{model['id']}/states", token)
        raw_labels_str = states_resp.get("data", {}).get("stateLabels") or "{}"

        try:
            raw_labels = json.loads(raw_labels_str) if isinstance(raw_labels_str, str) else raw_labels_str
        except Exception:
            raw_labels = {}

        sem_map = build_semantic_map(raw_labels)
        sem_maps[tf] = sem_map

        ok(f"{SYMBOL}/{tf} → {model['nStates']} states: {sem_map}")

        if len(sem_map) < 3:
            warn(f"  Only {len(sem_map)} semantic keys mapped — strategies may have incomplete patterns")

    # 3. Inject each strategy
    hdr("Step 3 — Inject Theories + Patterns")
    results = []

    for s in STRATEGIES:
        tf    = s["timeframe"]
        sem   = sem_maps.get(tf, sem_maps.get("H1", {}))
        code  = s["code"]
        name  = s["name"]
        inf(f"{code} …")

        # Resolve state indices
        state_indices = []
        missing = []
        for sem_key in s["states"]:
            idx = sem.get(sem_key)
            if idx is not None:
                state_indices.append(idx)
            else:
                missing.append(sem_key)

        if missing:
            warn(f"  Missing semantic keys: {missing} — using index 0 as fallback")
            for _ in missing:
                state_indices.append(0)

        seq_repr = "".join(f"S{i}" for i in state_indices)

        # 3a. Create Pattern (upsert by code)
        try:
            pat_resp = cs_post("/api/patterns", {
                "code":          code,
                "name":          name,
                "description":   s.get("description", ""),
                "patternType":   "HMM_SEQUENCE",
                "timeframe":     tf,
                "stateSequence": json.dumps(state_indices),
                "stateSeqRepr":  seq_repr,
            }, token)
            pattern_id = pat_resp["data"]["id"]
        except Exception as e:
            err(f"  Pattern create failed: {e}")
            results.append(dict(code=code, status="FAILED", reason=str(e)))
            continue

        # 3b. Create Theory (upsert by checking existing)
        try:
            # Check if theory with same name already exists
            theories_resp = cs_get("/api/theories", token)
            existing = next(
                (t for t in theories_resp.get("data", []) if t["name"] == name),
                None
            )

            if existing:
                theory_id = existing["id"]
                warn(f"  Theory already exists ({theory_id[:8]}…) — skipping create")
            else:
                theory_resp = cs_post("/api/theories", {
                    "name":          name,
                    "description":   s.get("description", ""),
                    "instrument":    SYMBOL,
                    "direction":     s["direction"],
                    "threshold":     60,
                    "minConfidence": 60.0,
                }, token)
                theory_id = theory_resp["data"]["id"]

            # 3c. Add factor linking pattern → theory
            # Check if factor already exists to avoid duplicates
            detail_resp = cs_get(f"/api/theories/{theory_id}", token)
            existing_factors = detail_resp.get("data", {}).get("factors", [])
            has_pattern_factor = any(
                f.get("patternId") == pattern_id for f in existing_factors
            )

            if not has_pattern_factor:
                cs_post(f"/api/theories/{theory_id}/factors", {
                    "patternId":      pattern_id,
                    "factorCode":     "PATTERN_SIMILARITY",
                    "factorType":     "HMM_PATTERN",
                    "decisionPoint":  60,
                    "isRequired":     True,
                    "operator":       ">=",
                    "thresholdValue": 0.60,
                    "timeframe":      tf,
                    "sortOrder":      1,
                }, token)

            ok(f"  {code} → theory={theory_id[:8]}… pattern={pattern_id[:8]}… states={state_indices}")
            results.append(dict(code=code, status="OK", theory_id=theory_id, pattern_id=pattern_id, states=state_indices))

        except Exception as e:
            err(f"  Theory/factor failed: {e}")
            results.append(dict(code=code, status="FAILED", reason=str(e)))

    # 4. Summary
    hdr("═══ INJECTION SUMMARY ═══")
    ok_count   = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] == "FAILED")
    print(f"\n  Injected : {GRN}{ok_count}{RST}")
    print(f"  Failed   : {RED}{fail_count}{RST}")
    print()
    for r in results:
        status = f"{GRN}OK{RST}" if r["status"] == "OK" else f"{RED}FAILED{RST}"
        detail = f"states={r.get('states')} theory={r.get('theory_id','')[:8]}" if r["status"] == "OK" else r.get("reason","")
        print(f"  {r['code']:<32} [{status}]  {detail}")

    print()
    if ok_count > 0:
        ok("Done! Refresh the Live page — theories should appear in the dropdown.")
    else:
        err("All injections failed. Check that C# API and Python sidecar are running.")


if __name__ == "__main__":
    main()
