# FRONTEND DESIGN — TradeOS v5.1

## Design Philosophy: "Command Center"
Every panel has at least one action button. Nothing is display-only.
A trader should feel in control at all times.

## Design Tokens (tokens.css)

```css
:root {
  /* Backgrounds */
  --bg-base:      #0F172A;
  --bg-surface:   #1E293B;
  --bg-elevated:  #263347;

  /* Text */
  --text-primary:   #F1F5F9;
  --text-secondary: #94A3B8;
  --text-tertiary:  #64748B;

  /* Semantic — trading */
  --buy:      #10B981; --buy-bg:  rgba(16,185,129,0.12);
  --sell:     #EF4444; --sell-bg: rgba(239,68,68,0.12);
  --watch:    #F59E0B; --watch-bg:rgba(245,158,11,0.12);
  --win:      #10B981;
  --loss:     #EF4444;
  --be:       #F59E0B;

  /* Accent */
  --accent:   #3B82F6;

  /* HMM State Colors (consistent everywhere) */
  --s0-trend-bull:  #10B981; /* emerald */
  --s1-trend-bear:  #EF4444; /* red */
  --s2-ranging:     #F59E0B; /* amber */
  --s3-post-bos:    #3B82F6; /* blue */
  --s4-retest:      #8B5CF6; /* purple */
  --s5-high-vol:    #F97316; /* coral */

  /* Bayesian tier colors */
  --tier-insufficient: #64748B;
  --tier-developing:   #F59E0B;
  --tier-reliable:     #3B82F6;
  --tier-strong:       #10B981;

  /* Typography */
  --font-ui:   'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace; /* prices, states, numbers */
}
```

## Key Component Specs

### SignalCard
```
[BUY/SELL/WATCH] XAUUSD · H1                    [84.2%] ████████░
                 Break & Retest Bullish
                 14:32 · Score: 15.0 · P(WIN): 73.6% (reliable, n=70)
State: S0→S0→S3→S2→S4     [Record Outcome]  [Detail]
```

### StateTimeline
```
Horizontal sequence of colored state pills:
[S0 Bull][S0 Bull][S3 BOS][S2 Range][S4 Retest]  log_p: -8.54
Each pill colored per HMM state color system
```

### BayesGauge
```
P(WIN) = 73.6%  ████████░░  [reliable · n=70]
         wins: 52  losses: 18  be: 0
```

### FactorRow
```
HMM State Sequence    [+5] ██████████  0.87 match
HTF Bias Bullish      [+3] ████████
EQL Swept             [+2] ██████
Price in OB           [+2] █████░  0.88
HMM Ranging (veto)    [-4] ██████████ (not triggered — good)
```

## Page Layout: Live Command Center
```
TOPBAR: Logo | Live | Theories | Patterns | HMM | Backtest | Trades
SIDEBAR: Active theories + win rates | Instruments | Quick actions
MAIN:
  Row 1: Metric cards (WR, PF, Sharpe, MaxDD, Signals)
  Row 2: [Factor panel + State timeline] | [Live signals]
  Row 3: Trade log table with outcome recording
```

## Page Layout: Live (Updated — 3-Column with HMM Alert Log)
```
3-column grid: 3fr | 4fr | 3fr  (log open)
               3fr | 4fr | 36px (log collapsed)

Col 1 (3fr):  MT5 Positions Table (aggressive/smart/cascade engine status)
Col 2 (4fr):  Trading Panel (signal dashboard, outcome recording)
Col 3 (3fr):  HMM Alert Log Panel  ← NEW
              OR
              36px tab "HMM LOG" vertical text + live dot (collapsed)
```

## Component: HmmAlertLog
```
┌─ HMM LOG ● [XAUUSD ▼] [⏸] [🗑] [◀] ──────────────────┐
│ 12 / 500 entries                           ● live       │
│ ■ ≥70% kuat  ■ 45–69% sedang  ■ <45% lemah             │
├────────────────────────────────────────────────────────┤
│ 14:32:05 [M1][M5] [STATE] [72%]            ▲ BUY       │
│ S2 (Ranging) · → Netral                                 │
├────────────────────────────────────────────────────────┤
│ 14:32:05 [H1] [S/R] [65%]                  ▼ SELL      │
│ Mendekati resistance (skor 0.82) — siapkan SELL         │
├────────────────────────────────────────────────────────┤
│ 14:00:00 [--] [DIV] [58%]                  ▼ SELL      │
│ Divergensi bias: LTF bullish vs HTF bearish — bull trap │
└────────────────────────────────────────────────────────┘
```

### Sub-components
- **TfBadges** — `log.tf` split by comma → multiple small TF pills (gray bg, monospace)
- **ConfBadge** — `{pct}%` colored pill: ≥70% = `--buy`, 45-69% = `--warning`, <45% = `--sell`
- **ActionBadge** — right-aligned colored pill: `▲ BUY` (green), `▼ SELL` (red), `● NEUTRAL` (gray)
- **LogEntry** — `borderLeft` colored by severity + two rows: meta | message

### Severity Colors
| Severity | Border | Background | Use |
|----------|--------|-----------|-----|
| info | `--accent` | accent/5% | STATE neutral/bull |
| warning | `--warning` | warning/5% | S/R proximity, LIQ, MOM moderate |
| danger | `--sell` | sell/5% | VOL high, MOM extreme |
| divergence | `#f97316` | orange/5% | Cross-TF divergence |
| system | `--border` | transparent | System messages (start/stop) |

### Smart TF Polling Logic
```
Every 30s tick:
  always:       M1, M5
  min % 5 == 0: add M15
  min % 15 == 0: add M30
  min == 0:     add H1
  min == 0 && hour % 4 == 0: add H4
```
