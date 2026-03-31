import { Pause, Play, Trash2, ChevronLeft } from 'lucide-react'
import type { AlertLog } from '../hooks/useHmmAlertLog'

const SYMBOL_OPTIONS = [
  'XAUUSDc','XAUUSDm','XAUUSD','XAGUSDm','XAGUSD',
  'BTCUSDm','BTCUSD','ETHUSDm','ETHUSD',
  'EURUSD','GBPUSDm','GBPUSD','USDJPY','USDCHF','AUDUSD','NAS100',
]

const SEV: Record<string, { border: string; bg: string; color: string }> = {
  info:       { border: 'var(--accent)',  bg: 'rgba(99,102,241,0.05)',  color: 'var(--accent)'   },
  warning:    { border: 'var(--warning)', bg: 'rgba(245,158,11,0.05)',  color: 'var(--warning)'  },
  danger:     { border: 'var(--sell)',    bg: 'rgba(239,68,68,0.05)',   color: 'var(--sell)'     },
  divergence: { border: '#f97316',        bg: 'rgba(249,115,22,0.05)', color: '#f97316'          },
  system:     { border: 'var(--border)',  bg: 'transparent',            color: 'var(--text-faint)'},
}

// Confidence thresholds → colour
function confColor(c: number): string {
  if (c >= 0.70) return 'var(--buy)'
  if (c >= 0.45) return 'var(--warning)'
  return 'var(--sell)'
}

function ConfBadge({ confidence }: { confidence: number }) {
  if (confidence <= 0) return null
  const pct   = Math.round(confidence * 100)
  const color = confColor(confidence)
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 9, fontWeight: 700, padding: '1px 6px',
      borderRadius: 3, border: `1px solid ${color}40`,
      background: `${color}15`, color,
      fontFamily: 'var(--font-mono)',
    }}>
      {pct}%
    </span>
  )
}

const ACTION_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  BUY:     { bg: 'rgba(34,197,94,0.15)',  color: 'var(--buy)',     label: '▲ BUY'     },
  SELL:    { bg: 'rgba(239,68,68,0.15)',  color: 'var(--sell)',    label: '▼ SELL'    },
  NEUTRAL: { bg: 'rgba(148,163,184,0.1)', color: 'var(--text-muted)', label: '● NEUTRAL' },
}

function ActionBadge({ action }: { action: string }) {
  if (!action) return null
  const s = ACTION_STYLE[action] ?? ACTION_STYLE.NEUTRAL
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, padding: '1px 6px', borderRadius: 3,
      background: s.bg, color: s.color,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.3px',
      marginLeft: 'auto', flexShrink: 0,
    }}>
      {s.label}
    </span>
  )
}

function TfBadges({ tf }: { tf: string }) {
  if (tf === '--') return null
  const tfs = tf.split(',').filter(Boolean)
  return (
    <>
      {tfs.map(t => (
        <span key={t} style={{
          fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          background: 'var(--surface-2)', color: 'var(--text-muted)',
          border: '1px solid var(--border)',
        }}>
          {t}
        </span>
      ))}
    </>
  )
}

function LogEntry({ log }: { log: AlertLog }) {
  const s = SEV[log.severity] ?? SEV.system
  return (
    <div style={{
      borderLeft: `3px solid ${s.border}`,
      background: s.bg,
      padding: '5px 10px',
      borderRadius: '0 4px 4px 0',
      display: 'flex',
      flexDirection: 'column',
      gap: 3,
    }}>
      {/* Row 1: timestamp · TF badges · tag badge · confidence · action */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', flexShrink: 0 }}>
          {log.ts}
        </span>
        <TfBadges tf={log.tf} />
        <span style={{
          fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          background: `${s.color}25`, color: s.color,
        }}>
          {log.tag}
        </span>
        <ConfBadge confidence={log.confidence} />
        <ActionBadge action={log.action} />
      </div>
      {/* Row 2: message */}
      <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.45 }}>
        {log.msg}
      </div>
    </div>
  )
}

interface Props {
  instrument:         string
  onInstrumentChange: (v: string) => void
  enabled:            boolean
  logs:               AlertLog[]
  isPaused:           boolean
  onPause:            () => void
  onClear:            () => void
  onToggle:           () => void
}

export default function HmmAlertLog({
  instrument, onInstrumentChange,
  enabled, logs, isPaused, onPause, onClear, onToggle,
}: Props) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 10, overflow: 'hidden', height: '100%', minHeight: 0,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 10px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.5px' }}>
            HMM LOG
          </span>
          {enabled && !isPaused && (
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--buy)', display: 'inline-block',
              animation: 'pulse 1.5s infinite',
            }} />
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <select
            value={instrument}
            onChange={e => onInstrumentChange(e.target.value)}
            style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: 'var(--text)', fontFamily: 'var(--font-mono)', fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {SYMBOL_OPTIONS.map(s => <option key={s}>{s}</option>)}
          </select>
          <button onClick={onPause} className="btn-icon-danger" title={isPaused ? 'Resume' : 'Pause'}
            style={{ color: isPaused ? 'var(--buy)' : undefined }}>
            {isPaused ? <Play size={11} /> : <Pause size={11} />}
          </button>
          <button onClick={onClear} className="btn-icon-danger" title="Clear log">
            <Trash2 size={11} />
          </button>
          <button onClick={onToggle} className="btn-icon-danger" title="Collapse">
            <ChevronLeft size={11} />
          </button>
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        padding: '3px 10px', borderBottom: '1px solid var(--border)',
        fontSize: 10, color: 'var(--text-faint)', background: 'var(--surface)',
        flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>{logs.length} / 500 entries</span>
        <span style={{ color: isPaused ? 'var(--warning)' : enabled ? 'var(--buy)' : 'var(--text-faint)' }}>
          {isPaused ? '⏸ paused' : enabled ? '● live' : '○ engine off'}
        </span>
      </div>

      {/* Confidence legend */}
      <div style={{
        padding: '3px 10px', borderBottom: '1px solid var(--border)',
        fontSize: 9, color: 'var(--text-faint)', background: 'var(--surface)',
        flexShrink: 0, display: 'flex', gap: 10,
      }}>
        <span style={{ color: 'var(--buy)' }}>■ ≥70% kuat</span>
        <span style={{ color: 'var(--warning)' }}>■ 45–69% sedang</span>
        <span style={{ color: 'var(--sell)' }}>■ &lt;45% lemah</span>
      </div>

      {/* Log list */}
      <div style={{
        flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
        gap: 4, padding: 8,
      }}>
        {!enabled && logs.length === 0 && (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 8,
            color: 'var(--text-faint)', fontSize: 12, textAlign: 'center', padding: 20,
          }}>
            <span style={{ fontSize: 28, opacity: 0.3 }}>📡</span>
            <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Engine tidak aktif</div>
            <div style={{ fontSize: 11 }}>
              Jalankan salah satu engine trading<br />untuk memulai analisis HMM live.
            </div>
          </div>
        )}
        {logs.map(log => <LogEntry key={log.id} log={log} />)}
      </div>
    </div>
  )
}
