# GUIDE LINE — TradeOS v5.1
## Operating Rules | HMM + Bayesian Edition

---

## 1. TEAM ROLES

| Role | Drive | Mandatory Challenge |
|------|-------|---------------------|
| 🏛️ Architect | System coherence, HMM integration | Rejects anything that breaks pipeline |
| 📊 Product Analyst | Real user value, scope | Cuts features not serving core use case |
| ⚙️ Tech Lead | Feasibility, reads tech_preference.md first | No LLM shortcuts |
| 🎨 UX Strategist | Command Center philosophy | Nothing display-only |
| 🗄️ DB Expert | Schema, JSONB, GIN indexes | Enforces Bayesian counter integrity |
| 😈 Devil's Advocate | Stress-tests HMM assumptions | Catches Bayesian edge cases |
| 📝 Scribe | Logs everything, append-only | Never edits past entries |

---

## 2. HMM-SPECIFIC RULES (non-negotiable)

1. **Pattern = state sequence, never candle shape** — cosine similarity on raw OHLC is forbidden
2. **HMM must be trained per instrument** — XAUUSD model ≠ EURUSD model
3. **K selection via BIC** — never hardcode K without BIC validation
4. **Minimum training data: 6 months** — less = unreliable state distributions
5. **Model version tracked in hmm_models table** — every signal references hmm_model_version
6. **StandardScaler saved alongside model** — scaler.pkl + model.pkl always in pair
7. **Viterbi algorithm for sequence decoding** — not forward algorithm (Viterbi is more interpretable)
8. **HMM retraining is background job** — never blocks live signal generation

---

## 3. BAYESIAN-SPECIFIC RULES

1. **Always use Laplace smoothing (α=1)** — prevents P=0 or P=1 on small samples
2. **Show confidence tier with every probability** — P alone without sample size is misleading
3. **Minimum threshold for signal: P(WIN) ≥ 0.55** — below this is essentially random
4. **Update is synchronous after outcome** — no async delay, counter must be current
5. **Never delete Bayesian counters** — only soft-archive (set is_active = FALSE)
6. **State sequence hash = SHA256 first 16 chars** — deterministic, collision-resistant for 6-state seq

---

## 4. CODE STANDARDS

```
Language    : English for all code, comments, commits
C#          : Nullable reference types ON, no warnings tolerated
Python      : Type hints on ALL function signatures
TypeScript  : strict: true, no any types
Commits     : feat|fix|refactor|db|hmm|bayes|test|docs(scope): description
```

---

## 5. LOG FORMAT

### log.md entry
```
## [YYYY-MM-DD HH:MM] — session:{short-id}
Phase: [Foundation|HMM|Theory|UI|Live]
Task: [description]
### Done
- [item]
### In Progress  
- [item]
### Blockers
- [item or None]
### Next
- [item]
---
```

### memory.md milestone
```
## Milestone: [name]
Date: YYYY-MM-DD | Phase: [name] | Status: ✅ | 🔄 | ⏳
### What was built
- [deliverable]
### Key decisions
- [decision: rationale]
### Tech debt
- [item or None]
---
```

---

## 6. DEFINITION OF DONE

- [ ] Code written and functional (no placeholder logic)
- [ ] Basic error handling in place
- [ ] Manual verification or unit test done
- [ ] log.md updated
- [ ] If DB change: migration file exists and is idempotent
- [ ] If new endpoint: documented in idea_framework.md API catalogue
- [ ] If HMM change: hmm_model_version updated in relevant tables

---

## 7. SIGNAL LIFECYCLE

```
generated → (executed | skipped | expired) → (WIN | LOSS | BREAK_EVEN)
                                                       ↓
                                            Bayesian counter updated
                                            pattern_scores updated
                                            HMM transition weights noted
```

Signal is EXPIRED if not recorded within: M1=5min, M5=25min, H1=5h, H4=20h

---

*Every decision must serve the 12-step intelligence pipeline.*
*When in doubt: does this improve pattern recognition or probability accuracy?*
