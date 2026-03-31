import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type BacktestSession, type BacktestResultStats, type BacktestTradeRecord } from '../lib/api'
import { useState, useMemo } from 'react'
import { Play, FlaskConical, ChevronDown, ChevronRight, TrendingUp, TrendingDown, Minus, Trash2 } from 'lucide-react'

type SortKey = 'newest' | 'oldest' | 'completed' | 'instrument'
const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'newest',    label: 'Terbaru'   },
  { key: 'oldest',    label: 'Terlama'   },
  { key: 'completed', label: 'Selesai ↑' },
  { key: 'instrument',label: 'Instrument'},
]

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    completed: { cls: 'badge--buy',    label: 'Completed' },
    failed:    { cls: 'badge--sell',   label: 'Failed'    },
    running:   { cls: 'badge--warn',   label: 'Running'   },
    queued:    { cls: 'badge--accent', label: 'Queued'    },
    pending:   { cls: 'badge--neutral',label: 'Pending'   },
  }
  const { cls = 'badge--neutral', label = status } = map[status] ?? {}
  return <span className={`badge ${cls}`}>{label}</span>
}

// ── Mini equity sparkline ─────────────────────────────────────────────────────
function EquitySpark({ curve }: { curve: number[] }) {
  if (!Array.isArray(curve) || curve.length < 2) return null
  const W = 160; const H = 40
  const min = Math.min(...curve); const max = Math.max(...curve)
  const range = max - min || 1
  const pts = curve.map((v, i) => {
    const x = (i / (curve.length - 1)) * W
    const y = H - ((v - min) / range) * H
    return `${x},${y}`
  }).join(' ')
  const last = curve[curve.length - 1]
  const color = last >= curve[0] ? 'var(--buy)' : 'var(--sell)'
  return (
    <svg width={W} height={H} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  )
}

// ── Stat tile ─────────────────────────────────────────────────────────────────
function StatTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', color: color ?? 'var(--text)' }}>{value}</span>
    </div>
  )
}

// ── Trade outcome chip ────────────────────────────────────────────────────────
function OutcomeChip({ outcome }: { outcome: string }) {
  const map: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
    win:       { color: 'var(--buy)',     bg: 'var(--buy-bg)',  icon: <TrendingUp size={10} /> },
    loss:      { color: 'var(--sell)',    bg: 'var(--sell-bg)', icon: <TrendingDown size={10} /> },
    breakeven: { color: 'var(--warning)', bg: 'var(--warn-bg)', icon: <Minus size={10} /> },
  }
  const cfg = map[outcome] ?? map.breakeven
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 700,
      padding: '1px 7px', borderRadius: 3, background: cfg.bg, color: cfg.color }}>
      {cfg.icon}{outcome.toUpperCase()}
    </span>
  )
}

