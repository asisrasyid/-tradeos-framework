"""
_fix_factors.py — link pattern -> theory via theory_factor rows
Run: python scripts/_fix_factors.py
"""
import json, sys, httpx

CS_API    = "http://localhost:5206"
SYMBOL    = "XAUUSDm"
AUTH_USER = "admin"
AUTH_PASS = "123456"

SEMANTIC_KEYWORDS = {
    "trending_bull": ["trending bull", "bull trend", "uptrend"],
    "trending_bear": ["trending bear", "bear trend", "downtrend"],
    "ranging":       ["ranging", "range", "consolidat", "low vol"],
    "post_bos":      ["post-bos", "post bos", "expansion", "breakout"],
    "retest":        ["retest", "pullback", "correction"],
    "high_vol":      ["high volat", "volatil event", "spike"],
}

STRATEGIES = [
    dict(code="LONG_BNR_H1",            name="Break & Retest Bullish -- H1",         direction="LONG",  timeframe="H1",  states=["trending_bull","post_bos","retest"]),
    dict(code="LONG_CHOCH_H1",          name="CHoCH Bullish -- H1",                  direction="LONG",  timeframe="H1",  states=["trending_bear","post_bos","trending_bull"]),
    dict(code="LONG_RANGE_BREAK_M15",   name="Range Breakout Bullish -- M15",        direction="LONG",  timeframe="M15", states=["ranging","post_bos","retest"]),
    dict(code="LONG_OB_DISCOUNT_H1",    name="OB Discount Zone BUY -- H1",           direction="LONG",  timeframe="H1",  states=["trending_bull","retest","post_bos"]),
    dict(code="SHORT_BNR_H1",           name="Break & Retest Bearish -- H1",         direction="SHORT", timeframe="H1",  states=["trending_bear","post_bos","retest"]),
    dict(code="SHORT_CHOCH_H1",         name="CHoCH Bearish -- H1",                  direction="SHORT", timeframe="H1",  states=["trending_bull","post_bos","trending_bear"]),
    dict(code="SHORT_RANGE_BREAK_M15",  name="Range Breakdown Bearish -- M15",       direction="SHORT", timeframe="M15", states=["ranging","post_bos","retest"]),
    dict(code="SHORT_EQH_SWEEP_M15",    name="Equal Highs Sweep SELL -- M15",        direction="SHORT", timeframe="M15", states=["post_bos","retest","trending_bear"]),
    dict(code="SHORT_FVG_FILL_H1",      name="FVG Fill Bearish -- H1",               direction="SHORT", timeframe="H1",  states=["trending_bear","retest","post_bos"]),
    dict(code="SHORT_OB_REJECTION_M15", name="OB Rejection SELL -- M15",             direction="SHORT", timeframe="M15", states=["trending_bear","retest","trending_bear"]),
    dict(code="SHORT_DISTRIBUTION_H1",  name="Distribution Zone Breakdown -- H1",    direction="SHORT", timeframe="H1",  states=["high_vol","trending_bear","post_bos"]),
    dict(code="SHORT_CONTINUATION_M15", name="Lower High Continuation SELL -- M15",  direction="SHORT", timeframe="M15", states=["trending_bear","post_bos","retest"]),
]

c = httpx.Client(timeout=30)

def hdr(h): return {"Authorization": f"Bearer {h}"}

