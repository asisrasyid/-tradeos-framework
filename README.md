# TradeOS — Algorithmic Trading Intelligence System
### AI Agent Dev Framework v5.1 | HMM + Bayesian Edition
### Stack: React · ASP.NET Core · PostgreSQL · Python (HMM + Bayesian)

---

## ⚡ AGENT BOOTSTRAP — READ THIS FIRST

You are an AI agent starting or resuming a development session for **TradeOS**.
Follow this sequence **without exception**:

```
STEP 1 : Read this README.md completely (you are doing this now)
STEP 2 : Read ai-dev-framework-v5/main/guide_line.md
STEP 3 : Read ai-dev-framework-v5/main/idea_framework.md   ← full spec, FILLED
STEP 4 : Read ai-dev-framework-v5/main/tech_preference.md  ← stack, FILLED
STEP 5 : Read project/ai/user.md                           ← find STATUS: start / progress
STEP 6 : Read project/ai/system_snap.md                    ← current build state
STEP 7 : Read project/ai/memory.md                         ← completed milestones
STEP 8 : Read project/ai/log.md                            ← last session activity
STEP 9 : Read ai-dev-framework-v5/output/*.md              ← all design artifacts
STEP 10: Begin work on active task in user.md
```

> **MASTER** — After reading ALL context files above, write the single word
> **"master"** at the very top of your first response. This confirms full
> context is loaded. It is mandatory — do not skip it.

> **DO NOT start from scratch** when log.md / memory.md already have entries.

---

## 🗣️ Language Rules

| Context | Language |
|---------|----------|
| Code, logs, artifacts, comments | **English** |
| Communication to Director | **Bahasa Indonesia** |

---

## 🧭 Core Concept (read this carefully)

TradeOS uses a **three-layer intelligence pipeline**:

```
Layer 1 — FEATURE EXTRACTION
  Raw OHLC → scale-invariant features
  (ATR percentile, momentum z-score, swing ratio, body dominance, HTF slope, liq proximity)

Layer 2 — HMM STATE CLASSIFICATION
  Features → hidden market state (S0…S5)
  Gaussian HMM trained on historical data
  Each candle gets a state label — not a shape match

Layer 3 — BAYESIAN PROBABILITY
  State sequence → P(WIN | seq, theory, instrument)
  Self-updating counter per outcome
  Laplace smoothing prevents overfitting on rare sequences
```

**Pattern = state sequence, NOT candle shape.**
This makes matching scale-invariant and noise-tolerant.

---

## 📁 Project Structure

```
tradeos-framework-v2/
│
├── README.md                                    ← YOU ARE HERE
│
├── ai-dev-framework-v5/
│   ├── main/
│   │   ├── idea_framework.md                    ← Full system spec (FILLED)
│   │   ├── guide_line.md                        ← Dev constitution
│   │   └── tech_preference.md                   ← Stack constraints (FILLED)
│   ├── log/
│   │   ├── change_log.md
│   │   └── log_dev.md
│   └── output/
│       ├── framework_arc.md
│       ├── feature_list.md
│       ├── system_design.md
│       ├── frontend_design.md
│       ├── tech_stack.md
│       ├── database.md
│       ├── decision_log.md
│       ├── improvement_log.md
│       └── templates/
│           ├── api_template.md
│           ├── db_migration_template.md
│           └── pattern_theory_template.md
│
└── project/
    ├── ai/
    │   ├── user.md          ← Task register — Director writes here
    │   ├── system_snap.md   ← Current build state
    │   ├── memory.md        ← Milestone tracker
    │   └── log.md           ← Dev activity log
    ├── docs/
    │   ├── CLAUDE.md        ← Quick dev rules reference
    │   └── hmm_bayesian_spec.md  ← Math spec for HMM + Bayes
    ├── backend/             ← ASP.NET Core 8 C#
    ├── frontend/            ← React 18 + TypeScript + Vite
    ├── python-sidecar/      ← FastAPI + HMM + Bayesian engine
    └── database/
        └── migrations/      ← PostgreSQL migration files
```

---

## 🚀 Director Quick Commands

```
# Start new task
→ Write new entry in project/ai/user.md, set STATUS: start

# Resume session
→ "Baca README.md. Lanjutkan dari task progress di user.md."

# Check progress
→ "Baca README.md. Buat ringkasan dari memory.md dan log.md terbaru."

# Generate specific artifact
→ "Baca README.md. Generate artifact: [nama file]"
```

---

## 👥 Super Team

| Role | Drive |
|------|-------|
| 🏛️ Architect | Coherence, scalability, HMM integration integrity |
| 📊 Product Analyst | Real user value, scope control |
| ⚙️ Tech Lead | Reads tech_preference.md before every stack decision |
| 🎨 UX Strategist | Command Center UX, friction elimination |
| 🗄️ Database Expert | Schema, JSONB discipline, query performance |
| 😈 Devil's Advocate | Stress-test HMM assumptions, Bayesian edge cases |
| 📝 Scribe | Maintains all log files, append-only |

---

*TradeOS Framework v5.1 | HMM + Bayesian Pattern Intelligence*
*Stack: React · ASP.NET Core 8 · Python FastAPI · PostgreSQL · Redis*
