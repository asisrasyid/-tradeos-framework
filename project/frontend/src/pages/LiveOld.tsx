import { useQuery, useMutation } from '@tanstack/react-query'
import { api, type AggressiveSession, type SmartSession, type SmartTradeLog, type CascadeSession } from '../lib/api'
import React, { useState } from 'react'

// ── Aggressive Engine Panel ───────────────────────────────────────────────────

function AggressiveSessionRow({ sess, onStop, onStopAndClose }: {
  sess: AggressiveSession
  onStop: (id: string) => void
  onStopAndClose: (id: string) => void
}) {
  const color  = sess.active ? 'var(--warning)' : 'var(--text-faint)'
  const profit = sess.total_profit ?? 0
  const pColor = profit > 0 ? 'var(--buy)' : profit < 0 ? 'var(--sell)' : 'var(--text-muted)'

  return (
    <div className="session-row session-row--warn">
      {/* Row 1: title + status + stop */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${sess.active ? 'animate-pulse' : ''}`}
            style={{ background: color }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {sess.symbol} · {sess.direction}
            {sess.current_direction && sess.current_direction !== sess.direction && (
              <span style={{ color: sess.current_direction === 'BUY' ? 'var(--buy)' : 'var(--sell)' }}>
                {' '}→{sess.current_direction}
              </span>
            )}
            {' '}· ×{sess.layers} layers · {sess.volume} lot
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* MCGuard status badge */}
          {sess.mc_guard && sess.mc_status && sess.mc_status !== 'OK' && (
            <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{
              background: sess.mc_status === 'EMERGENCY' ? 'var(--sell)' :
                          sess.mc_status === 'DANGER'    ? '#dc2626' :
                          sess.mc_status === 'WARNING'   ? 'var(--warning)' : 'var(--accent)',
              color: '#000',
            }}>
              MC:{sess.mc_status}
            </span>
          )}
          {/* Trend-guided indicator */}
          {sess.trend_guided && (
            <span className="text-xs px-1 py-0.5 rounded" style={{ background: 'var(--buy)20', color: 'var(--buy)', border: '1px solid var(--buy)' }}>
              TG
            </span>
          )}
          <span className={`badge ${sess.active ? 'badge--warn' : 'badge--neutral'}`}>
            {sess.active ? 'running' : 'stopped'}
          </span>
          {sess.active && (
            <>
              <button
                onClick={() => onStop(sess.session_id)}
                className="btn-stop"
              >
                STOP
              </button>
              <button
                onClick={() => onStopAndClose(sess.session_id)}
                className="btn-stop"
                style={{ background: 'var(--sell)', borderColor: 'var(--sell)' }}
              >
                SELL ALL
              </button>
            </>
          )}
        </div>
      </div>

      {/* Row 2: stats */}
      <div className="flex items-center gap-4 text-xs flex-wrap">
        <span style={{ color: 'var(--text-muted)' }}>
          Open: <span className="font-semibold" style={{ color: 'var(--text)' }}>{sess.open_positions}</span>
          <span style={{ color: 'var(--text-faint)' }}>/{sess.layers}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Wins: <span className="font-semibold" style={{ color: 'var(--buy)' }}>{sess.total_closed_win}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Other: <span style={{ color: 'var(--text)' }}>{sess.total_closed_other}</span>
        </span>
        {sess.total_closed_sl > 0 && (
          <span style={{ color: 'var(--text-muted)' }}>
            SL: <span style={{ color: 'var(--sell)' }}>{sess.total_closed_sl}</span>
          </span>
        )}
        <span style={{ color: 'var(--text-muted)' }}>
          Total profit: <span className="font-semibold mono" style={{ color: pColor }}>
            {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
          </span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Target: <span style={{ color: 'var(--text)' }}>${sess.profit_target}</span>
        </span>
        {sess.flip_mode && sess.flip_mode !== 'none' && (
          <span style={{ color: 'var(--text-muted)' }}>
            Flip: <span style={{ color: 'var(--text)' }}>{sess.flip_mode}</span>
            {sess.total_flips > 0 && (
              <span style={{ color: 'var(--buy)' }}> ×{sess.total_flips}</span>
            )}
            {sess.consecutive_tp > 0 && (
              <span style={{ color: 'var(--text-faint)' }}> ({sess.consecutive_tp} consec)</span>
            )}
          </span>
        )}
        <span style={{ color: 'var(--text-faint)' }}>
          Up {Math.floor(sess.uptime_s / 60)}m {sess.uptime_s % 60}s
        </span>
      </div>

      {/* Row 3: last action */}
      <div className="text-xs truncate" style={{ color: sess.error ? 'var(--sell)' : 'var(--text-faint)' }}>
        {sess.error ? `ERROR: ${sess.error}` : sess.last_action}
      </div>
    </div>
  )
}

function AggressivePanel() {
  const [symbol,               setSymbol]               = useState('XAUUSDc')
  const [direction,            setDirection]            = useState('BUY')
  const [layers,               setLayers]               = useState('10')
  const [volume,               setVolume]               = useState('0.01')
  const [profitTarget,         setProfitTarget]         = useState('0.5')
  const [slPips,               setSlPips]               = useState('0')
  const [flipMode,             setFlipMode]             = useState('none')
  const [flipPercentile,       setFlipPercentile]       = useState('0.80')
  const [flipAfter,            setFlipAfter]            = useState('3')
  const [trendGuided,          setTrendGuided]          = useState(false)
  const [mcGuard,              setMcGuard]              = useState(false)
  const [mcLevelPct,           setMcLevelPct]           = useState('0.10')
  const [safetyMultiplier,     setSafetyMultiplier]     = useState('3.0')
  const [emergencyMultiplier,  setEmergencyMultiplier]  = useState('1.5')
  const [slLossMultiplier,     setSlLossMultiplier]     = useState('0')
  const [sessFilter,           setSessFilter]           = useState<'all' | 'active'>('all')

  const { data: status, refetch } = useQuery({
    queryKey: ['aggressive-status'],
    queryFn: api.aggressiveStatus,
    refetchInterval: 5_000,
    throwOnError: false,
    retry: false,
  })

  const startMut = useMutation({
    mutationFn: () => api.aggressiveStart({
      symbol, direction, layers: parseInt(layers), volume: parseFloat(volume),
      profitTarget: parseFloat(profitTarget), slPips: parseFloat(slPips), tpPips: 0,
      flipMode, flipPercentile: parseFloat(flipPercentile),
      flipAfter: parseInt(flipAfter), lookbackBars: 20,
      trendGuided,
      mcGuard, mcLevelPct: parseFloat(mcLevelPct),
      safetyMultiplier: parseFloat(safetyMultiplier),
      emergencyMultiplier: parseFloat(emergencyMultiplier),
      slLossMultiplier: parseFloat(slLossMultiplier),
    }),
    onSuccess: () => refetch(),
  })

  const stopMut = useMutation({
    mutationFn: (id: string) => api.aggressiveStop(id),
    onSuccess: () => refetch(),
  })

  const stopAndCloseMut = useMutation({
    mutationFn: async (id: string) => {
      await api.aggressiveStop(id)
      await api.mt5CloseAll('all')
    },
    onSuccess: () => refetch(),
  })

  const sessions = status?.sessions ?? []
  const running  = sessions.filter(s => s.active)
  const displayedSessions = sessFilter === 'active' ? sessions.filter(s => s.active) : sessions

  return (
    <div className="panel-card panel-card--aggr flex flex-col">

      {/* ── Fixed header + config ── */}
      <div className="panel-header flex-shrink-0 flex-wrap gap-y-2">
        <span className={`inline-block ${running.length > 0 ? 'animate-pulse' : ''}`}
          style={{ width: 10, height: 10, borderRadius: '50%', background: running.length > 0 ? 'var(--warning)' : 'var(--text-faint)', flexShrink: 0 }} />
        <span className="panel-title">Aggressive Engine</span>
        {running.length > 0 && (
          <span className="badge badge--warn">
            {running.length} running · {sessions.filter(s => s.active).reduce((a, s) => a + s.open_positions, 0)} open positions
          </span>
        )}
        <span className="badge badge--accent ml-auto">HMM + MOMENTUM</span>
        <div className="flex gap-1 ml-2">
          <button
            onClick={() => setSessFilter('all')}
            className="text-xs px-2 py-0.5 rounded"
            style={{ background: sessFilter === 'all' ? 'var(--warning)' : 'var(--surface-2)', color: sessFilter === 'all' ? '#000' : 'var(--text-muted)', border: '1px solid var(--border)', fontWeight: sessFilter === 'all' ? 700 : 400 }}
          >
            All
          </button>
          <button
            onClick={() => setSessFilter('active')}
            className="text-xs px-2 py-0.5 rounded"
            style={{ background: sessFilter === 'active' ? 'var(--warning)' : 'var(--surface-2)', color: sessFilter === 'active' ? '#000' : 'var(--text-muted)', border: '1px solid var(--border)', fontWeight: sessFilter === 'active' ? 700 : 400 }}
          >
            Active
          </button>
        </div>
      </div>
      {/* ── Live orders warning banner ── */}
      <div className="warning-banner" role="alert">
        ⚠ NO VALIDATION — THIS ENGINE PLACES LIVE MT5 ORDERS WITHOUT ADDITIONAL CONFIRMATION
      </div>

      <div className="panel-body flex-shrink-0">
        {/* Config row */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <input value={symbol} onChange={e => setSymbol(e.target.value)}
            placeholder="Symbol" className="rounded px-2 py-1 text-xs w-24"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          <select value={direction} onChange={e => setDirection(e.target.value)}
            className="rounded px-2 py-1 text-xs w-20"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
            <option>BUY</option><option>SELL</option><option>BOTH</option>
          </select>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Layers
            <input value={layers} onChange={e => setLayers(e.target.value)}
              type="number" min="1" max="50"
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Vol
            <input value={volume} onChange={e => setVolume(e.target.value)}
              type="number" min="0.01" step="0.01"
              className="rounded px-2 py-1 text-xs w-16"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Profit $
            <input value={profitTarget} onChange={e => setProfitTarget(e.target.value)}
              type="number" min="0.01" step="0.1"
              className="rounded px-2 py-1 text-xs w-16"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            SL pips
            <input value={slPips} onChange={e => setSlPips(e.target.value)}
              type="number" min="0" step="1"
              className="rounded px-2 py-1 text-xs w-16"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
          </label>
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            Flip
            <select value={flipMode} onChange={e => setFlipMode(e.target.value)}
              className="rounded px-2 py-1 text-xs w-24"
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
                className="rounded px-2 py-1 text-xs w-16"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
          )}
          {(flipMode === 'counter' || flipMode === 'hybrid') && (
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              After
              <input value={flipAfter} onChange={e => setFlipAfter(e.target.value)}
                type="number" min="1" max="20" step="1"
                className="rounded px-2 py-1 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
          )}
        </div>

        {/* Row 2: Trend-Guided + MCGuard + Per-position SL */}
        <div className="flex items-center gap-2 flex-wrap" style={{ marginTop: '6px' }}>
          {/* Trend-Guided toggle */}
          <label className="flex items-center gap-1 text-xs cursor-pointer select-none"
            style={{ color: trendGuided ? 'var(--buy)' : 'var(--text-muted)' }}>
            <input type="checkbox" checked={trendGuided} onChange={e => setTrendGuided(e.target.checked)}
              className="w-3 h-3 accent-emerald-500" />
            Trend Guide (M1+M5)
          </label>

          {/* MCGuard toggle */}
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
                className="rounded px-2 py-1 text-xs w-16"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--warning)', color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Safety×
              <input value={safetyMultiplier} onChange={e => setSafetyMultiplier(e.target.value)}
                type="number" min="1" step="0.5"
                className="rounded px-2 py-1 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Emrg×
              <input value={emergencyMultiplier} onChange={e => setEmergencyMultiplier(e.target.value)}
                type="number" min="1" step="0.5"
                className="rounded px-2 py-1 text-xs w-14"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
            </label>
          </>)}

          {/* Per-position SL multiplier */}
          <label className="flex items-center gap-1 text-xs" style={{ color: parseFloat(slLossMultiplier) > 0 ? 'var(--sell)' : 'var(--text-muted)' }}>
            SL Loss×
            <input value={slLossMultiplier} onChange={e => setSlLossMultiplier(e.target.value)}
              type="number" min="0" step="0.5"
              title="Close position when floating loss > N × profit_target AND trend is against it. 0 = disabled."
              className="rounded px-2 py-1 text-xs w-14"
              style={{ background: 'var(--surface-2)', border: `1px solid ${parseFloat(slLossMultiplier) > 0 ? 'var(--sell)' : 'var(--border)'}`, color: 'var(--text)' }} />
          </label>

          <button
            onClick={() => startMut.mutate()}
            disabled={startMut.isPending}
            className="btn-start btn-start--aggr"
            style={{ marginLeft: 'auto' }}
          >
            {startMut.isPending ? 'Starting…' : 'START AGGR'}
          </button>
        </div>

        {startMut.isError && (
          <div className="text-xs" style={{ color: 'var(--sell)' }}>{String(startMut.error)}</div>
        )}
      </div>{/* /panel-body */}

      {/* ── Scrollable session list ── */}
      <div style={{ padding: '8px 16px 12px', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '320px', overflowY: 'auto' }}>
        {displayedSessions.length === 0 ? (
          <div className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
            {sessions.length === 0 ? `Configure above and click START AGGR to open ${layers} concurrent positions.` : 'No active sessions.'}
          </div>
        ) : (
          displayedSessions.map(s => (
            <AggressiveSessionRow key={s.session_id} sess={s}
              onStop={id => stopMut.mutate(id)}
              onStopAndClose={id => stopAndCloseMut.mutate(id)} />
          ))
        )}
      </div>
    </div>
  )
}

// ── Smart Aggressive Engine Panel ────────────────────────────────────────────

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
  const color  = isPaused ? 'var(--warning)' : sess.active ? '#a78bfa' : 'var(--text-faint)'
  const profit = sess.total_profit ?? 0
  const pColor = profit > 0 ? 'var(--buy)' : profit < 0 ? 'var(--sell)' : 'var(--text-muted)'

  return (
    <div className={`session-row ${isPaused ? 'session-row--warn' : sess.active ? 'session-row--smart' : 'session-row--stopped'}`}>

      {/* Row 1: title + badges + buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${sess.active && !isPaused ? 'animate-pulse' : ''}`}
            style={{ background: color }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {sess.symbol} · {sess.timeframe} · ×{sess.max_layers} · {sess.volume} lot
          </span>
          {sess.ai_enabled && (
            <span className="badge badge--ai">AI</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {sess.ai_enabled && (
            <span className="text-xs mono" style={{ color: 'var(--text-faint)' }}>
              {sess.ai_calls_this_hour}/{sess.max_calls_per_hour}/hr
            </span>
          )}
          <span className={`badge ${isPaused ? 'badge--warn' : sess.active ? 'badge--ai' : 'badge--neutral'}`}>
            {isPaused ? 'AI PAUSED' : sess.active ? 'running' : 'stopped'}
          </span>
          {isPaused && (
            <button onClick={() => onResumeAi(sess.session_id)}
              className="px-2 py-1 rounded text-xs font-semibold"
              style={{ background: 'var(--warn-bg)', color: 'var(--warning)', border: '1px solid var(--warn-bg)' }}>
              RESUME AI
            </button>
          )}
          {sess.active && (
            <button onClick={() => onStop(sess.session_id)}
              className="btn-stop">
              STOP
            </button>
          )}
        </div>
      </div>

      {/* Row 2: stats */}
      <div className="flex items-center gap-4 text-xs flex-wrap">
        <span style={{ color: 'var(--text-muted)' }}>
          Open: <span className="font-semibold" style={{ color: 'var(--text)' }}>{sess.open_positions}</span>
          <span style={{ color: 'var(--text-faint)' }}>/{sess.max_layers}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Opened: <span style={{ color: 'var(--text)' }}>{sess.total_opened}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          W/<span style={{ color: 'var(--buy)' }}>{sess.total_closed_win}</span>
          {' '}L/<span style={{ color: 'var(--sell)' }}>{sess.total_closed_loss}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Profit: <span className="font-semibold mono" style={{ color: pColor }}>
            {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
          </span>
        </span>
        {sess.ai_enabled
          ? <span style={{ color: 'var(--text-muted)' }}>
              Entries/decision: <span style={{ color: 'var(--text)' }}>{sess.entries_per_decision}</span>
            </span>
          : <span style={{ color: 'var(--text-muted)' }}>
              TP/SL ATR×<span style={{ color: 'var(--text)' }}>{sess.tp_atr_mult}/{sess.sl_atr_mult}</span>
            </span>
        }
        <span style={{ color: 'var(--text-faint)' }}>
          Up {Math.floor(sess.uptime_s / 60)}m {sess.uptime_s % 60}s
        </span>
      </div>

      {/* Row 3: last action */}
      <div className="text-xs truncate" style={{ color: sess.error ? 'var(--sell)' : 'var(--text-faint)' }}>
        {sess.error ? `ERROR: ${sess.error}` : sess.last_action}
      </div>

      {/* Row 4: AI last reasoning (only if AI enabled and has reasoning) */}
      {sess.ai_enabled && sess.ai_last_reasoning && (
        <div className="text-xs rounded px-2 py-1.5 leading-relaxed"
          style={{ background: '#a78bfa08', border: '1px solid #a78bfa20', color: 'var(--text-muted)' }}>
          <span className="font-semibold" style={{ color: '#a78bfa' }}>AI: </span>
          {sess.ai_last_decision && (
            <span className="font-semibold mr-1"
              style={{ color: sess.ai_last_decision === 'BUY' ? 'var(--buy)' : sess.ai_last_decision === 'SELL' ? 'var(--sell)' : 'var(--text-faint)' }}>
              {sess.ai_last_decision}
            </span>
          )}
          {sess.ai_last_confidence > 0 && (
            <span className="mr-1" style={{ color: 'var(--text-faint)' }}>
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

function SmartAggressivePanel() {
  // ── Tab ───────────────────────────────────────────────────────────────────
  const [engineTab, setEngineTab] = useState<'smart' | 'cascade'>('smart')

  // ── Smart state ───────────────────────────────────────────────────────────
  const [symbol,          setSymbol]          = useState('XAUUSDc')
  const [timeframe,       setTimeframe]       = useState('M15')
  const [maxLayers,       setMaxLayers]       = useState('10')
  const [openPerInterval, setOpenPerInterval] = useState('1')
  const [evalInterval,    setEvalInterval]    = useState('30')
  const [volume,          setVolume]          = useState('0.01')
  const [tpAtr,           setTpAtr]           = useState('1.0')
  const [slAtr,           setSlAtr]           = useState('0.5')
  const [minAtr,          setMinAtr]          = useState('0.5')
  const [maxAtr,          setMaxAtr]          = useState('15')
  const [minConf,         setMinConf]         = useState('0.5')
  const [aiEnabled,          setAiEnabled]          = useState(false)
  const [entriesPerDecision, setEntriesPerDecision] = useState('5')
  const [maxCallsPerHour,    setMaxCallsPerHour]    = useState('6')
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
  const [csHardSl,     setCsHardSl]     = useState('30')
  const [csMaxPos,     setCsMaxPos]     = useState('30')
  const [csEvalSec,    setCsEvalSec]    = useState('300')
  const [csMcPct,      setCsMcPct]      = useState('10')
  const [csSafetyMult, setCsSafetyMult] = useState('3.0')
  const [csEmergMult,  setCsEmergMult]  = useState('1.5')
  const [csSessFilter, setCsSessFilter] = useState<'all' | 'active'>('all')
  const [engineTab,          setEngineTab]          = useState<'smart' | 'cascade'>('smart')

  // Cascade state (merged)
  const [csSymbol,     setCsSymbol]     = useState('XAUUSDm')
  const [csInitBatch,  setCsInitBatch]  = useState('10')
  const [csTopupBatch, setCsTopupBatch] = useState('5')
  const [csVolume,     setCsVolume]     = useState('0.01')
  const [csProfitTgt,  setCsProfitTgt]  = useState('2.0')
  const [csHardSl,     setCsHardSl]     = useState('30')
  const [csMaxPos,     setCsMaxPos]     = useState('30')
  const [csEvalSec,    setCsEvalSec]    = useState('300')
  const [csMcPct,      setCsMcPct]      = useState('10')
  const [csSafetyMult, setCsSafetyMult] = useState('3.0')
  const [csEmergMult,  setCsEmergMult]  = useState('1.5')
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
      volume:             parseFloat(volume),
      tpAtrMult:          parseFloat(tpAtr),
      slAtrMult:          parseFloat(slAtr),
      minAtr:             parseFloat(minAtr),
      maxAtr:             parseFloat(maxAtr),
      minConfidence:      parseFloat(minConf),
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
      maxPositions:        parseInt(csMaxPos),
      evalInterval:        parseInt(csEvalSec),
      mcLevelPct:          parseFloat(csMcPct) / 100,
      safetyMultiplier:    parseFloat(csSafetyMult),
      emergencyMultiplier: parseFloat(csEmergMult),
    }),
    onSuccess: () => refetchCascade(),
  })
  const cascadeStopMut = useMutation({
    mutationFn: (id: string) => api.cascadeStop(id),
    onSuccess: () => refetchCascade(),
  })
  const cascadeSessions  = cascadeStatus?.sessions ?? []
  const cascadeRunning   = cascadeSessions.filter(s => s.active).length
  const cascadeDisplayed = csSessFilter === 'active' ? cascadeSessions.filter(s => s.active) : cascadeSessions

  const sessions = status?.sessions ?? []
  const running  = sessions.filter(s => s.active)

  return (
    <div className="panel-card panel-card--smart flex flex-col">

      {/* ── Fixed header with tab switcher ── */}
      <div className="panel-header flex-shrink-0 flex-wrap gap-y-2">
        <span className={`inline-block ${(running.length > 0 || cascadeRunning > 0) ? 'animate-pulse' : ''}`}
          style={{ width: 10, height: 10, borderRadius: '50%', background: running.length > 0 ? '#a78bfa' : cascadeRunning > 0 ? '#7c3aed' : 'var(--text-faint)', flexShrink: 0 }} />
        {/* Tab buttons */}
        <div className="flex gap-1">
          <button onClick={() => setEngineTab('smart')} style={{
            padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            background: engineTab === 'smart' ? '#a78bfa' : 'var(--surface-2)',
            color: engineTab === 'smart' ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            Smart {running.length > 0 && <span style={{ fontSize: '10px' }}>●{running.length}</span>}
          </button>
          <button onClick={() => setEngineTab('cascade')} style={{
            padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            background: engineTab === 'cascade' ? '#7c3aed' : 'var(--surface-2)',
            color: engineTab === 'cascade' ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            Cascade {cascadeRunning > 0 && <span style={{ fontSize: '10px' }}>●{cascadeRunning}</span>}
          </button>
        </div>
        <span className="badge badge--accent ml-auto" style={{ fontSize: '10px' }}>
          {engineTab === 'smart' ? 'HMM + EMA + MOMENTUM' : 'LAYERED CASCADE'}
        </span>
      </div>

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
          <input value={symbol} onChange={e => setSymbol(e.target.value)}
            placeholder="Symbol" className="rounded px-2 py-1.5 text-xs w-24"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }} />
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
            <input value={volume} onChange={e => setVolume(e.target.value)}
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

      {engineTab === 'cascade' && (
        <div className="panel-body flex-shrink-0">
          {/* Cascade config grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '6px' }}>
            {[
              { label: 'Symbol',       val: csSymbol,     set: setCsSymbol,     type: 'text' },
              { label: 'Init batch',   val: csInitBatch,  set: setCsInitBatch,  type: 'number', min: 1 },
              { label: 'Topup batch',  val: csTopupBatch, set: setCsTopupBatch, type: 'number', min: 1 },
              { label: 'Volume',       val: csVolume,     set: setCsVolume,     type: 'number', step: 0.01 },
              { label: 'Profit tgt $', val: csProfitTgt,  set: setCsProfitTgt,  type: 'number', step: 0.5 },
              { label: 'Hard SL pips', val: csHardSl,     set: setCsHardSl,     type: 'number' },
              { label: 'Max pos',      val: csMaxPos,     set: setCsMaxPos,     type: 'number' },
              { label: 'Eval (sec)',   val: csEvalSec,    set: setCsEvalSec,    type: 'number' },
              { label: 'MC level %',   val: csMcPct,      set: setCsMcPct,      type: 'number' },
              { label: 'Safety x',     val: csSafetyMult, set: setCsSafetyMult, type: 'number', step: 0.5 },
              { label: 'Emergency x',  val: csEmergMult,  set: setCsEmergMult,  type: 'number', step: 0.5 },
            ].map(({ label, val, set, type, min, step }: any) => (
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
            <div className="flex gap-1">
              {(['all', 'active'] as const).map(f => (
                <button key={f} onClick={() => setCsSessFilter(f)} style={{
                  padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: csSessFilter === f ? 700 : 400,
                  background: csSessFilter === f ? '#7c3aed' : 'var(--surface-2)',
                  color: csSessFilter === f ? '#fff' : 'var(--text-muted)',
                  border: '1px solid var(--border)', cursor: 'pointer',
                }}>{f === 'all' ? 'All' : 'Active'}</button>
              ))}
            </div>
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
          {sessions.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs"
              style={{ color: 'var(--text-muted)' }}>
              Configure above and click START SMART to begin auto-direction trading.
            </div>
          ) : (
            sessions.map(s => (
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
              {sessions.map(s => (
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
          {cascadeDisplayed.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-faint)', textAlign: 'center', padding: '12px 0' }}>
              {cascadeSessions.length === 0 ? 'Configure above and click START CASCADE.' : 'No active sessions.'}
            </div>
          ) : (
            cascadeDisplayed.map(s => (
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

  const totalOpen  = sess.batches.reduce((s, b) => s + b.open, 0)
  const totalTp    = sess.batches.reduce((s, b) => s + b.closed_tp, 0)
  const totalSl    = sess.batches.reduce((s, b) => s + b.closed_sl, 0)

  return (
    <div style={{
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      borderRadius: '8px', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: '6px',
    }}>
      {/* Row 1: symbol + direction + status + stop */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: sess.active ? 'var(--buy)' : 'var(--text-faint)',
            animation: sess.active ? 'pulse 2s infinite' : 'none',
          }} />
          <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text)' }}>
            {sess.symbol}
          </span>
          <span style={{
            padding: '1px 7px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
            background: sess.current_direction === 'BUY' ? 'var(--buy-bg,#10b98120)' : 'var(--sell-bg,#ef444420)',
            color: sess.current_direction === 'BUY' ? 'var(--buy)' : 'var(--sell)',
          }}>{sess.current_direction}</span>

          {/* MCGuard badge */}
          <span style={{
            padding: '1px 7px', borderRadius: '4px', fontSize: '10px', fontWeight: 700,
            border: `1px solid ${mcColor}`, color: mcColor,
          }}>
            {sess.mc_status}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {Math.floor(sess.uptime_s / 60)}m {sess.uptime_s % 60}s
          </span>
          {sess.active && (
            <button onClick={() => onStop(sess.session_id)}
              style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
                background: 'transparent', border: '1px solid var(--sell)', color: 'var(--sell)', cursor: 'pointer' }}>
              STOP
            </button>
          )}
        </div>
      </div>

      {/* Row 2: stats */}
      <div style={{ display: 'flex', gap: '14px', fontSize: '11px', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--text-muted)' }}>Open <b style={{ color: 'var(--text)' }}>{totalOpen}</b>/{sess.max_positions}</span>
        <span style={{ color: 'var(--text-muted)' }}>TP <b style={{ color: 'var(--buy)' }}>{totalTp}</b></span>
        <span style={{ color: 'var(--text-muted)' }}>SL <b style={{ color: 'var(--sell)' }}>{totalSl}</b></span>
        {sess.total_closed_emergency > 0 && (
          <span style={{ color: '#7c3aed' }}>EMG <b>{sess.total_closed_emergency}</b></span>
        )}
        <span style={{ color: pColor, fontWeight: 700 }}>
          {sess.total_profit >= 0 ? '+' : ''}${sess.total_profit.toFixed(2)}
        </span>
      </div>

      {/* Row 3: batch breakdown */}
      {sess.batches.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {sess.batches.map(b => (
            <span key={b.batch_id} style={{
              padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: b.direction === 'BUY' ? 'var(--buy)' : 'var(--sell)',
            }}>
              {b.direction} ×{b.open}
            </span>
          ))}
        </div>
      )}

      {/* Row 4: last action */}
      <div style={{ fontSize: '11px', color: sess.error ? 'var(--sell)' : 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {sess.error ? `ERR: ${sess.error}` : sess.last_action}
      </div>
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
    <div className="panel-card flex flex-col" style={{ borderColor: 'var(--border)' }}>
      <div className="panel-header flex-shrink-0 flex-wrap gap-y-2">
        <span className="panel-title">MT5 Terminal</span>
        <span className="badge badge--neutral ml-2">{positions.length} open</span>
        {positions.length > 0 && (
          <span className="mono text-xs ml-2" style={{ color: totalProfit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
            {totalProfit >= 0 ? '+' : ''}${totalProfit.toFixed(2)}
          </span>
        )}
        <div className="flex items-center gap-1.5 ml-auto flex-wrap">
          <button onClick={() => closeAllMut.mutate('profit')} disabled={closeAllMut.isPending || profitCount === 0}
            style={{ ...btnS, background: profitCount > 0 ? 'var(--buy)' : 'transparent', color: profitCount > 0 ? '#000' : 'var(--text-faint)', borderColor: profitCount > 0 ? 'var(--buy)' : 'var(--border)', opacity: profitCount === 0 ? 0.5 : 1 }}>
            +Profit ({profitCount})
          </button>
          <button onClick={() => closeAllMut.mutate('loss')} disabled={closeAllMut.isPending || lossCount === 0}
            style={{ ...btnS, background: lossCount > 0 ? 'var(--sell)' : 'transparent', color: lossCount > 0 ? '#fff' : 'var(--text-faint)', borderColor: lossCount > 0 ? 'var(--sell)' : 'var(--border)', opacity: lossCount === 0 ? 0.5 : 1 }}>
            -Loss ({lossCount})
          </button>
          <button onClick={() => closeAllMut.mutate('all')} disabled={closeAllMut.isPending || positions.length === 0}
            style={{ ...btnS, background: 'var(--surface-2)', color: positions.length > 0 ? 'var(--text)' : 'var(--text-faint)', opacity: positions.length === 0 ? 0.5 : 1 }}>
            Close All ({positions.length})
          </button>
        </div>
      </div>

      {closeAllMut.isError && <div className="text-xs px-4 pb-2" style={{ color: 'var(--sell)' }}>{String(closeAllMut.error)}</div>}

      {positions.length === 0 ? (
        <div style={{ padding: '14px 16px', color: 'var(--text-faint)', fontSize: '12px', textAlign: 'center' }}>No open positions</div>
      ) : (
        <div style={{ overflowX: 'auto', padding: '4px 16px 12px' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ width: '18px', padding: '5px 4px' }} />
                {['Symbol', 'Type', 'Vol', 'P&L'].map(h => (
                  <th key={h} style={{ padding: '5px 8px', color: 'var(--text-muted)', fontWeight: 600, textAlign: h === 'Vol' || h === 'P&L' ? 'right' : 'left', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => {
                const isExp = expandedTicket === p.ticket
                const bg    = i % 2 === 0 ? 'transparent' : 'var(--surface-2)'
                return (
                  <React.Fragment key={p.ticket}>
                    <tr onClick={() => setExpandedTicket(isExp ? null : p.ticket)}
                      style={{ borderBottom: isExp ? 'none' : '1px solid var(--border)', background: bg, cursor: 'pointer' }}>
                      <td style={{ padding: '6px 4px', color: 'var(--text-faint)', fontSize: '10px', textAlign: 'center', userSelect: 'none' }}>
                        {isExp ? '▼' : '▶'}
                      </td>
                      <td style={{ padding: '6px 8px', fontWeight: 600, color: 'var(--text)' }}>{p.symbol}</td>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{ padding: '1px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, background: p.type === 'BUY' ? '#10b98120' : '#ef444420', color: p.type === 'BUY' ? 'var(--buy)' : 'var(--sell)' }}>{p.type}</span>
                      </td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', color: 'var(--text)', textAlign: 'right' }}>{p.volume}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontWeight: 700, textAlign: 'right', color: p.profit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
                        {p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}
                      </td>
                    </tr>
                    {isExp && (
                      <tr style={{ background: bg, borderBottom: '1px solid var(--border)' }}>
                        <td />
                        <td colSpan={4} style={{ padding: '3px 8px 8px' }}>
                          <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '11px', color: 'var(--text-muted)' }}>
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
            <tfoot>
              <tr style={{ borderTop: '2px solid var(--border)' }}>
                <td /><td colSpan={3} style={{ padding: '6px 8px', color: 'var(--text-muted)', fontSize: '11px', fontWeight: 600 }}>TOTAL FLOAT</td>
                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontWeight: 700, textAlign: 'right', color: totalProfit >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
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
  const qc = useQueryClient()
  const { data: signals = [], isLoading } = useQuery({
    queryKey: ['live-signals'],
    queryFn: api.getLiveSignals,
    refetchInterval: 30_000,
  })

  useEffect(() => {
    startSignalR().then(() => {
      const conn = getSignalRConnection()
      conn.on('NewSignal', () => {
        qc.invalidateQueries({ queryKey: ['live-signals'] })
      })
    })
  }, [qc])

  return (
    <div style={{ overflowY: 'auto', padding: 'clamp(14px, 2vw, 24px)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 style={{ fontWeight: 700, color: 'var(--text)', fontSize: 'clamp(16px, 2.5vw, 20px)', letterSpacing: '-0.5px' }}>
          Live Trading
        </h1>
        <div className="live-pill">
          <span className="live-pill__dot" />
          LIVE
        </div>
      </div>

      {/* Main 2-column grid: left=MT5 Terminal, right=engines */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '16px', alignItems: 'start' }}>
        {/* Left: MT5 Terminal */}
        <MT5TerminalPanel />

        {/* Right: engines stacked */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <EnginePanel />
          <AggressivePanel />
          <CascadePanel />
          <SmartAggressivePanel />
        </div>
      </div>

      {/* Signal cards - below the grid, full width */}
      {isLoading && (
        <div className="flex items-center gap-2" style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
          <span className="spinner spinner--sm spinner--buy" />
          Loading signals…
        </div>
      )}
      {!isLoading && signals.length === 0 && (
        <div className="empty-state" style={{ padding: '24px' }}>
          <div style={{ fontSize: '28px', opacity: 0.4 }}>📡</div>
          <div style={{ fontWeight: 600 }}>No active signals</div>
          <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>Start the engine above to begin monitoring.</div>
        </div>
      )}
      {signals.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {signals.map((s) => <SignalCard key={s.tradeLogId} s={s} />)}
        </div>
      )}
    </div>
  )
}
