import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type AggressiveSession, type SmartSession, type SmartTradeLog, type CascadeSession, type HmmAdvisory, type Theory, type EngineSession, type EngineStatusResult } from '../lib/api'
import React, { useState, useEffect, useRef } from 'react'
import { useHmmAlertLog } from '../hooks/useHmmAlertLog'
import HmmAlertLog from '../components/HmmAlertLog'

const SYMBOL_OPTIONS = [
  // Gold
  'XAUUSDc', 'XAUUSDm', 'XAUUSD',
  // Silver
  'XAGUSDc', 'XAGUSDm', 'XAGUSD',
  // Crypto (cent / micro / standard)
  'BTCUSDc', 'BTCUSDm', 'BTCUSD', 'ETHUSDc', 'ETHUSDm', 'ETHUSD',
  // Forex majors
  'EURUSD', 'GBPUSDm', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD',
]

// ── HMM Global Badge — always visible in header ───────────────────────────────
function HmmGlobalBadge() {
  const qc = useQueryClient()
  const [symbol, setSymbol] = useState('XAUUSDm')
  const [open, setOpen]     = useState(false)
  const [tab, setTab]       = useState<'symbol' | 'engine'>('symbol')
  const [selTheory, setSelTheory] = useState('')
  const [selTf, setSelTf]         = useState('M15')
  const ref = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const { data, isFetching } = useQuery<HmmAdvisory>({
    queryKey: ['hmm-global', symbol],
    queryFn:  () => api.engineLastSignal(symbol),
    refetchInterval: 10_000,
    throwOnError: false,
    retry: false,
  })

  const { data: engineStatus } = useQuery<EngineStatusResult>({
    queryKey: ['engine-status'],
    queryFn:  () => api.engineStatus(),
    refetchInterval: 5_000,
    throwOnError: false,
    retry: false,
  })

  const { data: theories } = useQuery<Theory[]>({
    queryKey: ['theories-list'],
    queryFn:  () => api.listTheories(),
    throwOnError: false,
    retry: false,
    enabled: open && tab === 'engine',
  })

  const startMut = useMutation({
    mutationFn: () => api.engineStart(selTheory, selTf),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engine-status'] })
      qc.invalidateQueries({ queryKey: ['hmm-global', symbol] })
    },
  })

  const stopMut = useMutation({
    mutationFn: (sessionId: string) => api.engineStop(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['engine-status'] }),
  })

  // Filter sessions for selected symbol
  const activeSessions = (engineStatus?.sessions ?? []).filter(
    s => s.instrument.toUpperCase() === symbol.toUpperCase() && s.status === 'running'
  )

  // Derive badge appearance
  let bg = 'var(--surface-2)', border = 'var(--border)', color = 'var(--text-muted)'
  let label = 'HMM offline', dot = '○', title = 'Signal Engine tidak running'

  if (data) {
    if (!data.found) {
      label = `HMM · ${symbol.replace('m','').replace('c','')}`
      dot   = '◌'
      title = 'Signal Engine running — belum ada sinyal untuk symbol ini'
      color = 'var(--text-muted)'
    } else {
      const fresh = data.age_s <= 300
      const dir   = data.direction === 'LONG' ? 'BUY' : 'SELL'
      const age   = data.age_s < 60 ? `${data.age_s}s` : `${Math.round(data.age_s / 60)}m`
      bg     = fresh ? '#22c55e18' : '#f59e0b18'
      border = fresh ? '#22c55e'   : '#f59e0b'
      color  = fresh ? '#22c55e'   : '#f59e0b'
      dot    = fresh ? '●'         : '◑'
      label  = `HMM · ${dir} ${data.similarity.toFixed(2)} · ${age}`
      title  = `${symbol} | ${data.timeframe} | similarity ${data.similarity.toFixed(3)} | ${age} yang lalu | ${fresh ? 'FRESH ✓' : 'STALE — sinyal mulai tua'}`
    }
  }

  // Running count badge on HMM dot
  const totalRunning = (engineStatus?.sessions ?? []).filter(s => s.status === 'running').length

  const DD_LABEL: Record<string, string> = { symbol: 'SYMBOL', engine: 'ENGINE' }
  const tfOptions = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4']

  return (
    <div ref={ref} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 4 }}>
      {/* Main badge */}
      <div
        onClick={() => setOpen(o => !o)}
        title={title}
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '3px 8px', borderRadius: 6, cursor: 'pointer',
          background: bg, border: `1px solid ${border}`, color,
          fontSize: 11, fontWeight: 600, letterSpacing: '0.3px',
          userSelect: 'none', transition: 'all 0.2s',
          opacity: isFetching ? 0.7 : 1,
        }}
      >
        <span style={{ fontSize: 8, lineHeight: 1 }}>{dot}</span>
        <span>{label}</span>
        {totalRunning > 0 && (
          <span style={{
            fontSize: 9, background: '#22c55e', color: '#000',
            borderRadius: '999px', padding: '0 4px', lineHeight: '14px',
            fontWeight: 700, marginLeft: 1,
          }}>{totalRunning}</span>
        )}
        <span style={{ fontSize: 9, color: 'var(--text-faint)', marginLeft: 2 }}>▾</span>
      </div>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, zIndex: 999,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 8, minWidth: 260,
          boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          overflow: 'hidden',
        }}>
          {/* Tab bar */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
            {(['symbol', 'engine'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  flex: 1, padding: '7px 0', fontSize: 10, fontWeight: 700,
                  letterSpacing: '0.5px', cursor: 'pointer', border: 'none',
                  background: tab === t ? 'var(--surface-2)' : 'transparent',
                  color: tab === t ? 'var(--accent)' : 'var(--text-muted)',
                  borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {DD_LABEL[t]}
              </button>
            ))}
          </div>

          {/* SYMBOL tab */}
          {tab === 'symbol' && (
            <div style={{ maxHeight: 220, overflowY: 'auto', padding: '4px 0' }}>
              {SYMBOL_OPTIONS.map(s => (
                <div
                  key={s}
                  onClick={() => { setSymbol(s); setOpen(false) }}
                  style={{
                    padding: '5px 12px', fontSize: 12, cursor: 'pointer',
                    color: s === symbol ? 'var(--accent)' : 'var(--text)',
                    background: s === symbol ? 'var(--accent)15' : 'transparent',
                    fontWeight: s === symbol ? 600 : 400,
                  }}
                  onMouseEnter={e => { if (s !== symbol) (e.target as HTMLElement).style.background = 'var(--surface-2)' }}
                  onMouseLeave={e => { if (s !== symbol) (e.target as HTMLElement).style.background = 'transparent' }}
                >
                  {s}
                </div>
              ))}
            </div>
          )}

          {/* ENGINE tab */}
          {tab === 'engine' && (
            <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Active sessions for this symbol */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: '0.5px', marginBottom: 6 }}>
                  ACTIVE — {symbol}
                </div>
                {activeSessions.length === 0 ? (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 0' }}>
                    No running sessions
                  </div>
                ) : (
                  activeSessions.map(s => (
                    <div key={s.session_id} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '4px 6px', borderRadius: 4, background: 'var(--surface-2)',
                      marginBottom: 4,
                    }}>
                      <div style={{ fontSize: 11 }}>
                        <span style={{ color: s.direction === 'LONG' ? 'var(--buy)' : 'var(--sell)', fontWeight: 700 }}>
                          {s.direction}
                        </span>
                        <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{s.timeframe}</span>
                        <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                          {s.signals_fired} sig
                        </span>
                        {s.no_signal_warning && (
                          <span title="Belum ada sinyal setelah 20 bars — cek pattern_states"
                            style={{ marginLeft: 6, color: 'var(--warning)', fontSize: 10 }}>⚠</span>
                        )}
                      </div>
                      <button
                        onClick={() => stopMut.mutate(s.session_id)}
                        disabled={stopMut.isPending}
                        style={{
                          fontSize: 10, padding: '2px 6px', borderRadius: 3,
                          background: 'var(--sell-bg)', color: 'var(--sell)',
                          border: '1px solid var(--sell)40', cursor: 'pointer',
                        }}
                      >
                        Stop
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* Divider */}
              <div style={{ borderTop: '1px solid var(--border)' }} />

              {/* Quick start */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: '0.5px', marginBottom: 8 }}>
                  QUICK START
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <select
                    value={selTheory}
                    onChange={e => setSelTheory(e.target.value)}
                    style={{
                      fontSize: 11, padding: '4px 6px', borderRadius: 4, width: '100%',
                      background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)',
                    }}
                  >
                    <option value="">— pilih theory —</option>
                    {(theories ?? []).map(t => (
                      <option key={t.id} value={t.id}>
                        {t.name} · {t.instrument} · {t.direction}
                      </option>
                    ))}
                  </select>

                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <select
                      value={selTf}
                      onChange={e => setSelTf(e.target.value)}
                      style={{
                        fontSize: 11, padding: '4px 6px', borderRadius: 4, flex: 1,
                        background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)',
                      }}
                    >
                      {tfOptions.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                    </select>

                    <button
                      onClick={() => { if (selTheory) startMut.mutate() }}
                      disabled={!selTheory || startMut.isPending}
                      style={{
                        fontSize: 11, padding: '4px 10px', borderRadius: 4,
                        background: selTheory ? 'var(--accent)' : 'var(--surface-2)',
                        color: selTheory ? '#000' : 'var(--text-muted)',
                        border: 'none', cursor: selTheory ? 'pointer' : 'default',
                        fontWeight: 700, flex: 1,
                      }}
                    >
                      {startMut.isPending ? '…' : '▶ Start'}
                    </button>
                  </div>

                  {startMut.isError && (
                    <div style={{ fontSize: 10, color: 'var(--sell)', padding: '2px 0' }}>
                      {startMut.error instanceof Error ? startMut.error.message : 'Failed'}
                    </div>
                  )}
                  {startMut.isSuccess && (
                    <div style={{ fontSize: 10, color: 'var(--buy)', padding: '2px 0' }}>
                      Signal Engine started ✓
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SymbolSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="rounded px-2 py-1 text-xs w-28"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
      {SYMBOL_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
    </select>
  )
}

// ── Aggressive Engine Panel ───────────────────────────────────────────────────

function AggressiveSessionRow({ sess, onStop, onStopAndClose }: {
  sess: AggressiveSession
  onStop: (id: string) => void
  onStopAndClose: (id: string) => void
}) {
  const profit   = sess.total_profit ?? 0
  const pColor   = profit > 0 ? 'var(--buy)' : profit < 0 ? 'var(--sell)' : 'var(--text-muted)'
  const dotColor = sess.active ? 'var(--warning)' : 'var(--text-faint)'
  const currDir  = sess.current_direction ?? sess.direction
  const dirColor = currDir === 'BUY' ? 'var(--buy)' : currDir === 'SELL' ? 'var(--sell)' : 'var(--accent)'

  return (
    <div className="session-row session-row--warn">

      {/* Row 1: identity + badges + actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, flexWrap: 'wrap' }}>
        {/* Left: symbol · direction badge · size */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flexWrap: 'wrap' }}>
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${sess.active ? 'animate-pulse' : ''}`}
            style={{ background: dotColor }} />
          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', whiteSpace: 'nowrap' }}>
            {sess.symbol}
          </span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap',
            background: currDir === 'BUY' ? '#10b98120' : currDir === 'SELL' ? '#ef444420' : 'var(--accent)18',
            color: dirColor, border: `1px solid ${dirColor}40`,
          }}>
            {sess.direction === 'AUTO'
              ? `AUTO→${sess.current_direction ?? '?'}`
              : sess.current_direction && sess.current_direction !== sess.direction
                ? `${sess.direction}→${sess.current_direction}`
                : sess.direction}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            ×{sess.layers} · {sess.volume}lot
          </span>
          {sess.flip_mode && sess.flip_mode !== 'none' && (
            <span style={{ fontSize: 10, color: 'var(--text-faint)', whiteSpace: 'nowrap' }}>
              flip:{sess.flip_mode}{sess.total_flips > 0 ? ` ×${sess.total_flips}` : ''}
              {sess.consecutive_tp > 0 ? ` (${sess.consecutive_tp}c)` : ''}
            </span>
          )}
        </div>
        {/* Right: status badges + action buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, flexWrap: 'wrap' }}>
          {sess.mc_guard && sess.mc_status && sess.mc_status !== 'OK' && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
              background: sess.mc_status === 'EMERGENCY' ? 'var(--sell)' :
                          sess.mc_status === 'DANGER'    ? '#dc2626' :
                          sess.mc_status === 'WARNING'   ? 'var(--warning)' : 'var(--accent)',
              color: '#000',
            }}>MC:{sess.mc_status}</span>
          )}
          {sess.trend_guided && (
            <span style={{ fontSize: 10, padding: '2px 5px', borderRadius: 4, background: 'var(--buy)20', color: 'var(--buy)', border: '1px solid var(--buy)40', fontWeight: 600 }}>TG</span>
          )}
          {sess.hmm_gate_enabled && sess.active && (
            sess.hmm_in_danger ? (
              <span
                className="animate-pulse"
                title={`HMM validasi: ${sess.hmm_cooldown_reason} — re-check ${sess.hmm_recheck_in}s${sess.hmm_vote_last ? ` (vote: ${sess.hmm_vote_last})` : ''}`}
                style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: '#7c3aed22', color: '#a78bfa', border: '1px solid #7c3aed' }}>
                ⏳ HMM {sess.hmm_recheck_in}s
              </span>
            ) : (
              <span title="HMM Gate aktif — kondisi aman"
                style={{ fontSize: 10, padding: '2px 5px', borderRadius: 4, background: '#7c3aed11', color: '#7c3aed', border: '1px solid #7c3aed44' }}>
                HMM
              </span>
            )
          )}
          {sess.active && (sess.sl_cooldown_remaining ?? 0) > 0 && (
            <span title="SL cooldown — menunggu sebelum reopen" style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: 'var(--sell)20', color: 'var(--sell)', border: '1px solid var(--sell)' }}>
              ⏸ {sess.sl_cooldown_remaining}s
            </span>
          )}
          <span className={`badge ${sess.active ? 'badge--warn' : 'badge--neutral'}`}>
            {sess.active ? 'running' : 'stopped'}
          </span>
          {sess.active && (<>
            <button onClick={() => onStop(sess.session_id)} className="btn-stop">STOP</button>
            <button onClick={() => onStopAndClose(sess.session_id)} className="btn-stop"
              style={{ background: 'var(--sell)', borderColor: 'var(--sell)' }}>SELL ALL</button>
          </>)}
        </div>
      </div>

      {/* Row 2: stats (left) + P&L (right) */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        {/* Left: positions · trade counts · uptime */}
        <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap', alignItems: 'center' }}>
          <span>
            <b style={{ color: 'var(--text)' }}>{sess.open_positions}</b>
            {(sess.pending_orders ?? 0) > 0 && (
              <span title="Pending limit orders" style={{ color: '#34d399', marginLeft: 2 }}>+{sess.pending_orders}⏳</span>
            )}
            <span style={{ color: 'var(--text-faint)' }}>/{sess.layers}</span>
            {' '}open
          </span>
          <span>W:<b style={{ color: 'var(--buy)' }}>{sess.total_closed_win}</b></span>
          {sess.total_closed_sl > 0 && (
            <span>SL:<b style={{ color: 'var(--sell)' }}>{sess.total_closed_sl}</b></span>
          )}
          {sess.total_closed_other > 0 && (
            <span>Oth:<b style={{ color: 'var(--text)' }}>{sess.total_closed_other}</b></span>
          )}
          <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>
            Up {Math.floor(sess.uptime_s / 60)}m{sess.uptime_s % 60}s
          </span>
          <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>tgt ${sess.profit_target}</span>
        </div>
        {/* Right: P&L block — most important metric, prominent display */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', color: pColor, lineHeight: 1.1 }}>
            {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
          </div>
          {sess.floating_pnl !== 0 && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: sess.floating_pnl >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
              float {sess.floating_pnl >= 0 ? '+' : ''}${sess.floating_pnl.toFixed(2)}
            </div>
          )}
          {sess.peak_profit > 0 && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-faint)' }}>
              peak ${sess.peak_profit.toFixed(2)}
            </div>
          )}
          {(sess.total_net ?? 0) !== 0 && (sess.total_net ?? 0) !== profit && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: (sess.total_net ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
              net {(sess.total_net ?? 0) >= 0 ? '+' : ''}${(sess.total_net ?? 0).toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* Row 3: last action / error */}
      <div style={{ fontSize: 11, color: sess.error ? 'var(--sell)' : 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {sess.error ? `ERROR: ${sess.error}` : sess.last_action}
      </div>

      {/* Row 4: recommendation (stopped only) */}
      {!sess.active && sess.next_recommendation && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, marginTop: 2 }}>
          <span style={{ color: 'var(--text-muted)' }}>Next session:</span>
          <span style={{
            fontWeight: 700, padding: '1px 8px', borderRadius: 4,
            background: sess.next_recommendation === 'BUY'  ? 'var(--buy)20'  :
                        sess.next_recommendation === 'SELL' ? 'var(--sell)20' : 'var(--surface-2)',
            color:      sess.next_recommendation === 'BUY'  ? 'var(--buy)'  :
                        sess.next_recommendation === 'SELL' ? 'var(--sell)' : 'var(--text-muted)',
            border: `1px solid ${sess.next_recommendation === 'BUY' ? 'var(--buy)' : sess.next_recommendation === 'SELL' ? 'var(--sell)' : 'var(--border)'}`,
          }}>{sess.next_recommendation}</span>
          <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>M5+M15 vote</span>
        </div>
      )}
    </div>
  )
}

// ── Smart / Trading Panel ─────────────────────────────────────────────────────

function VoteChip({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value ?? 0
  const color = v > 0 ? 'var(--buy)' : v < 0 ? 'var(--sell)' : 'var(--text-faint)'
  return (
    <span className="text-xs font-mono" style={{ color }}>
      {label}:{v > 0 ? '+' : ''}{v}
    </span>
  )
}

function SmartSessionRow({ sess, onStop, onResumeAi }: {
  sess: SmartSession
  onStop: (id: string) => void
  onResumeAi: (id: string) => void
}) {
  const isPaused = sess.ai_enabled && sess.ai_status === 'ai_paused'
  const dotColor = isPaused ? 'var(--warning)' : sess.active ? '#a78bfa' : 'var(--text-faint)'
  const profit   = sess.total_profit ?? 0
  const pColor   = profit > 0 ? 'var(--buy)' : profit < 0 ? 'var(--sell)' : 'var(--text-muted)'

  return (
    <div className={`session-row ${isPaused ? 'session-row--warn' : sess.active ? 'session-row--smart' : 'session-row--stopped'}`}>

      {/* Row 1: identity + badges + actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flexWrap: 'wrap' }}>
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${sess.active && !isPaused ? 'animate-pulse' : ''}`}
            style={{ background: dotColor }} />
          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', whiteSpace: 'nowrap' }}>
            {sess.symbol}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            {sess.timeframe} · ×{sess.max_layers} · {sess.volume}lot
          </span>
          {sess.ai_enabled && <span className="badge badge--ai">AI</span>}
          {sess.allow_short
            ? <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: '#ef444420', color: 'var(--sell)', border: '1px solid #ef444440', fontWeight: 700 }}>SHORT</span>
            : <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text-faint)', border: '1px solid var(--border)' }}>LONG</span>
          }
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, flexWrap: 'wrap' }}>
          {sess.ai_enabled && (
            <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-faint)' }}>
              {sess.ai_calls_this_hour}/{sess.max_calls_per_hour}/hr
            </span>
          )}
          <span className={`badge ${isPaused ? 'badge--warn' : sess.active ? 'badge--ai' : 'badge--neutral'}`}>
            {isPaused ? 'AI PAUSED' : sess.active ? 'running' : 'stopped'}
          </span>
          {isPaused && (
            <button onClick={() => onResumeAi(sess.session_id)}
              style={{ padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, cursor: 'pointer', background: 'var(--warn-bg)', color: 'var(--warning)', border: '1px solid var(--warn-bg)' }}>
              RESUME AI
            </button>
          )}
          {sess.active && (
            <button onClick={() => onStop(sess.session_id)} className="btn-stop">STOP</button>
          )}
        </div>
      </div>

      {/* Row 2: stats (left) + P&L (right) */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap', alignItems: 'center' }}>
          <span>
            <b style={{ color: 'var(--text)' }}>{sess.open_positions}</b>
            <span style={{ color: 'var(--text-faint)' }}>/{sess.max_layers}</span>
            {' '}open
          </span>
          <span>
            W:<b style={{ color: 'var(--buy)' }}>{sess.total_closed_win}</b>
            {' '}L:<b style={{ color: 'var(--sell)' }}>{sess.total_closed_loss}</b>
          </span>
          {sess.ai_enabled
            ? <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>{sess.entries_per_decision} ent/dec</span>
            : <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>TP/SL ×{sess.tp_atr_mult}/{sess.sl_atr_mult}</span>
          }
          <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>
            Up {Math.floor(sess.uptime_s / 60)}m{sess.uptime_s % 60}s
          </span>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', color: pColor, lineHeight: 1.1 }}>
            {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Row 3: last action / error */}
      <div style={{ fontSize: 11, color: sess.error ? 'var(--sell)' : 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {sess.error ? `ERROR: ${sess.error}` : sess.last_action}
      </div>

      {/* Row 4: AI last reasoning */}
      {sess.ai_enabled && sess.ai_last_reasoning && (
        <div style={{ fontSize: 11, borderRadius: 4, padding: '4px 8px', lineHeight: 1.5, background: '#a78bfa08', border: '1px solid #a78bfa20', color: 'var(--text-muted)' }}>
          <span style={{ fontWeight: 700, color: '#a78bfa' }}>AI: </span>
          {sess.ai_last_decision && (
            <span style={{ fontWeight: 700, marginRight: 4,
              color: sess.ai_last_decision === 'BUY' ? 'var(--buy)' : sess.ai_last_decision === 'SELL' ? 'var(--sell)' : 'var(--text-faint)' }}>
              {sess.ai_last_decision}
            </span>
          )}
          {sess.ai_last_confidence > 0 && (
            <span style={{ color: 'var(--text-faint)', marginRight: 4 }}>
              conf={sess.ai_last_confidence.toFixed(2)} ·{' '}
            </span>
          )}
          <span>{sess.ai_last_reasoning}</span>
        </div>
      )}
    </div>
  )
}

function SmartTradeLogRow({ log, expanded, onToggle }: {
  log: SmartTradeLog
  expanded: boolean
  onToggle: () => void
}) {
  const dirColor     = log.direction === 'BUY' ? 'var(--buy)' : 'var(--sell)'
  const outcomeColor = log.outcome === 'WIN' ? 'var(--buy)' : log.outcome === 'LOSS' ? 'var(--sell)' : 'var(--text-muted)'
  return (
    <>
      <tr className="border-b text-xs cursor-pointer tr-hover transition-colors"
        style={{ borderColor: 'var(--border)' }}
        onClick={log.aiEnabled && log.llmReasoning ? onToggle : undefined}>
        <td className="py-1.5 px-2">
          <div className="flex items-center gap-1">
            {log.aiEnabled
              ? <span className="badge badge--ai">AI</span>
              : <span className="badge badge--neutral">V</span>
            }
            <span className="font-semibold" style={{ color: dirColor }}>{log.direction}</span>
          </div>
        </td>
        <td className="py-1.5 px-2 mono" style={{ color: 'var(--text)' }}>{(log.entryPrice ?? 0).toFixed(3)}</td>
        <td className="py-1.5 px-2 mono" style={{ color: 'var(--buy)' }}>{(log.tpPrice ?? 0).toFixed(3)}</td>
        <td className="py-1.5 px-2 mono" style={{ color: 'var(--sell)' }}>{(log.slPrice ?? 0).toFixed(3)}</td>
        <td className="py-1.5 px-2">
          <div className="flex gap-1">
            <VoteChip label="H" value={log.voteHmm} />
            <VoteChip label="E" value={log.voteEma} />
            <VoteChip label="M" value={log.voteMomentum} />
          </div>
        </td>
        <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{log.hmmStateLabel ?? '—'}</td>
        <td className="py-1.5 px-2 mono" style={{ color: 'var(--text-muted)' }}>{log.atrValue != null ? log.atrValue.toFixed(3) : '—'}</td>
        <td className="py-1.5 px-2">
          {log.aiEnabled && log.llmConfidence != null && (
            <span className="text-xs" style={{ color: '#a78bfa' }}>{log.llmConfidence.toFixed(2)}</span>
          )}
          {log.aiEnabled && log.llmLatencyMs != null && (
            <span className="text-xs ml-1" style={{ color: 'var(--text-faint)' }}>{log.llmLatencyMs}ms</span>
          )}
          {!log.aiEnabled && <span style={{ color: 'var(--text-faint)' }}>—</span>}
        </td>
        <td className="py-1.5 px-2">
          <span className={`badge ${log.outcome === 'WIN' ? 'badge--buy' : log.outcome === 'LOSS' ? 'badge--sell' : 'badge--accent'}`}>
            {log.outcome ?? 'OPEN'}
          </span>
        </td>
        <td className="py-1.5 px-2 mono" style={{ color: outcomeColor }}>
          {log.profitUsd != null ? `${log.profitUsd >= 0 ? '+' : ''}$${log.profitUsd.toFixed(2)}` : '—'}
        </td>
        <td className="py-1.5 px-2" style={{ color: 'var(--text-faint)' }}>
          {new Date(log.openedAt).toLocaleTimeString()}
        </td>
      </tr>
      {expanded && log.llmReasoning && (
        <tr className="ai-reasoning-row">
          <td colSpan={11} className="px-3 py-2">
            <div className="ai-reasoning-block">
              <span className="font-semibold" style={{ color: '#a78bfa' }}>AI Reasoning: </span>
              {log.llmReasoning}
              {log.llmSkipReason && (
                <span className="ml-2" style={{ color: 'var(--warning)' }}>Skip: {log.llmSkipReason}</span>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Strategy Presets ─────────────────────────────────────────────────────────

const SMART_PRESETS = {
  A: {
    label: 'A — Selective',
    desc:  'High confidence, H1, RR 4:1 — fewer entries, higher quality',
    color: '#10B981',
    timeframe:       'H1',
    maxLayers:       '6',
    openPerInterval: '1',
    evalInterval:    '60',
    tpAtr:           '2.0',
    slAtr:           '0.5',
    minAtr:          '0.8',
    maxAtr:          '12',
    minConf:         '0.7',
    aiEnabled:       false,
    entriesPerDecision: '3',
    maxCallsPerHour: '4',
  },
  B: {
    label: 'B — Aggressive',
    desc:  'Fast eval, M15, open 3/interval — high frequency scalping',
    color: '#EF4444',
    timeframe:       'M15',
    maxLayers:       '10',
    openPerInterval: '3',
    evalInterval:    '15',
    tpAtr:           '1.0',
    slAtr:           '0.5',
    minAtr:          '0.3',
    maxAtr:          '20',
    minConf:         '0.4',
    aiEnabled:       false,
    entriesPerDecision: '5',
    maxCallsPerHour: '6',
  },
  C: {
    label: 'C — Balanced',
    desc:  'M15, RR 3:1, 2/interval — balanced risk and frequency',
    color: '#F59E0B',
    timeframe:       'M15',
    maxLayers:       '10',
    openPerInterval: '2',
    evalInterval:    '30',
    tpAtr:           '1.5',
    slAtr:           '0.5',
    minAtr:          '0.5',
    maxAtr:          '15',
    minConf:         '0.6',
    aiEnabled:       false,
    entriesPerDecision: '5',
    maxCallsPerHour: '6',
  },
  D: {
    label: 'D — AI Powered',
    desc:  'Claude AI decides: M15+H1 multi-TF, 5 entries/decision, 6 calls/hr',
    color: '#a78bfa',
    timeframe:       'M15',
    maxLayers:       '6',
    openPerInterval: '1',
    evalInterval:    '900',
    tpAtr:           '1.5',
    slAtr:           '0.5',
    minAtr:          '0.5',
    maxAtr:          '15',
    minConf:         '0.70',
    aiEnabled:       true,
    entriesPerDecision: '5',
    maxCallsPerHour: '6',
  },
} as const

type PresetKey = keyof typeof SMART_PRESETS

function TradingPanel() {
  // ── Tab ───────────────────────────────────────────────────────────────────
  const [engineTab, setEngineTab] = useState<'aggr' | 'cascade' | 'smart'>('aggr')

  // ── Aggressive state ──────────────────────────────────────────────────────
  const [aggrSymbol,           setAggrSymbol]           = useState('XAUUSDm')
  const [direction,            setDirection]            = useState('BUY')
  const [layers,               setLayers]               = useState('10')
  const [volume,               setVolume]               = useState('0.01')
  const [profitTarget,         setProfitTarget]         = useState('0.5')
  const [slPips,               setSlPips]               = useState('0')
  const [flipMode,             setFlipMode]             = useState('none')
  const [flipPercentile,       setFlipPercentile]       = useState('0.80')
  const [flipAfter,            setFlipAfter]            = useState('3')
  const [trendGuided,          setTrendGuided]          = useState(true)
  const [mcGuard,              setMcGuard]              = useState(false)
  const [mcLevelPct,           setMcLevelPct]           = useState('0.10')
  const [safetyMultiplier,     setSafetyMultiplier]     = useState('3.0')
  const [emergencyMultiplier,  setEmergencyMultiplier]  = useState('1.5')
  const [slLossMultiplier,     setSlLossMultiplier]     = useState('1.0')
  const [slCooldownSec,        setSlCooldownSec]        = useState('0')
  const [maxSessionLossUsd,    setMaxSessionLossUsd]    = useState('0')
  const [maxDrawdownFromPeak,  setMaxDrawdownFromPeak]  = useState('0')
  const [hmmGateEnabled,       setHmmGateEnabled]       = useState(false)
  const [hmmCooldownSec,       setHmmCooldownSec]       = useState('60')
  const [autoDirectionHmm,     setAutoDirectionHmm]     = useState(false)
  const [limitOrderEnabled,    setLimitOrderEnabled]    = useState(false)
  const [limitAtrMult,         setLimitAtrMult]         = useState('0.1')
  const [pendingExpirySec,     setPendingExpirySec]     = useState('15')
  const [aggrSessFilter,       setAggrSessFilter]       = useState<'all' | 'active'>('all')

  // ── Smart state ───────────────────────────────────────────────────────────
  const [symbol,          setSymbol]          = useState('XAUUSDm')
  const [timeframe,       setTimeframe]       = useState('M15')
  const [maxLayers,       setMaxLayers]       = useState('10')
  const [openPerInterval, setOpenPerInterval] = useState('1')
  const [evalInterval,    setEvalInterval]    = useState('30')
  const [smartVolume,     setSmartVolume]     = useState('0.01')
  const [tpAtr,           setTpAtr]           = useState('1.0')
  const [slAtr,           setSlAtr]           = useState('0.5')
  const [minAtr,          setMinAtr]          = useState('0.5')
  const [maxAtr,          setMaxAtr]          = useState('15')
  const [minConf,         setMinConf]         = useState('0.5')
  const [aiEnabled,          setAiEnabled]          = useState(false)
  const [entriesPerDecision, setEntriesPerDecision] = useState('5')
  const [maxCallsPerHour,    setMaxCallsPerHour]    = useState('6')
  const [allowShort,         setAllowShort]         = useState(false)
  const [smartSessFilter,    setSmartSessFilter]    = useState<'all' | 'active'>('all')
  const [showLogs,           setShowLogs]           = useState(false)
  const [expandedLog,        setExpandedLog]        = useState<string | null>(null)
  const [logSession,         setLogSession]         = useState<string | undefined>()
  const [activePreset,       setActivePreset]       = useState<PresetKey | null>(null)

  // ── Cascade state (merged) ────────────────────────────────────────────────
  const [csSymbol,     setCsSymbol]     = useState('XAUUSDm')
  const [csInitBatch,  setCsInitBatch]  = useState('10')
  const [csTopupBatch, setCsTopupBatch] = useState('5')
  const [csVolume,     setCsVolume]     = useState('0.01')
  const [csProfitTgt,  setCsProfitTgt]  = useState('2.0')
  const [csHardSl,       setCsHardSl]       = useState('0')
  const [csSlLossMult,   setCsSlLossMult]   = useState('1.0')
  const [csMaxPos,       setCsMaxPos]       = useState('30')
  const [csEvalSec,    setCsEvalSec]    = useState('300')
  const [csMcPct,      setCsMcPct]      = useState('10')
  const [csSafetyMult,      setCsSafetyMult]      = useState('3.0')
  const [csEmergMult,       setCsEmergMult]       = useState('1.5')
  const [csMaxLossUsd,      setCsMaxLossUsd]      = useState('0')
  const [csMaxDrawdown,     setCsMaxDrawdown]     = useState('0')
  const [csSessFilter, setCsSessFilter] = useState<'all' | 'active'>('all')

  function applyPreset(key: PresetKey) {
    const p = SMART_PRESETS[key]
    setTimeframe(p.timeframe)
    setMaxLayers(p.maxLayers)
    setOpenPerInterval(p.openPerInterval)
    setEvalInterval(p.evalInterval)
    setTpAtr(p.tpAtr)
    setSlAtr(p.slAtr)
    setMinAtr(p.minAtr)
    setMaxAtr(p.maxAtr)
    setMinConf(p.minConf)
    setAiEnabled(p.aiEnabled)
    setEntriesPerDecision(p.entriesPerDecision)
    setMaxCallsPerHour(p.maxCallsPerHour)
    setActivePreset(key)
  }

  // ── Aggressive queries/mutations ─────────────────────────────────────────
  const { data: aggrStatus, refetch: refetchAggr } = useQuery({
    queryKey: ['aggressive-status'],
    queryFn: api.aggressiveStatus,
    refetchInterval: 5_000,
    throwOnError: false,
    retry: false,
  })

  const aggrStartMut = useMutation({
    mutationFn: () => api.aggressiveStart({
      symbol: aggrSymbol, direction, layers: parseInt(layers), volume: parseFloat(volume),
      profitTarget: parseFloat(profitTarget), slPips: parseFloat(slPips), tpPips: 0,
      flipMode, flipPercentile: parseFloat(flipPercentile),
      flipAfter: parseInt(flipAfter), lookbackBars: 20,
      trendGuided,
      mcGuard, mcLevelPct: parseFloat(mcLevelPct),
      safetyMultiplier: parseFloat(safetyMultiplier),
      emergencyMultiplier: parseFloat(emergencyMultiplier),
      slLossMultiplier:    parseFloat(slLossMultiplier),
      slCooldownSec:       parseFloat(slCooldownSec),
      maxSessionLossUsd:   parseFloat(maxSessionLossUsd),
      maxDrawdownFromPeak: parseFloat(maxDrawdownFromPeak),
      hmmGateEnabled,
      hmmCooldownSec:      parseFloat(hmmCooldownSec),
      autoDirectionHmm,
      limitAtrMult:        limitOrderEnabled ? parseFloat(limitAtrMult) : 0.0,
      pendingExpirySec:    parseFloat(pendingExpirySec),
    }),
    onSuccess: () => refetchAggr(),
    onError: (err: Error) => {
      if (direction === 'AUTO' && err.message.includes('422')) {
        alert('AUTO direction: market masih neutral setelah 30s. Coba lagi atau gunakan BUY/SELL secara eksplisit.')
      }
    },
  })

  const aggrStopMut = useMutation({
    mutationFn: (id: string) => api.aggressiveStop(id),
    onSuccess: () => refetchAggr(),
  })

  const aggrStopAndCloseMut = useMutation({
    mutationFn: async (id: string) => {
      await api.aggressiveStop(id)
      await api.mt5CloseAll('all')
    },
    onSuccess: () => refetchAggr(),
  })

  // ── Smart queries/mutations ───────────────────────────────────────────────
  const { data: status, refetch } = useQuery({
    queryKey: ['smart-status'],
    queryFn: api.smartStatus,
    refetchInterval: 8_000,
    throwOnError: false,
    retry: false,
  })

  const { data: logsData = [] } = useQuery({
    queryKey: ['smart-logs', logSession],
    queryFn: () => api.smartLogs(logSession, undefined, 100),
    enabled: showLogs,
    refetchInterval: showLogs ? 10_000 : false,
    throwOnError: false,
    retry: false,
  })

  const startMut = useMutation({
    mutationFn: () => api.smartStart({
      symbol, timeframe,
      maxLayers:          parseInt(maxLayers),
      openPerInterval:    parseInt(openPerInterval),
      evalIntervalS:      parseInt(evalInterval),
      volume:             parseFloat(smartVolume),
      tpAtrMult:          parseFloat(tpAtr),
      slAtrMult:          parseFloat(slAtr),
      minAtr:             parseFloat(minAtr),
      maxAtr:             parseFloat(maxAtr),
      minConfidence:      parseFloat(minConf),
      allowShort,
      aiEnabled,
      entriesPerDecision: parseInt(entriesPerDecision),
      maxCallsPerHour:    parseInt(maxCallsPerHour),
    }),
    onSuccess: () => refetch(),
  })

  const stopMut = useMutation({
    mutationFn: (id: string) => api.smartStop(id),
    onSuccess: () => refetch(),
  })

  const resumeAiMut = useMutation({
    mutationFn: (id: string) => api.smartResumeAi(id),
    onSuccess: () => refetch(),
  })

  const { data: cascadeStatus, refetch: refetchCascade } = useQuery({
    queryKey: ['cascade-status'],
    queryFn:  api.cascadeStatus,
    refetchInterval: 5_000,
    throwOnError: false,
    retry: false,
  })
  const cascadeStartMut = useMutation({
    mutationFn: () => api.cascadeStart({
      symbol:              csSymbol,
      initialBatch:        parseInt(csInitBatch),
      topupBatch:          parseInt(csTopupBatch),
      volume:              parseFloat(csVolume),
      profitTarget:        parseFloat(csProfitTgt),
      hardSlPips:          parseFloat(csHardSl),
      slLossMultiplier:    parseFloat(csSlLossMult),
      maxPositions:        parseInt(csMaxPos),
      evalInterval:        parseInt(csEvalSec),
      mcLevelPct:          parseFloat(csMcPct) / 100,
      safetyMultiplier:    parseFloat(csSafetyMult),
      emergencyMultiplier: parseFloat(csEmergMult),
      maxSessionLossUsd:   parseFloat(csMaxLossUsd),
      maxDrawdownFromPeak: parseFloat(csMaxDrawdown),
    }),
    onSuccess: () => refetchCascade(),
  })
  const cascadeStopMut = useMutation({
    mutationFn: (id: string) => api.cascadeStop(id),
    onSuccess: () => refetchCascade(),
  })
  // ── Derived values ────────────────────────────────────────────────────────
  const aggrSessions    = aggrStatus?.sessions ?? []
  const aggrRunning     = aggrSessions.filter(s => s.active)
  const aggrDisplayed   = aggrSessFilter === 'active' ? aggrSessions.filter(s => s.active) : aggrSessions

  const sessions        = status?.sessions ?? []
  const running         = sessions.filter(s => s.active)

  const cascadeSessions  = cascadeStatus?.sessions ?? []
  const cascadeRunning   = cascadeSessions.filter(s => s.active).length
  const cascadeDisplayed = csSessFilter === 'active' ? cascadeSessions.filter(s => s.active) : cascadeSessions

  const anyRunning = aggrRunning.length > 0 || running.length > 0 || cascadeRunning > 0

  return (
    <div className="panel-card panel-card--smart flex flex-col">

      {/* ── Running Systems strip ── */}
      {anyRunning && (
        <div style={{
          padding: '5px 14px', background: 'var(--surface-2)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', flexWrap: 'wrap', gap: '5px', alignItems: 'center',
        }}>
          <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.06em', flexShrink: 0 }}>
            RUNNING:
          </span>
          {aggrRunning.map(s => (
            <span key={s.session_id} style={{
              fontSize: '10px', padding: '1px 7px', borderRadius: '4px',
              background: '#f59e0b18', border: '1px solid #f59e0b40', color: '#f59e0b',
            }}>
              AGGR {s.symbol} {s.direction} ×{s.layers} · {s.open_positions}pos
              {s.total_profit !== 0 && <span> · {s.total_profit >= 0 ? '+' : ''}${s.total_profit.toFixed(2)}</span>}
            </span>
          ))}
          {running.map(s => (
            <span key={s.session_id} style={{
              fontSize: '10px', padding: '1px 7px', borderRadius: '4px',
              background: '#a78bfa18', border: '1px solid #a78bfa40', color: '#a78bfa',
            }}>
              SMART {s.symbol} {s.timeframe} ×{s.max_layers} · {s.open_positions}pos
            </span>
          ))}
          {cascadeSessions.filter(s => s.active).map(s => (
            <span key={s.session_id} style={{
              fontSize: '10px', padding: '1px 7px', borderRadius: '4px',
              background: '#7c3aed18', border: '1px solid #7c3aed40', color: '#c4b5fd',
            }}>
              CASCADE {s.symbol} {s.current_direction} · {s.batches.reduce((a, b) => a + b.open, 0)}pos
            </span>
          ))}
        </div>
      )}

      {/* ── Tab header ── */}
      <div className="panel-header flex-shrink-0 flex-wrap gap-y-2">
        <span className={`inline-block ${anyRunning ? 'animate-pulse' : ''}`}
          style={{ width: 10, height: 10, borderRadius: '50%', background: aggrRunning.length > 0 ? 'var(--warning)' : running.length > 0 ? '#a78bfa' : cascadeRunning > 0 ? '#7c3aed' : 'var(--text-faint)', flexShrink: 0 }} />
        <div className="flex gap-1">
          <button onClick={() => setEngineTab('aggr')} style={{
            padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            background: engineTab === 'aggr' ? 'var(--warning)' : 'var(--surface-2)',
            color: engineTab === 'aggr' ? '#000' : 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            AGGR {aggrRunning.length > 0 && <span style={{ fontSize: '10px' }}>●{aggrRunning.length}</span>}
          </button>
          <button onClick={() => setEngineTab('cascade')} style={{
            padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            background: engineTab === 'cascade' ? '#7c3aed' : 'var(--surface-2)',
            color: engineTab === 'cascade' ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            Cascade {cascadeRunning > 0 && <span style={{ fontSize: '10px' }}>●{cascadeRunning}</span>}
          </button>
          <button onClick={() => setEngineTab('smart')} style={{
            padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            background: engineTab === 'smart' ? '#a78bfa' : 'var(--surface-2)',
            color: engineTab === 'smart' ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            Smart {running.length > 0 && <span style={{ fontSize: '10px' }}>●{running.length}</span>}
          </button>
        </div>
        <span className="badge badge--accent ml-auto" style={{ fontSize: '10px' }}>
          {engineTab === 'aggr' ? 'LAYER SCALPING' : engineTab === 'cascade' ? 'LAYERED CASCADE' : 'HMM + EMA + MOMENTUM'}
        </span>
      </div>

      {/* ── AGGR tab ── */}
      {engineTab === 'aggr' && (<>
        <div className="warning-banner" role="alert">
          ⚠ NO VALIDATION — THIS ENGINE PLACES LIVE MT5 ORDERS WITHOUT ADDITIONAL CONFIRMATION
        </div>
        <div className="panel-body flex-shrink-0">
          <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', letterSpacing: '0.6px', marginBottom: '5px' }}>CORE CONFIG</div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <SymbolSelect value={aggrSymbol} onChange={setAggrSymbol} />
            <select value={direction} onChange={e => setDirection(e.target.value)}
              className="rounded px-2 py-1 text-xs w-20"
              style={{
                background: 'var(--surface-2)', color: 'var(--text)',
                border: `1px solid ${direction === 'AUTO' ? 'var(--accent)' : 'var(--border)'}`,
              }}>
              <option>BUY</option><option>SELL</option><option>BOTH</option><option>AUTO</option>
            </select>
            {direction === 'AUTO' && (
              <span className="text-xs px-1.5 py-0.5 rounded" style={{
                background: 'var(--accent)20', color: 'var(--accent)',
                border: '1px solid var(--accent)', whiteSpace: 'nowrap',
              }}>
                M5+M15 vote
              </span>
            )}
            {direction === 'BOTH' && (
              <span className="text-xs px-1.5 py-0.5 rounded" style={{
                background: '#f59e0b20', color: '#f59e0b',
                border: '1px solid #f59e0b', whiteSpace: 'nowrap',
              }}
              title="BOTH membuka BUY dan SELL bersamaan. Net position = flat. Spread kena dua kali. Gunakan hanya untuk hedging sadar.">
                ⚠ hedge mode — spread ×2
              </span>
            )}
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Layers
              <input value={layers} onChange={e => setLayers(e.target.value)}
                type="number" min="1" max="50"
                className="rounded px-2 py-1.5 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Vol
              <input value={volume} onChange={e => setVolume(e.target.value)}
                type="number" min="0.01" step="0.01"
                className="rounded px-2 py-1.5 text-xs w-16"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Profit $
              <input value={profitTarget} onChange={e => setProfitTarget(e.target.value)}
                type="number" min="0.01" step="0.1"
                className="rounded px-2 py-1.5 text-xs w-16"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
            {/* sl_pips hidden — always 0, engine uses profit monitoring instead */}
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Flip
              <select value={flipMode} onChange={e => setFlipMode(e.target.value)}
                className="rounded px-2 py-1.5 text-xs w-24"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
                <option value="none">none</option>
                <option value="percentile">percentile</option>
                <option value="counter">counter</option>
                <option value="hybrid">hybrid</option>
              </select>
            </label>
            {(flipMode === 'percentile' || flipMode === 'hybrid') && (
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Pct
                <input value={flipPercentile} onChange={e => setFlipPercentile(e.target.value)}
                  type="number" min="0.5" max="1" step="0.05"
                  className="rounded px-2 py-1.5 text-xs w-16"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              </label>
            )}
            {(flipMode === 'counter' || flipMode === 'hybrid') && (
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                After
                <input value={flipAfter} onChange={e => setFlipAfter(e.target.value)}
                  type="number" min="1" max="20" step="1"
                  className="rounded px-2 py-1.5 text-xs w-14"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              </label>
            )}
          </div>

          <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', letterSpacing: '0.6px', marginTop: '10px', marginBottom: '5px' }}>RISK CONTROLS</div>
          <div className="flex items-center gap-2 flex-wrap">
            <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
              style={{ color: trendGuided ? 'var(--buy)' : 'var(--text-muted)' }}>
              <input type="checkbox" checked={trendGuided} onChange={e => setTrendGuided(e.target.checked)}
                className="w-3 h-3 accent-emerald-500" />
              Trend Guide
            </label>
            <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
              style={{ color: mcGuard ? 'var(--warning)' : 'var(--text-muted)' }}>
              <input type="checkbox" checked={mcGuard} onChange={e => setMcGuard(e.target.checked)}
                className="w-3 h-3 accent-amber-500" />
              MCGuard
            </label>
            {mcGuard && (<>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                MC%
                <input value={mcLevelPct} onChange={e => setMcLevelPct(e.target.value)}
                  type="number" min="0.01" max="0.5" step="0.01"
                  className="rounded px-2 py-1.5 text-xs w-16"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--warning)', color: 'var(--text)' }} />
              </label>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Safety×
                <input value={safetyMultiplier} onChange={e => setSafetyMultiplier(e.target.value)}
                  type="number" min="1" step="0.5"
                  className="rounded px-2 py-1.5 text-xs w-14"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              </label>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Emrg×
                <input value={emergencyMultiplier} onChange={e => setEmergencyMultiplier(e.target.value)}
                  type="number" min="1" step="0.5"
                  className="rounded px-2 py-1.5 text-xs w-14"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              </label>
            </>)}
            <label className="flex items-center gap-1 text-xs"
              style={{ color: parseFloat(slLossMultiplier) > 0 ? 'var(--sell)' : 'var(--text-muted)' }}>
              SL Loss×
              <input value={slLossMultiplier} onChange={e => setSlLossMultiplier(e.target.value)}
                type="number" min="0" step="0.5"
                title="Hard SL: close immediately when floating loss ≥ N × profit_target. 0 = disabled."
                className="rounded px-2 py-1.5 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: `1px solid ${parseFloat(slLossMultiplier) > 0 ? 'var(--sell)' : 'var(--border)'}`, color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs"
              style={{ color: parseFloat(slCooldownSec) > 0 ? 'var(--sell)' : 'var(--text-muted)' }}>
              SL Cooldown
              <input value={slCooldownSec} onChange={e => setSlCooldownSec(e.target.value)}
                type="number" min="0" step="10"
                title="SL Cooldown: wait N seconds after any SL event before reopening positions. Prevents revenge trading. 0 = disabled."
                className="rounded px-2 py-1.5 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: `1px solid ${parseFloat(slCooldownSec) > 0 ? 'var(--sell)' : 'var(--border)'}`, color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs"
              style={{ color: parseFloat(maxSessionLossUsd) > 0 ? 'var(--warning)' : 'var(--text-muted)' }}>
              Max Loss $
              <input value={maxSessionLossUsd} onChange={e => setMaxSessionLossUsd(e.target.value)}
                type="number" min="0" step="1"
                title="Profit Guard floor: stop session when net loss exceeds this amount. 0 = disabled."
                className="rounded px-2 py-1.5 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: `1px solid ${parseFloat(maxSessionLossUsd) > 0 ? 'var(--warning)' : 'var(--border)'}`, color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs"
              style={{ color: parseFloat(maxDrawdownFromPeak) > 0 ? 'var(--warning)' : 'var(--text-muted)' }}>
              Max DD $
              <input value={maxDrawdownFromPeak} onChange={e => setMaxDrawdownFromPeak(e.target.value)}
                type="number" min="0" step="1"
                title="Profit Guard drawdown: stop session when profit drops this much from peak. 0 = disabled."
                className="rounded px-2 py-1.5 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: `1px solid ${parseFloat(maxDrawdownFromPeak) > 0 ? 'var(--warning)' : 'var(--border)'}`, color: 'var(--text)' }} />
            </label>
          {/* HMM Gate section */}
          <div style={{ width: '100%', borderTop: '1px solid var(--border)', paddingTop: 8,
            display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ width: '100%', fontSize: '10px', fontWeight: 700, color: '#a78bfa80', letterSpacing: '0.6px', marginBottom: '2px' }}>HMM GATE</span>
            <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
              title="HMM Gate: sebelum buka posisi, cek kondisi bahaya dari analisa HMM M5+M15 (S/R trap, extreme momentum, divergence). Jika bahaya ditemukan → cooldown, tunggu vote HMM konfirmasi arah."
              style={{ color: hmmGateEnabled ? '#a78bfa' : 'var(--text-muted)', fontWeight: hmmGateEnabled ? 700 : 400 }}>
              <input type="checkbox" checked={hmmGateEnabled} onChange={e => setHmmGateEnabled(e.target.checked)}
                className="w-3 h-3" style={{ accentColor: '#a78bfa' }} />
              HMM Gate
            </label>
            {hmmGateEnabled && (
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Cooldown s
                <input value={hmmCooldownSec} onChange={e => setHmmCooldownSec(e.target.value)}
                  type="number" min="10" step="10"
                  title="Durasi cooldown (detik) saat HMM gate mendeteksi bahaya. Engine pause, lalu tunggu HMM vote konfirmasi sebelum reopen."
                  className="rounded px-2 py-1.5 text-xs w-14"
                  style={{ background: 'var(--surface-2)', border: '1px solid #a78bfa55', color: 'var(--text)' }} />
              </label>
            )}
            <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
              title="Auto Direction HMM: gunakan analisa HMM M5+M15 (bukan EMA) untuk menentukan arah BUY/SELL saat mode AUTO, dan update arah mid-session setelah setiap TP close."
              style={{ color: autoDirectionHmm ? '#a78bfa' : 'var(--text-muted)', fontWeight: autoDirectionHmm ? 700 : 400 }}>
              <input type="checkbox" checked={autoDirectionHmm} onChange={e => setAutoDirectionHmm(e.target.checked)}
                className="w-3 h-3" style={{ accentColor: '#a78bfa' }} />
              Auto Dir HMM
            </label>
          </div>
          {/* Limit Order section */}
          <div style={{ width: '100%', borderTop: '1px solid var(--border)', paddingTop: 8,
            display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ width: '100%', fontSize: '10px', fontWeight: 700, color: '#34d39980', letterSpacing: '0.6px', marginBottom: '2px' }}>ENTRY ORDERS</span>
            <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
              title="Limit Order: ganti market order dengan pending BUY_LIMIT/SELL_LIMIT di harga lebih rendah/tinggi dari harga saat ini (offset = ATR × mult). Hindari beli di pucuk / jual di bawah."
              style={{ color: limitOrderEnabled ? '#34d399' : 'var(--text-muted)', fontWeight: limitOrderEnabled ? 700 : 400 }}>
              <input type="checkbox" checked={limitOrderEnabled} onChange={e => setLimitOrderEnabled(e.target.checked)}
                className="w-3 h-3" style={{ accentColor: '#34d399' }} />
              Limit Order
            </label>
            {limitOrderEnabled && (<>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                ATR Mult
                <input value={limitAtrMult} onChange={e => setLimitAtrMult(e.target.value)}
                  type="number" min="0.01" max="1" step="0.01"
                  title="Offset limit dari harga pasar = ATR(M1,14) × mult. Contoh: 0.1 = 10% ATR di bawah ask (BUY) atau di atas bid (SELL)."
                  className="rounded px-2 py-1.5 text-xs w-16"
                  style={{ background: 'var(--surface-2)', border: '1px solid #34d39955', color: 'var(--text)' }} />
              </label>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Expiry s
                <input value={pendingExpirySec} onChange={e => setPendingExpirySec(e.target.value)}
                  type="number" min="5" max="300" step="5"
                  title="Batalkan pending order jika belum terisi dalam N detik. Default 15s — cocok untuk XAUUSD pasar cepat."
                  className="rounded px-2 py-1.5 text-xs w-14"
                  style={{ background: 'var(--surface-2)', border: '1px solid #34d39955', color: 'var(--text)' }} />
              </label>
            </>)}
          </div>
          <button
              type="button"
              onClick={() => {
                const sl = parseFloat(slLossMultiplier) || 0
                const pt = parseFloat(profitTarget) || 0
                const ly = parseInt(layers) || 1
                if (sl > 0 && pt > 0) {
                  const threshold = sl * pt
                  const loss = Math.round(ly * threshold * 1.5 * 100) / 100
                  const dd   = Math.round(loss * 0.5 * 100) / 100
                  setMaxSessionLossUsd(String(loss))
                  setMaxDrawdownFromPeak(String(dd))
                }
              }}
              title={`Calc Guard: Loss $ = layers × (SL× × profit_target) × 1.5 | DD $ = Loss $ × 0.5\nSL× must be > 0`}
              className="text-xs px-2 py-1.5 rounded"
              style={{ background: 'var(--surface-2)', color: 'var(--buy)', border: '1px solid var(--buy)', cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: 600 }}
            >
              Calc Guard
            </button>
            <button
              onClick={() => aggrStartMut.mutate()}
              disabled={aggrStartMut.isPending}
              className="btn-start btn-start--aggr"
              style={{ marginLeft: 'auto' }}
            >
              {aggrStartMut.isPending ? 'Starting…' : 'START AGGR'}
            </button>
          </div>
          {aggrStartMut.isError && (
            <div className="text-xs" style={{ color: 'var(--sell)' }}>{String(aggrStartMut.error)}</div>
          )}
        </div>

        <div style={{ padding: '8px 16px 12px', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: 'calc(100vh - 280px)', minHeight: 'calc(100vh - 334px)', overflowY: 'auto' }}>
          {aggrSessions.length > 0 && (
            <div className="flex gap-1 mb-1">
              {(['all', 'active'] as const).map(f => (
                <button key={f} onClick={() => setAggrSessFilter(f)}
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ background: aggrSessFilter === f ? 'var(--warning)' : 'var(--surface-2)', color: aggrSessFilter === f ? '#000' : 'var(--text-muted)', border: '1px solid var(--border)', fontWeight: aggrSessFilter === f ? 700 : 400 }}>
                  {f === 'all' ? 'All' : 'Active'}
                </button>
              ))}
            </div>
          )}
          {aggrDisplayed.length === 0 ? (
            <div className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
              {aggrSessions.length === 0 ? `Configure above and click START AGGR to open ${layers} concurrent positions.` : 'No active sessions.'}
            </div>
          ) : (
            [...aggrDisplayed].reverse().map(s => (
              <AggressiveSessionRow key={s.session_id} sess={s}
                onStop={id => aggrStopMut.mutate(id)}
                onStopAndClose={id => aggrStopAndCloseMut.mutate(id)} />
            ))
          )}
        </div>
      </>)}

      {/* ── SMART tab ── */}
      {engineTab === 'smart' && (
      <div className="panel-body flex-shrink-0">
        {/* ── Preset buttons ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {(Object.keys(SMART_PRESETS) as PresetKey[]).map(key => {
            const p = SMART_PRESETS[key]
            const isActive = activePreset === key
            return (
              <button
                key={key}
                onClick={() => applyPreset(key)}
                className={`preset-card ${isActive ? 'preset-card--active' : ''}`}
                style={isActive ? { '--preset-accent': p.color } as React.CSSProperties : undefined}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: p.color }} />
                  <span className="text-xs font-semibold" style={{ color: isActive ? p.color : 'var(--text)' }}>
                    {p.label}
                  </span>
                </div>
                <div className="text-xs leading-tight" style={{ color: 'var(--text-faint)', fontSize: '11px', lineHeight: '1.4' }}>{p.desc}</div>
                <div className="flex gap-2 mt-1.5 flex-wrap">
                  <span className="text-xs mono" style={{ color: 'var(--text-muted)' }}>{p.timeframe}</span>
                  <span className="text-xs mono" style={{ color: 'var(--text-muted)' }}>×{p.maxLayers}</span>
                  <span className="text-xs mono" style={{ color: 'var(--text-muted)' }}>{p.openPerInterval}/interval</span>
                  <span className="text-xs mono" style={{ color: 'var(--text-muted)' }}>TP×{p.tpAtr}</span>
                  <span className="text-xs mono" style={{ color: 'var(--text-muted)' }}>conf≥{p.minConf}</span>
                </div>
              </button>
            )
          })}
        </div>

        {/* Config row 1 */}
        <div className="flex items-center gap-2 flex-wrap">
          <SymbolSelect value={symbol} onChange={setSymbol} />
          <select value={timeframe} onChange={e => { setTimeframe(e.target.value); setActivePreset(null) }}
            className="rounded px-2 py-1.5 text-xs w-20"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
            {['M1','M5','M15','M30','H1','H4'].map(tf => <option key={tf}>{tf}</option>)}
          </select>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Max layers
            <input value={maxLayers} onChange={e => { setMaxLayers(e.target.value); setActivePreset(null) }}
              type="number" min="1" max="50"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Open/interval
            <input value={openPerInterval} onChange={e => { setOpenPerInterval(e.target.value); setActivePreset(null) }}
              type="number" min="1" max="10"
              className="rounded px-2 py-1 text-xs w-12"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Eval(s)
            <input value={evalInterval} onChange={e => { setEvalInterval(e.target.value); setActivePreset(null) }}
              type="number" min="5"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Vol
            <input value={smartVolume} onChange={e => setSmartVolume(e.target.value)}
              type="number" min="0.01" step="0.01"
              className="rounded px-2 py-1 text-xs w-16"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
        </div>

        {/* Config row 2 — ATR params */}
        <div className="flex items-center gap-2 flex-wrap">
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            TP×ATR
            <input value={tpAtr} onChange={e => { setTpAtr(e.target.value); setActivePreset(null) }}
              type="number" min="0.1" step="0.1"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            SL×ATR
            <input value={slAtr} onChange={e => { setSlAtr(e.target.value); setActivePreset(null) }}
              type="number" min="0.1" step="0.1"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Min ATR
            <input value={minAtr} onChange={e => { setMinAtr(e.target.value); setActivePreset(null) }}
              type="number" min="0" step="0.1"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Max ATR
            <input value={maxAtr} onChange={e => { setMaxAtr(e.target.value); setActivePreset(null) }}
              type="number" min="0.1" step="1"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Min conf
            <input value={minConf} onChange={e => { setMinConf(e.target.value); setActivePreset(null) }}
              type="number" min="0" max="1" step="0.05"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>

          {/* Short toggle */}
          <label className="flex items-center gap-1.5 cursor-pointer select-none"
            style={{ color: allowShort ? 'var(--sell)' : 'var(--text-muted)' }}>
            <input type="checkbox" checked={allowShort} onChange={e => { setAllowShort(e.target.checked); setActivePreset(null) }}
              className="w-3 h-3 accent-red-500" />
            <span className="text-xs font-semibold">Short</span>
          </label>

          {/* AI toggle */}
          <label className="flex items-center gap-1.5 cursor-pointer select-none ml-1">
            <div
              onClick={() => { setAiEnabled(v => !v); setActivePreset(null) }}
              className="relative w-9 h-5 rounded-full transition-colors cursor-pointer flex-shrink-0"
              style={{ background: aiEnabled ? '#a78bfa' : 'var(--surface-2)', border: '1px solid var(--border)' }}
            >
              <span className="absolute top-0.5 w-4 h-4 rounded-full transition-all"
                style={{ background: aiEnabled ? '#fff' : 'var(--text-faint)', left: aiEnabled ? '18px' : '2px' }} />
            </div>
            <span className="text-xs font-semibold" style={{ color: aiEnabled ? '#a78bfa' : 'var(--text-faint)' }}>
              AI
            </span>
          </label>

          {aiEnabled && (
            <>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Entries/decision
                <input value={entriesPerDecision} onChange={e => { setEntriesPerDecision(e.target.value); setActivePreset(null) }}
                  type="number" min="1" max="20"
                  className="rounded px-2 py-1 text-xs w-12"
                  style={{ background: 'var(--surface-2)', border: '1px solid #a78bfa40', color: 'var(--text)' }} />
              </label>
              <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Calls/hr
                <input value={maxCallsPerHour} onChange={e => { setMaxCallsPerHour(e.target.value); setActivePreset(null) }}
                  type="number" min="1" max="60"
                  className="rounded px-2 py-1 text-xs w-12"
                  style={{ background: 'var(--surface-2)', border: '1px solid #a78bfa40', color: 'var(--text)' }} />
              </label>
            </>
          )}

          <button
            onClick={() => startMut.mutate()}
            disabled={startMut.isPending}
            className={`btn-start ${aiEnabled ? 'btn-start--ai' : 'btn-start--smart'}`}
          >
            {startMut.isPending ? 'Starting…' : aiEnabled ? 'START AI' : 'START SMART'}
          </button>
          <button
            onClick={() => { setShowLogs(v => !v); setLogSession(undefined) }}
            className="px-3 py-1.5 rounded text-xs font-semibold"
            style={{ background: showLogs ? 'var(--surface-2)' : 'var(--bg)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
          >
            {showLogs ? 'Hide Logs' : 'Trade Logs'}
          </button>
        </div>

        {startMut.isError && (
          <div className="text-xs" style={{ color: 'var(--sell)' }}>{String(startMut.error)}</div>
        )}
      </div>
      )}{/* /engineTab === smart panel-body */}

      {/* ── CASCADE tab ── */}
      {engineTab === 'cascade' && (
        <div className="panel-body flex-shrink-0">
          <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-faint)', letterSpacing: '0.6px', marginBottom: '8px' }}>CASCADE CONFIG</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '6px' }}>
            {/* Symbol — uses dropdown instead of text input */}
            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '2px' }}>Symbol</div>
              <SymbolSelect value={csSymbol} onChange={setCsSymbol} />
            </div>
            {[
              { label: 'Init batch',   val: csInitBatch,  set: setCsInitBatch,  type: 'number' as const, min: 1 },
              { label: 'Topup batch',  val: csTopupBatch, set: setCsTopupBatch, type: 'number' as const, min: 1 },
              { label: 'Volume',       val: csVolume,     set: setCsVolume,     type: 'number' as const, step: 0.01 },
              { label: 'Profit tgt $', val: csProfitTgt,  set: setCsProfitTgt,  type: 'number' as const, step: 0.5 },
              { label: 'SL Loss×',     val: csSlLossMult, set: setCsSlLossMult, type: 'number' as const, step: 0.5 },
              { label: 'Max pos',      val: csMaxPos,     set: setCsMaxPos,     type: 'number' as const },
              { label: 'Eval (sec)',   val: csEvalSec,    set: setCsEvalSec,    type: 'number' as const },
              { label: 'MC level %',   val: csMcPct,      set: setCsMcPct,      type: 'number' as const },
              { label: 'Safety x',     val: csSafetyMult, set: setCsSafetyMult, type: 'number' as const, step: 0.5 },
              { label: 'Emergency x',  val: csEmergMult,  set: setCsEmergMult,  type: 'number' as const, step: 0.5 },
              { label: 'Loss floor $', val: csMaxLossUsd,  set: setCsMaxLossUsd,  type: 'number' as const, step: 1 },
              { label: 'Drawdown $',   val: csMaxDrawdown, set: setCsMaxDrawdown, type: 'number' as const, step: 1 },
            ].map(({ label, val, set, type, min, step }) => (
              <div key={label}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '2px' }}>{label}</div>
                <input
                  value={val} onChange={e => set(e.target.value)}
                  type={type} min={min} step={step}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)', padding: '4px 6px', fontSize: '12px', width: '100%' }}
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <button
              type="button"
              onClick={() => {
                const sl = parseFloat(csSlLossMult) || 0
                const pt = parseFloat(csProfitTgt) || 0
                const ly = parseInt(csMaxPos) || 1
                if (sl > 0 && pt > 0) {
                  const threshold = sl * pt
                  const loss = Math.round(ly * threshold * 1.5 * 100) / 100
                  const dd   = Math.round(loss * 0.5 * 100) / 100
                  setCsMaxLossUsd(String(loss))
                  setCsMaxDrawdown(String(dd))
                }
              }}
              title={`Calc Guard: Loss floor $ = max_pos × (SL× × profit_target) × 1.5 | Drawdown $ = Loss $ × 0.5\nSL× must be > 0`}
              style={{ padding: '5px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, background: 'var(--surface-2)', color: 'var(--buy)', border: '1px solid var(--buy)', cursor: 'pointer' }}
            >
              Calc Guard
            </button>
            <button
              onClick={() => cascadeStartMut.mutate()} disabled={cascadeStartMut.isPending}
              style={{
                marginLeft: 'auto', padding: '5px 16px', borderRadius: '6px', fontSize: '12px', fontWeight: 700,
                background: '#7c3aed', color: '#fff', border: 'none', cursor: 'pointer',
                opacity: cascadeStartMut.isPending ? 0.6 : 1,
              }}
            >
              {cascadeStartMut.isPending ? 'Starting…' : 'START CASCADE'}
            </button>
          </div>
          {cascadeStartMut.isError && (
            <div style={{ fontSize: '11px', color: 'var(--sell)', marginTop: '4px' }}>{String(cascadeStartMut.error)}</div>
          )}
        </div>
      )}

      {/* ── Smart sessions list ── */}
      {engineTab === 'smart' && !showLogs && (
        <div style={{ padding: '8px 16px 12px', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '300px', overflowY: 'auto' }}>
          {sessions.length > 0 && (
            <div className="flex gap-1 mb-1">
              {(['all', 'active'] as const).map(f => (
                <button key={f} onClick={() => setSmartSessFilter(f)}
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ background: smartSessFilter === f ? '#a78bfa' : 'var(--surface-2)', color: smartSessFilter === f ? '#fff' : 'var(--text-muted)', border: '1px solid var(--border)', fontWeight: smartSessFilter === f ? 700 : 400 }}>
                  {f === 'all' ? 'All' : 'Active'}
                </button>
              ))}
            </div>
          )}
          {sessions.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs"
              style={{ color: 'var(--text-muted)' }}>
              Configure above and click START SMART to begin auto-direction trading.
            </div>
          ) : (
            [...(smartSessFilter === 'active' ? sessions.filter(s => s.active) : sessions)].reverse().map(s => (
              <SmartSessionRow key={s.session_id} sess={s}
                onStop={id => stopMut.mutate(id)}
                onResumeAi={id => resumeAiMut.mutate(id)} />
            ))
          )}
        </div>
      )}

      {/* ── Trade log table ── */}
      {engineTab === 'smart' && showLogs && (
        <div className="overflow-auto p-3" style={{ maxHeight: '400px' }}>
          {sessions.length > 0 && (
            <div className="flex gap-2 mb-3 flex-wrap">
              <button
                onClick={() => setLogSession(undefined)}
                className="text-xs px-2 py-0.5 rounded"
                style={{ background: logSession == null ? '#a78bfa20' : 'var(--surface-2)', color: logSession == null ? '#a78bfa' : 'var(--text-muted)', border: '1px solid var(--border)' }}
              >
                All sessions
              </button>
              {[...sessions].reverse().map(s => (
                <button key={s.session_id}
                  onClick={() => setLogSession(s.session_id)}
                  className="text-xs px-2 py-0.5 rounded mono"
                  style={{ background: logSession === s.session_id ? '#a78bfa20' : 'var(--surface-2)', color: logSession === s.session_id ? '#a78bfa' : 'var(--text-muted)', border: '1px solid var(--border)' }}
                >
                  {s.session_id.slice(0, 8)} {s.symbol}
                </button>
              ))}
            </div>
          )}
          {logsData.length === 0 ? (
            <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No trade logs yet. Logs appear here as positions open and close.
            </div>
          ) : (
            <table className="trade-table">
              <thead>
                <tr>
                  <th>Dir</th>
                  <th>Entry</th>
                  <th>TP</th>
                  <th>SL</th>
                  <th>Votes</th>
                  <th>HMM State</th>
                  <th>ATR</th>
                  <th>AI conf</th>
                  <th>Outcome</th>
                  <th>P&amp;L</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {logsData.map(log => (
                  <SmartTradeLogRow
                    key={log.id} log={log}
                    expanded={expandedLog === log.id}
                    onToggle={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Cascade sessions list ── */}
      {engineTab === 'cascade' && (
        <div style={{ padding: '8px 16px 12px', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '300px', overflowY: 'auto' }}>
          {cascadeSessions.length > 0 && (
            <div className="flex gap-1 mb-1">
              {(['all', 'active'] as const).map(f => (
                <button key={f} onClick={() => setCsSessFilter(f)}
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ background: csSessFilter === f ? '#7c3aed' : 'var(--surface-2)', color: csSessFilter === f ? '#fff' : 'var(--text-muted)', border: '1px solid var(--border)', fontWeight: csSessFilter === f ? 700 : 400 }}>
                  {f === 'all' ? 'All' : 'Active'}
                </button>
              ))}
            </div>
          )}
          {cascadeDisplayed.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-faint)', textAlign: 'center', padding: '12px 0' }}>
              {cascadeSessions.length === 0 ? 'Configure above and click START CASCADE.' : 'No active sessions.'}
            </div>
          ) : (
            [...cascadeDisplayed].reverse().map(s => (
              <CascadeSessionRow key={s.session_id} sess={s} onStop={id => cascadeStopMut.mutate(id)} />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Cascade Engine Panel ──────────────────────────────────────────────────────

const MC_COLOR: Record<string, string> = {
  OK:        'var(--buy)',
  CAUTION:   '#f59e0b',
  WARNING:   '#f97316',
  DANGER:    'var(--sell)',
  EMERGENCY: '#7c3aed',
}

function CascadeSessionRow({ sess, onStop }: { sess: CascadeSession; onStop: (id: string) => void }) {
  const mcColor = MC_COLOR[sess.mc_status] ?? 'var(--text-muted)'
  const pColor  = sess.total_profit > 0 ? 'var(--buy)' : sess.total_profit < 0 ? 'var(--sell)' : 'var(--text-muted)'

  const totalOpen = sess.batches.reduce((s, b) => s + b.open, 0)
  const totalTp   = sess.batches.reduce((s, b) => s + b.closed_tp, 0)
  const totalSl   = sess.batches.reduce((s, b) => s + b.closed_sl, 0)

  return (
    <div style={{
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6,
    }}>

      {/* Row 1: identity + direction + MC + actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: sess.active ? 'var(--buy)' : 'var(--text-faint)',
            animation: sess.active ? 'pulse 2s infinite' : 'none',
          }} />
          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', whiteSpace: 'nowrap' }}>
            {sess.symbol}
          </span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap',
            background: sess.current_direction === 'BUY' ? '#10b98120' : '#ef444420',
            color: sess.current_direction === 'BUY' ? 'var(--buy)' : 'var(--sell)',
            border: `1px solid ${sess.current_direction === 'BUY' ? 'var(--buy)40' : 'var(--sell)40'}`,
          }}>{sess.current_direction}</span>
          <span style={{
            padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 700,
            border: `1px solid ${mcColor}40`, color: mcColor,
            background: `${mcColor}10`,
          }}>{sess.mc_status}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>
            Up {Math.floor(sess.uptime_s / 60)}m{sess.uptime_s % 60}s
          </span>
          {sess.active && (
            <button onClick={() => onStop(sess.session_id)} className="btn-stop">STOP</button>
          )}
        </div>
      </div>

      {/* Row 2: stats (left) + P&L (right) */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap', alignItems: 'center' }}>
          <span>
            <b style={{ color: 'var(--text)' }}>{totalOpen}</b>
            <span style={{ color: 'var(--text-faint)' }}>/{sess.max_positions}</span>
            {' '}open
          </span>
          <span>TP:<b style={{ color: 'var(--buy)' }}>{totalTp}</b></span>
          {totalSl > 0 && <span>SL:<b style={{ color: 'var(--sell)' }}>{totalSl}</b></span>}
          {sess.total_closed_emergency > 0 && (
            <span>EMG:<b style={{ color: '#7c3aed' }}>{sess.total_closed_emergency}</b></span>
          )}
          {/* Batch breakdown — inline chips */}
          {sess.batches.length > 0 && (
            <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {sess.batches.map(b => (
                <span key={b.batch_id} style={{
                  padding: '0 5px', borderRadius: 3, fontSize: 10,
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  color: b.direction === 'BUY' ? 'var(--buy)' : 'var(--sell)',
                }}>
                  {b.direction[0]}×{b.open}
                </span>
              ))}
            </span>
          )}
        </div>
        {/* Right: P&L block */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', color: pColor, lineHeight: 1.1 }}>
            {sess.total_profit >= 0 ? '+' : ''}${sess.total_profit.toFixed(2)}
          </div>
          {sess.floating_pnl !== 0 && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: sess.floating_pnl >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
              float {sess.floating_pnl >= 0 ? '+' : ''}${sess.floating_pnl.toFixed(2)}
            </div>
          )}
          {sess.peak_profit > 0 && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-faint)' }}>
              peak ${sess.peak_profit.toFixed(2)}
            </div>
          )}
          {(sess.total_net ?? 0) !== 0 && (sess.total_net ?? 0) !== sess.total_profit && (
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: (sess.total_net ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
              net {(sess.total_net ?? 0) >= 0 ? '+' : ''}${(sess.total_net ?? 0).toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* Row 3: last action / error */}
      <div style={{ fontSize: 11, color: sess.error ? 'var(--sell)' : 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {sess.error ? `ERR: ${sess.error}` : sess.last_action}
      </div>

      {/* Row 4: recommendation (stopped only) */}
      {!sess.active && sess.next_recommendation && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, marginTop: 2 }}>
          <span style={{ color: 'var(--text-muted)' }}>Next session:</span>
          <span style={{
            fontWeight: 700, padding: '1px 8px', borderRadius: 4,
            background: sess.next_recommendation === 'BUY'  ? '#10b98120' :
                        sess.next_recommendation === 'SELL' ? '#ef444420' : 'var(--surface)',
            color:      sess.next_recommendation === 'BUY'  ? 'var(--buy)'  :
                        sess.next_recommendation === 'SELL' ? 'var(--sell)' : 'var(--text-muted)',
            border: `1px solid ${sess.next_recommendation === 'BUY' ? 'var(--buy)' : sess.next_recommendation === 'SELL' ? 'var(--sell)' : 'var(--border)'}`,
          }}>{sess.next_recommendation}</span>
          <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>M5+M15 vote</span>
        </div>
      )}
    </div>
  )
}


// ── MT5 Terminal Panel ────────────────────────────────────────────────────────

function MT5TerminalPanel() {
  const [expandedTicket, setExpandedTicket] = useState<number | null>(null)

  const { data: positions = [], refetch } = useQuery({
    queryKey: ['mt5-positions'],
    queryFn: api.mt5Positions,
    refetchInterval: 3_000,
    throwOnError: false,
    retry: false,
  })

  const closeAllMut = useMutation({
    mutationFn: (filter: 'all' | 'profit' | 'loss') => api.mt5CloseAll(filter),
    onSuccess: () => refetch(),
  })

  const totalProfit = positions.reduce((s, p) => s + p.profit, 0)
  const profitCount = positions.filter(p => p.profit > 0).length
  const lossCount   = positions.filter(p => p.profit < 0).length
  const btnS: React.CSSProperties = { padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, cursor: 'pointer', border: '1px solid var(--border)' }

  return (
    <div className="panel-card flex flex-col" style={{ borderColor: 'var(--border)', minWidth: 0, width: '100%' }}>

      {/* ── Header ── */}
      <div className="panel-header flex-shrink-0 flex-wrap gap-y-2">
        <span className="panel-title">MT5 Terminal</span>
        <span className="badge badge--neutral ml-2">{positions.length} open</span>
        {positions.length > 0 && (
          <span className="mono ml-2" style={{ fontSize: 'clamp(10px, 1.1vw, 13px)', color: totalProfit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
            {totalProfit >= 0 ? '+' : ''}${totalProfit.toFixed(2)}
          </span>
        )}
        <div className="flex items-center gap-1.5 ml-auto flex-wrap">
          <button onClick={() => closeAllMut.mutate('profit')} disabled={closeAllMut.isPending || profitCount === 0}
            style={{ ...btnS, fontSize: 'clamp(9px, 1vw, 11px)', background: profitCount > 0 ? 'var(--buy)' : 'transparent', color: profitCount > 0 ? '#000' : 'var(--text-faint)', borderColor: profitCount > 0 ? 'var(--buy)' : 'var(--border)', opacity: profitCount === 0 ? 0.5 : 1 }}>
            +Profit ({profitCount})
          </button>
          <button onClick={() => closeAllMut.mutate('loss')} disabled={closeAllMut.isPending || lossCount === 0}
            style={{ ...btnS, fontSize: 'clamp(9px, 1vw, 11px)', background: lossCount > 0 ? 'var(--sell)' : 'transparent', color: lossCount > 0 ? '#fff' : 'var(--text-faint)', borderColor: lossCount > 0 ? 'var(--sell)' : 'var(--border)', opacity: lossCount === 0 ? 0.5 : 1 }}>
            -Loss ({lossCount})
          </button>
          <button onClick={() => closeAllMut.mutate('all')} disabled={closeAllMut.isPending || positions.length === 0}
            style={{ ...btnS, fontSize: 'clamp(9px, 1vw, 11px)', background: 'var(--surface-2)', color: positions.length > 0 ? 'var(--text)' : 'var(--text-faint)', opacity: positions.length === 0 ? 0.5 : 1 }}>
            Close All ({positions.length})
          </button>
        </div>
      </div>

      {closeAllMut.isError && (
        <div style={{ fontSize: 'clamp(10px, 1vw, 12px)', padding: '4px 16px', color: 'var(--sell)' }}>
          {String(closeAllMut.error)}
        </div>
      )}

      {/* ── Table ── */}
      {positions.length === 0 ? (
        <div style={{ padding: '14px 16px', color: 'var(--text-faint)', fontSize: 'clamp(11px, 1.1vw, 13px)', textAlign: 'center' }}>
          No open positions
        </div>
      ) : (
        <div style={{
          overflowX: 'auto',
          overflowY: 'auto',
          maxHeight: 'calc(100vh - 150px)',
          padding: '4px 0 8px',
          /* custom scrollbar agar tidak makan tempat */
          scrollbarWidth: 'thin',
          scrollbarColor: 'var(--border) transparent',
        }}>
          <table style={{
            borderCollapse: 'collapse',
            width: '100%',
            minWidth: '360px',          /* cegah tabel terlalu sempit */
            fontSize: 'clamp(10px, 1.1vw, 13px)',
            tableLayout: 'auto',
          }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 1, background: 'var(--surface)' }}>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ width: '1.2em', padding: 'clamp(3px,0.4vw,6px) 4px' }} />
                {['Symbol', 'Type', 'Vol', 'P&L'].map(h => (
                  <th key={h} style={{
                    padding: 'clamp(3px,0.4vw,6px) clamp(4px,0.6vw,10px)',
                    color: 'var(--text-muted)',
                    fontWeight: 600,
                    textAlign: ['Vol', 'P&L'].includes(h) ? 'right' : 'left',
                    whiteSpace: 'nowrap',
                    fontSize: 'clamp(9px, 1vw, 12px)',
                    letterSpacing: '0.03em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => {
                const isExp = expandedTicket === p.ticket
                const bg    = i % 2 === 0 ? 'transparent' : 'var(--surface-2)'
                const tdPad = 'clamp(4px,0.5vw,7px) clamp(4px,0.7vw,10px)'
                return (
                  <React.Fragment key={p.ticket}>
                    <tr
                      onClick={() => setExpandedTicket(isExp ? null : p.ticket)}
                      style={{ borderBottom: isExp ? 'none' : '1px solid var(--border)', background: bg, cursor: 'pointer', transition: 'background 0.15s' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-3, var(--surface-2))')}
                      onMouseLeave={e => (e.currentTarget.style.background = bg)}
                    >
                      <td style={{ padding: tdPad, color: 'var(--text-faint)', fontSize: '0.75em', textAlign: 'center', userSelect: 'none' }}>
                        {isExp ? '▼' : '▶'}
                      </td>
                      <td style={{ padding: tdPad, fontWeight: 700, color: 'var(--text)', whiteSpace: 'nowrap' }}>{p.symbol}</td>
                      <td style={{ padding: tdPad }}>
                        <span style={{
                          padding: '1px clamp(4px,0.5vw,7px)',
                          borderRadius: '4px',
                          fontSize: '0.85em',
                          fontWeight: 700,
                          background: p.type === 'BUY' ? '#10b98120' : '#ef444420',
                          color: p.type === 'BUY' ? 'var(--buy)' : 'var(--sell)',
                        }}>{p.type}</span>
                      </td>
                      <td style={{ padding: tdPad, fontFamily: 'monospace', color: 'var(--text)', textAlign: 'right', whiteSpace: 'nowrap' }}>{p.volume}</td>
                      <td style={{ padding: tdPad, fontFamily: 'monospace', fontWeight: 700, textAlign: 'right', whiteSpace: 'nowrap', color: p.profit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
                        {p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}
                      </td>
                    </tr>

                    {/* ── Expanded detail row ── */}
                    {isExp && (
                      <tr style={{ background: bg, borderBottom: '1px solid var(--border)' }}>
                        <td />
                        <td colSpan={4} style={{ padding: 'clamp(4px,0.5vw,8px) clamp(6px,0.8vw,12px) clamp(6px,0.8vw,10px)' }}>
                          <div style={{ display: 'flex', gap: 'clamp(8px,1.2vw,16px)', flexWrap: 'wrap', fontSize: 'clamp(9px, 0.95vw, 11px)', color: 'var(--text-muted)' }}>
                            <span>Ticket: <b style={{ color: 'var(--text-faint)', fontFamily: 'monospace' }}>{p.ticket}</b></span>
                            <span>Open: <b style={{ color: 'var(--text)', fontFamily: 'monospace' }}>{p.openPrice.toFixed(5)}</b></span>
                            {p.sl > 0 && <span>SL: <b style={{ color: 'var(--sell)', fontFamily: 'monospace' }}>{p.sl.toFixed(5)}</b></span>}
                            {p.tp > 0 && <span>TP: <b style={{ color: 'var(--buy)', fontFamily: 'monospace' }}>{p.tp.toFixed(5)}</b></span>}
                            {p.swap !== 0 && <span>Swap: <b style={{ color: 'var(--text-faint)', fontFamily: 'monospace' }}>{p.swap.toFixed(2)}</b></span>}
                            {p.comment && <span>Note: <b style={{ color: 'var(--text-faint)' }}>{p.comment}</b></span>}
                            <span>Time: <b style={{ color: 'var(--text-faint)' }}>{new Date(p.openTime).toLocaleTimeString()}</b></span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
            <tfoot style={{ position: 'sticky', bottom: 0, background: 'var(--surface)' }}>
              <tr style={{ borderTop: '2px solid var(--border)' }}>
                <td />
                <td colSpan={3} style={{ padding: 'clamp(4px,0.5vw,7px) clamp(4px,0.7vw,10px)', color: 'var(--text-muted)', fontSize: 'clamp(9px,1vw,11px)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  TOTAL FLOAT
                </td>
                <td style={{ padding: 'clamp(4px,0.5vw,7px) clamp(4px,0.7vw,10px)', fontFamily: 'monospace', fontWeight: 700, textAlign: 'right', whiteSpace: 'nowrap', color: totalProfit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
                  {totalProfit >= 0 ? '+' : ''}${totalProfit.toFixed(2)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Live() {
  const [isLogOpen,      setIsLogOpen]      = useState(true)
  const [logInstrument,  setLogInstrument]  = useState('XAUUSDm')

  // Deduplicated queries (React Query shares cache with TradingPanel queries)
  const { data: aggrStatus_   } = useQuery({ queryKey: ['aggressive-status'], queryFn: api.aggressiveStatus,  refetchInterval: 5_000, throwOnError: false, retry: false })
  const { data: smartStatus_  } = useQuery({ queryKey: ['smart-status'],      queryFn: api.smartStatus,       refetchInterval: 5_000, throwOnError: false, retry: false })
  const { data: cascadeStatus_} = useQuery({ queryKey: ['cascade-status'],    queryFn: api.cascadeStatus,     refetchInterval: 5_000, throwOnError: false, retry: false })

  const anyRunning = (
    (aggrStatus_?.sessions   ?? []).some((s: { active: boolean }) => s.active) ||
    (smartStatus_?.sessions  ?? []).some((s: { active: boolean }) => s.active) ||
    (cascadeStatus_?.sessions ?? []).some((s: { active: boolean }) => s.active)
  )

  const { logs, isPaused, setIsPaused, clearLogs } = useHmmAlertLog({
    instrument: logInstrument,
    enabled:    anyRunning,
  })

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 'clamp(10px, 2vw, 20px)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <h1 style={{ fontWeight: 700, color: 'var(--text)', fontSize: 'clamp(15px, 2.5vw, 20px)', letterSpacing: '-0.5px', margin: 0 }}>
          Live Trading
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HmmGlobalBadge />
          <div className="live-pill">
            <span className="live-pill__dot" />
            LIVE
          </div>
        </div>
      </div>

      {/* Main content — 3 columns: table 30% | trading 40% | log 30% */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isLogOpen
          ? 'minmax(0, 3fr) minmax(0, 4fr) minmax(0, 3fr)'
          : 'minmax(0, 3fr) minmax(0, 4fr) 36px',
        gap: '12px',
        alignItems: 'start',
        flex: 1,
        minHeight: 0,
      }}>
        <MT5TerminalPanel />
        <TradingPanel />

        {isLogOpen ? (
          <HmmAlertLog
            instrument={logInstrument}
            onInstrumentChange={setLogInstrument}
            enabled={anyRunning}
            logs={logs}
            isPaused={isPaused}
            onPause={() => setIsPaused(!isPaused)}
            onClear={clearLogs}
            onToggle={() => setIsLogOpen(false)}
          />
        ) : (
          <div
            onClick={() => setIsLogOpen(true)}
            title="Buka HMM Log"
            style={{
              cursor: 'pointer', display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 6,
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '16px 6px',
              transition: 'border-color 0.15s',
            }}
          >
            <span style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700, writingMode: 'vertical-rl', transform: 'rotate(180deg)', letterSpacing: 2 }}>
              HMM LOG
            </span>
            {anyRunning && !isPaused && (
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--buy)', display: 'inline-block' }} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}