// ── Results panel (injected as rows below session row) ────────────────────────
function ResultsPanel({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['bt-result', sessionId],
    queryFn: () => api.getResults(sessionId),
    staleTime: 60_000,
  })
  const { data: trades = [], isLoading: tradesLoading } = useQuery({
    queryKey: ['bt-trades', sessionId],
    queryFn: () => api.getBacktestTrades(sessionId),
    staleTime: 60_000,
  })

  if (isLoading) return (
    <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', background: 'var(--surface-2)' }}>
      <span className="spinner spinner--sm" style={{ marginRight: 8 }} /> Memuat hasil…
    </td></tr>
  )

  const r: BacktestResultStats | null = (data as { result: BacktestResultStats | null })?.result ?? null
  if (!r) return (
    <tr><td colSpan={7} style={{ padding: '16px 20px', color: 'var(--text-faint)', fontSize: 12, background: 'var(--surface-2)' }}>
      Belum ada hasil — backtest mungkin masih berjalan atau gagal.
    </td></tr>
  )

  const pfColor = r.profitFactor >= 1.5 ? 'var(--buy)' : r.profitFactor >= 1.0 ? 'var(--warning)' : 'var(--sell)'
  const wrColor = r.winRate >= 55 ? 'var(--buy)' : r.winRate >= 45 ? 'var(--warning)' : 'var(--sell)'
  const ddColor = r.maxDrawdown <= 10 ? 'var(--buy)' : r.maxDrawdown <= 20 ? 'var(--warning)' : 'var(--sell)'
  const rawCurve = r.equityCurve
  const equity: number[] = Array.isArray(rawCurve)
    ? rawCurve
    : typeof rawCurve === 'string'
      ? (() => { try { return JSON.parse(rawCurve) } catch { return [] } })()
      : []

  return (
    <>
      {/* Stats row */}
      <tr style={{ background: 'var(--surface-2)', borderLeft: '3px solid var(--accent)' }}>
        <td colSpan={7} style={{ padding: '14px 20px' }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            <StatTile label="Signals"       value={String(r.totalSignals)} />
            <StatTile label="Win"           value={String(r.wins)}         color="var(--buy)" />
            <StatTile label="Loss"          value={String(r.losses)}       color="var(--sell)" />
            <StatTile label="Win Rate"      value={`${r.winRate?.toFixed(1)}%`}   color={wrColor} />
            <StatTile label="Profit Factor" value={r.profitFactor?.toFixed(2)}    color={pfColor} />
            <StatTile label="Avg RR"        value={r.avgRr?.toFixed(2)} />
            <StatTile label="Total Pips"    value={`${(r.totalPips ?? 0) >= 0 ? '+' : ''}${r.totalPips?.toFixed(1)}`}
              color={(r.totalPips ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)'} />
            <StatTile label="Max DD"        value={`${r.maxDrawdown?.toFixed(1)}%`} color={ddColor} />
            <StatTile label="Sharpe"        value={r.sharpeRatio?.toFixed(3)} />
            {equity.length > 1 && (
              <div style={{ marginLeft: 'auto' }}>
                <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>Equity Curve</div>
                <EquitySpark curve={equity} />
              </div>
            )}
          </div>
          {(r.bestSeqRepr || r.worstSeqRepr) && (
            <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
              {r.bestSeqRepr && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Best: <span className="mono" style={{ color: 'var(--buy)', fontWeight: 700 }}>{r.bestSeqRepr}</span>
              </span>}
              {r.worstSeqRepr && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Worst: <span className="mono" style={{ color: 'var(--sell)', fontWeight: 700 }}>{r.worstSeqRepr}</span>
              </span>}
            </div>
          )}
        </td>
      </tr>

      {/* Trade log row */}
      {tradesLoading ? (
        <tr style={{ background: 'var(--surface-2)' }}><td colSpan={7} style={{ padding: '8px 20px', fontSize: 12, color: 'var(--text-faint)' }}>
          Memuat trade log…
        </td></tr>
      ) : (trades as BacktestTradeRecord[]).length > 0 ? (
        <tr style={{ background: 'var(--surface-2)' }}>
          <td colSpan={7} style={{ padding: '0 20px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', margin: '8px 0 6px' }}>
              TRADE LOG ({(trades as BacktestTradeRecord[]).length})
            </div>
            <div style={{ overflowX: 'auto', maxHeight: 300, overflowY: 'auto', borderRadius: 6, border: '1px solid var(--border)' }}>
              <table className="data-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    <th>#</th><th>Time</th><th>Dir</th><th>Entry</th>
                    <th>SL</th><th>TP</th><th>ATR</th><th>Exit</th>
                    <th>PnL</th><th>RR</th><th>Outcome</th><th>Seq</th><th>Sim</th>
                  </tr>
                </thead>
                <tbody>
                  {(trades as BacktestTradeRecord[]).map((t, i) => (
                    <tr key={t.id}>
                      <td className="mono" style={{ color: 'var(--text-faint)' }}>{i + 1}</td>
                      <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {t.time ? new Date(t.time).toLocaleString(undefined, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
                      </td>
                      <td><span style={{ fontWeight: 700, fontSize: 10, color: t.direction === 'LONG' ? 'var(--buy)' : 'var(--sell)' }}>{t.direction}</span></td>
                      <td className="mono">{t.entry?.toFixed(2)}</td>
                      <td className="mono" style={{ color: 'var(--sell)' }}>{t.sl?.toFixed(2)}</td>
                      <td className="mono" style={{ color: 'var(--buy)' }}>{t.tp?.toFixed(2)}</td>
                      <td className="mono" style={{ color: 'var(--text-faint)' }}>{t.atr?.toFixed(3)}</td>
                      <td className="mono">{t.exitPrice?.toFixed(2)}</td>
                      <td className="mono" style={{ color: (t.pnlPips ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)', fontWeight: 700 }}>
                        {(t.pnlPips ?? 0) >= 0 ? '+' : ''}{t.pnlPips?.toFixed(1)}
                      </td>
                      <td className="mono" style={{ color: (t.rrAchieved ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)' }}>
                        {(t.rrAchieved ?? 0) >= 0 ? '+' : ''}{t.rrAchieved?.toFixed(2)}R
                      </td>
                      <td><OutcomeChip outcome={t.outcome} /></td>
                      <td className="mono" style={{ color: 'var(--accent)', fontSize: 10 }}>{t.seqRepr ?? '—'}</td>
                      <td className="mono" style={{ color: 'var(--text-faint)' }}>{((t.similarity ?? 0) * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function Backtest() {
  const qc = useQueryClient()
  const [theoryId,   setTheoryId]   = useState('')
  const [instrument, setInstrument] = useState('XAUUSDm')
  const [timeframe,  setTimeframe]  = useState('M15')
  const [dateFrom,   setDateFrom]   = useState('2025-01-01')
  const [dateTo,     setDateTo]     = useState(new Date().toISOString().slice(0, 10))
  const [dataSource, setDataSource] = useState<'db' | 'mt5'>('db')
  const [slType,     setSlType]     = useState<'atr' | 'fixed'>('atr')
  const [slValue,    setSlValue]    = useState(1.0)
  const [tpType,     setTpType]     = useState<'atr' | 'fixed'>('atr')
  const [tpValue,    setTpValue]    = useState(2.0)
  const [maxHold,    setMaxHold]    = useState(20)
  const [expanded,   setExpanded]   = useState<string | null>(null)
  const [sort,       setSort]       = useState<SortKey>('newest')

  const { data: theories = [] } = useQuery({ queryKey: ['theories'], queryFn: api.listTheories })
  const { data: sessions = [], refetch } = useQuery({
    queryKey: ['bt-sessions'],
    queryFn: () => api.listSessions(),
    refetchInterval: 5_000,
  })

  const deleteMut = useMutation({
    mutationFn: api.deleteBacktestSession,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bt-sessions'] }),
  })

  function handleDelete(id: string) {
    if (!window.confirm('Hapus sesi backtest ini beserta semua trade log-nya?')) return
    if (expanded === id) setExpanded(null)
    deleteMut.mutate(id)
  }

  const sortedSessions = useMemo(() => {
    const list = [...(sessions as BacktestSession[])]
    if (sort === 'newest')     return list.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    if (sort === 'oldest')     return list.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
    if (sort === 'completed')  return list.sort((a, b) => (a.status === 'completed' ? -1 : 1) - (b.status === 'completed' ? -1 : 1))
    if (sort === 'instrument') return list.sort((a, b) => a.instrument.localeCompare(b.instrument))
    return list
  }, [sessions, sort])

  const run = useMutation({
    mutationFn: () => api.runBacktest({
      theoryId, instrument, timeframe,
      dateFrom: new Date(dateFrom), dateTo: new Date(dateTo),
      dataSource, slType, slValue, tpType, tpValue, maxHoldBars: maxHold,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['bt-sessions'] }); refetch() },
  })

  const slLabel = slType === 'atr' ? `ATR × ${slValue}` : `${slValue} pts`
  const tpLabel = tpType === 'atr' ? `ATR × ${tpValue}` : `${tpValue} pts`

  return (
    <div className="page-container">
      <div className="page-topbar">
        <h1 className="page-heading">Backtest</h1>
      </div>

      {/* ── Config Card ── */}
      <div className="card">
        <div className="section-title">Queue New Backtest</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(148px, 1fr))', gap: 12, alignItems: 'end' }}>

          <div className="form-group" style={{ gridColumn: 'span 2' }}>
            <label className="form-label">Theory</label>
            <select className="form-input" value={theoryId} onChange={e => setTheoryId(e.target.value)}>
              <option value="">Select theory…</option>
              {theories.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Instrument</label>
            {dataSource === 'mt5' ? (
              <input
                className="form-input mono"
                value={instrument}
                onChange={e => setInstrument(e.target.value)}
                placeholder="e.g. XAUUSD, EURUSD"
              />
            ) : (
              <select className="form-input" value={instrument} onChange={e => setInstrument(e.target.value)}>
                {['XAUUSDm','XAUUSDc','XAUUSD','EURUSD','GBPUSD','NAS100'].map(i => <option key={i}>{i}</option>)}
              </select>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Timeframe</label>
            <select className="form-input" value={timeframe} onChange={e => setTimeframe(e.target.value)}>
              {['M1','M5','M15','M30','H1','H4','D1'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Date From</label>
            <input type="date" className="form-input" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label">Date To</label>
            <input type="date" className="form-input" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label">Data Source</label>
            <div style={{ display: 'flex', gap: 6 }}>
              {(['db','mt5'] as const).map(src => (
                <button key={src} type="button" onClick={() => setDataSource(src)} style={{
                  flex: 1, padding: '6px 0', fontSize: 11, fontWeight: 700,
                  borderRadius: 4, cursor: 'pointer', border: '1px solid', transition: 'all 0.15s',
                  borderColor: dataSource === src ? 'var(--accent)' : 'var(--border)',
                  background:  dataSource === src ? 'var(--accent)20' : 'var(--surface-2)',
                  color:       dataSource === src ? 'var(--accent)' : 'var(--text-muted)',
                }}>
                  {src === 'db' ? '🗄 DB' : '📡 MT5'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── SL/TP Schema ── */}
        <div style={{ borderTop: '1px solid var(--border)', margin: '14px 0 12px' }} />
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '0.5px' }}>
          SKEMA SL/TP —{' '}
          <span className="mono" style={{ color: 'var(--sell)' }}>SL: {slLabel}</span>
          {' · '}
          <span className="mono" style={{ color: 'var(--buy)' }}>TP: {tpLabel}</span>
          {' · '}
          <span className="mono" style={{ color: 'var(--text-faint)' }}>Max Hold: {maxHold} bars</span>
          {slType === 'atr' && tpType === 'atr' && (
            <span style={{ marginLeft: 8, color: 'var(--text-faint)', fontWeight: 400 }}>
              RR teori: 1:{(tpValue / slValue).toFixed(2)}
            </span>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, alignItems: 'end' }}>

          <div className="form-group">
            <label className="form-label">SL Type</label>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['atr','fixed'] as const).map(t => (
                <button key={t} onClick={() => setSlType(t)} style={{
                  flex: 1, padding: '5px 0', fontSize: 11, fontWeight: 700,
                  borderRadius: 4, cursor: 'pointer',
                  border: `1px solid ${slType === t ? 'var(--sell)' : 'var(--border)'}`,
                  background: slType === t ? 'var(--sell-bg)' : 'transparent',
                  color: slType === t ? 'var(--sell)' : 'var(--text-muted)',
                }}>
                  {t === 'atr' ? 'ATR ×' : 'Fixed'}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">SL {slType === 'atr' ? 'Mult' : 'Units'}</label>
            <input type="number" className="form-input mono" value={slValue}
              onChange={e => setSlValue(parseFloat(e.target.value) || 1)}
              min={0.1} step={slType === 'atr' ? 0.1 : 0.5} />
          </div>

          <div className="form-group">
            <label className="form-label">TP Type</label>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['atr','fixed'] as const).map(t => (
                <button key={t} onClick={() => setTpType(t)} style={{
                  flex: 1, padding: '5px 0', fontSize: 11, fontWeight: 700,
                  borderRadius: 4, cursor: 'pointer',
                  border: `1px solid ${tpType === t ? 'var(--buy)' : 'var(--border)'}`,
                  background: tpType === t ? 'var(--buy-bg)' : 'transparent',
                  color: tpType === t ? 'var(--buy)' : 'var(--text-muted)',
                }}>
                  {t === 'atr' ? 'ATR ×' : 'Fixed'}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">TP {tpType === 'atr' ? 'Mult' : 'Units'}</label>
            <input type="number" className="form-input mono" value={tpValue}
              onChange={e => setTpValue(parseFloat(e.target.value) || 1)}
              min={0.1} step={tpType === 'atr' ? 0.1 : 0.5} />
          </div>

          <div className="form-group">
            <label className="form-label">Max Hold Bars</label>
            <input type="number" className="form-input mono" value={maxHold}
              onChange={e => setMaxHold(parseInt(e.target.value) || 20)} min={1} max={500} />
          </div>

          <div className="form-group" style={{ alignSelf: 'flex-end' }}>
            <button className="btn-primary" disabled={!theoryId || run.isPending}
              onClick={() => run.mutate()} style={{ width: '100%' }}>
              {run.isPending
                ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Queuing…</>
                : <><Play size={13} /> Run Backtest</>
              }
            </button>
          </div>
        </div>

        {run.isSuccess && (
          <div className="alert-success" style={{ marginTop: 12 }}>
            Queued · Job ID: <span className="mono font-semibold">{run.data}</span>
          </div>
        )}
        {run.isError && (
          <div className="alert-error" style={{ marginTop: 12 }}>{(run.error as Error).message}</div>
        )}
      </div>

      {/* ── Sessions + Results Table ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
          {(sessions as BacktestSession[]).length} session{(sessions as BacktestSession[]).length !== 1 ? 's' : ''}
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {SORT_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setSort(opt.key)} style={{
              padding: '4px 10px', fontSize: 11, fontWeight: 600, borderRadius: 4,
              cursor: 'pointer', border: '1px solid', transition: 'all 0.12s',
              borderColor: sort === opt.key ? 'var(--accent)' : 'var(--border)',
              background:  sort === opt.key ? 'var(--accent)20' : 'transparent',
              color:       sort === opt.key ? 'var(--accent)'   : 'var(--text-muted)',
            }}>{opt.label}</button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Theory</th>
              <th>Instrument/TF</th>
              <th>SL/TP Schema</th>
              <th>Data</th>
              <th>Status</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sortedSessions.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <div className="empty-state">
                    <FlaskConical size={32} style={{ color: 'var(--text-faint)', opacity: 0.5 }} />
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No backtest sessions yet</div>
                    <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>Configure parameters above and click Run Backtest.</div>
                  </div>
                </td>
              </tr>
            )}
            {sortedSessions.map(s => {
              const isExp = expanded === s.id
              const slLbl = s.slType === 'atr' ? `ATR×${s.slValue}` : `${s.slValue}pts`
              const tpLbl = s.tpType === 'atr' ? `ATR×${s.tpValue}` : `${s.tpValue}pts`
              return (
                <>
                  <tr key={s.id}
                    style={{ cursor: s.status === 'completed' ? 'pointer' : 'default' }}
                    onClick={() => s.status === 'completed' && setExpanded(isExp ? null : s.id)}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>
                      {s.theoryId?.slice(0, 8)}…
                    </td>
                    <td className="mono" style={{ fontWeight: 600 }}>{s.instrument} · {s.timeframe}</td>
                    <td style={{ fontSize: 11 }}>
                      <span className="mono" style={{ color: 'var(--sell)' }}>SL:{slLbl}</span>
                      {' '}
                      <span className="mono" style={{ color: 'var(--buy)' }}>TP:{tpLbl}</span>
                      {' '}
                      <span className="mono" style={{ color: 'var(--text-faint)' }}>{s.maxHoldBars}b</span>
                    </td>
                    <td style={{ fontSize: 10, color: 'var(--text-faint)' }}>DB</td>
                    <td><StatusBadge status={s.status} /></td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {new Date(s.createdAt).toLocaleString()}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {s.status === 'completed' && (
                          <span style={{ color: 'var(--text-faint)' }}>
                            {isExp ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </span>
                        )}
                        <button
                          onClick={() => handleDelete(s.id)}
                          className="btn-icon-danger"
                          title="Hapus sesi"
                          disabled={deleteMut.isPending}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {isExp && <ResultsPanel key={`rp-${s.id}`} sessionId={s.id} />}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
