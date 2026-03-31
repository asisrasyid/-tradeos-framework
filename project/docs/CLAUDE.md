# CLAUDE.md — TradeOS v5.1 Dev Rules

> **MANDATORY:** Read README.md first. Write **"master"** at top of first response.

---

## Stack Quick Reference
```
Frontend  : React 18 + TypeScript + Vite + shadcn/ui + Tailwind
Backend   : ASP.NET Core 8 C# (modular monolith)
Compute   : Python 3.11 FastAPI sidecar (HMM + Bayesian engine)
Database  : PostgreSQL 15 + Redis 7
Deploy    : Docker Compose
```

## Context Files (read every session)
```
README.md
project/ai/user.md          ← active tasks
project/ai/system_snap.md   ← current build state
project/ai/memory.md        ← milestones
project/ai/log.md           ← last session
ai-dev-framework-v5/main/   ← spec + rules + stack
```

---

## Core Architecture Rules

1. C# orchestrates → Python computes (never cross this boundary)
2. Pattern = HMM state sequence (NEVER raw candle shape)
3. Probability = Bayesian counter with Laplace smoothing
4. Redis = cache only (PostgreSQL = source of truth)
5. Every API response: `{ success, data, error, timestamp }`
6. Soft delete only on patterns/theories/models
7. `state_sequence` + `factor_snapshot` MUST be in every trade_log row

---

## Intelligence Pipeline (memorize this)
```
Raw OHLC
  → Feature extraction (6 scale-invariant features)
  → HMM classify → state label (S0–S5)
  → State sequence (N states) → pattern match
  → C-Code evaluation (SMC conditions)
  → Theory composite score (decision points)
  → Bayesian P(WIN) lookup
  → BUY / SELL / WAIT + confidence %
  → trade_log (full snapshot)
  → outcome recorded
  → Bayesian counter updated (self-learning)
```

---

## Design System

```css
/* Core colors */
--bg:        #0F172A  /* deep navy */
--surface:   #1E293B  /* slate card */
--accent:    #3B82F6  /* electric blue */
--buy:       #10B981  /* emerald */
--sell:      #EF4444  /* red */
--warning:   #F59E0B  /* amber */
--muted:     #64748B  /* secondary text */

/* Fonts */
UI text: Inter
Prices/numbers/state labels: JetBrains Mono (tabular-nums)
```

## HMM State Colors (consistent across UI)
```
S0 Trending Bull    → emerald  #10B981
S1 Trending Bear    → red      #EF4444
S2 Ranging          → amber    #F59E0B
S3 Post-BOS         → blue     #3B82F6
S4 Retest Zone      → purple   #8B5CF6
S5 High Volatility  → coral    #F97316
```

---

## Commit Convention
```
feat(module): description
fix(module): description
hmm(training): description
bayes(counter): description
db(migration): V{N}__description
```

---

## Bayesian Quick Formula
```
P(WIN) = (wins + 1) / (total + 2)   ← Laplace smoothing, α=1

Confidence tiers:
  < 10 samples  → "insufficient"
  10–29         → "developing"
  30–99         → "reliable"
  ≥ 100         → "strong"
```

---

*Full spec: ai-dev-framework-v5/main/idea_framework.md*
*Full rules: ai-dev-framework-v5/main/guide_line.md*