# 1. Auth
print("=== Step 1: Login ===")
r = c.post(f"{CS_API}/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASS})
r.raise_for_status()
token = r.json()["data"]["token"]
print(f"  Logged in as {AUTH_USER}")

# 2. HMM state labels
print("=== Step 2: HMM state labels ===")
FALLBACK = {"trending_bull":0,"trending_bear":1,"ranging":2,"post_bos":3,"retest":4,"high_vol":5}
sem_maps = {}
try:
    resp = c.get(f"{CS_API}/api/hmm/models", headers=hdr(token))
    if resp.status_code != 200:
        print(f"  /api/hmm/models returned {resp.status_code} -- using fallback for all TFs")
        sem_maps = {"H1": FALLBACK.copy(), "M15": FALLBACK.copy()}
    else:
        models = resp.json().get("data", [])
        for tf in ("H1", "M15"):
            model = next((m for m in models
                          if m["instrument"].upper() == SYMBOL.upper()
                          and m["timeframe"].upper() == tf
                          and m.get("isActive", True)), None)
            if model is None:
                print(f"  No HMM model for {tf} -- using fallback")
                sem_maps[tf] = FALLBACK.copy(); continue
            raw = c.get(f"{CS_API}/api/hmm/models/{model['id']}/states", headers=hdr(token)).json()
            raw_labels_str = raw.get("data", {}).get("stateLabels") or "{}"
            raw_labels = json.loads(raw_labels_str) if isinstance(raw_labels_str, str) else raw_labels_str
            sem = {}
            for idx_str, label in raw_labels.items():
                ll = label.lower()
                for key, kws in SEMANTIC_KEYWORDS.items():
                    if key not in sem and any(k in ll for k in kws):
                        sem[key] = int(idx_str); break
            sem_maps[tf] = sem
            print(f"  {SYMBOL}/{tf} -> {sem}")
except Exception as e:
    print(f"  HMM models error: {e} -- using fallback")
    sem_maps = {"H1": FALLBACK.copy(), "M15": FALLBACK.copy()}

# 3. Process each strategy
print("=== Step 3: Inject patterns + factors ===")
ok_count = 0; fail_count = 0
for s in STRATEGIES:
    tf   = s["timeframe"]
    sem  = sem_maps.get(tf, sem_maps.get("H1", {}))
    code = s["code"]
    name = s["name"]

    state_indices = [sem.get(k, 0) for k in s["states"]]
    seq_repr = "".join(f"S{i}" for i in state_indices)

    # Upsert pattern
    try:
        pr = c.post(f"{CS_API}/api/patterns", headers=hdr(token), json={
            "code": code, "name": name, "description": "",
            "patternType": "HMM_SEQUENCE", "timeframe": tf,
            "stateSequence": json.dumps(state_indices), "stateSeqRepr": seq_repr,
        })
        pr.raise_for_status()
        pattern_id = pr.json()["data"]["id"]
    except Exception as e:
        print(f"  FAIL {code} pattern: {e}"); fail_count += 1; continue

    # Find active theory by name
    theories = c.get(f"{CS_API}/api/theories", headers=hdr(token)).json().get("data", [])
    existing_theory = next((t for t in theories if t["name"] == name and t.get("isActive", True)), None)

    if existing_theory:
        theory_id = existing_theory["id"]
    else:
        try:
            tr = c.post(f"{CS_API}/api/theories", headers=hdr(token), json={
                "name": name, "description": "", "instrument": SYMBOL,
                "direction": s["direction"], "threshold": 60, "minConfidence": 60.0,
            })
            tr.raise_for_status()
            theory_id = tr.json()["data"]["id"]
        except Exception as e:
            print(f"  FAIL {code} theory: {e}"); fail_count += 1; continue

    # Check if factor with this patternId already exists
    det = c.get(f"{CS_API}/api/theories/{theory_id}", headers=hdr(token)).json()
    factors = det.get("data", {}).get("factors", [])
    has_factor = any(f.get("patternId") == pattern_id for f in factors)

    if not has_factor:
        try:
            fr = c.post(f"{CS_API}/api/theories/{theory_id}/factors", headers=hdr(token), json={
                "patternId": pattern_id, "factorCode": "PATTERN_SIMILARITY",
                "factorType": "HMM_PATTERN", "decisionPoint": 60, "isRequired": True,
                "operator": ">=", "thresholdValue": 0.60, "timeframe": tf, "sortOrder": 1,
            })
            fr.raise_for_status()
            print(f"  OK  {code:<32} theory={theory_id[:8]} pattern={pattern_id[:8]} states={state_indices}")
            ok_count += 1
        except Exception as e:
            print(f"  FAIL {code} factor: {e}"); fail_count += 1
    else:
        print(f"  SKIP {code:<31} factor already linked")
        ok_count += 1

print(f"\n=== Done: {ok_count} OK, {fail_count} FAILED ===")
if fail_count == 0:
    print("All theories now have pattern factors. Restart engine session.")
