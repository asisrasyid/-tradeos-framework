import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type EvaluateResult, type TheoryDetail, type TheoryFactor } from '../lib/api'
import { ArrowLeft, Trash2 } from 'lucide-react'

const STATE_PALETTE: Record<number, string> = {
  0: '#10B981', 1: '#EF4444', 2: '#F59E0B', 3: '#3B82F6',
  4: '#8B5CF6', 5: '#F97316', 6: '#06B6D4', 7: '#EC4899',
}

const TIMEFRAMES = ['M5', 'M15', 'H1', 'H4', 'D1']

const STATE_COLORS: Record<string, string> = {
  S0: '#10B981',
  S1: '#EF4444',
  S2: '#F59E0B',
  S3: '#3B82F6',
  S4: '#8B5CF6',
  S5: '#F97316',
}

function DecisionBadge({ decision }: { decision: string }) {
  const cls: Record<string, string> = {
    SIGNAL: 'badge--buy',
    WATCH:  'badge--warn',
    SKIP:   'badge--neutral',
  }
  return (
    <span className={`badge mono ${cls[decision] ?? 'badge--neutral'}`} style={{ fontSize: '13px', padding: '4px 12px' }}>
      {decision}
    </span>
  )
}

function StateSeqChips({ repr }: { repr: string }) {
  const tokens = repr.split(/[\s,→]+/).filter(Boolean)
  return (
    <div className="flex flex-wrap gap-1.5">
      {tokens.map((tok, i) => {
        const key = tok.replace(/[^A-Za-z0-9]/g, '').toUpperCase()
        const color = STATE_COLORS[key] ?? '#94A3B8'
        return (
          <span
            key={i}
            className="px-2 py-0.5 rounded text-xs font-mono font-semibold"
            style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
          >
            {tok}
          </span>
        )
      })}
    </div>
  )
}

const FACTOR_TYPES = ['state_sequence_match', 'c_code_condition', 'pattern_match']
const C_CODE_KEYS = [
  'HMM_STATE_SEQ_MATCH', 'HTF_BIAS_BULLISH', 'HTF_BIAS_BEARISH',
  'BOS_BULLISH', 'BOS_BEARISH', 'CHOCH_BULLISH', 'CHOCH_BEARISH',
  'OB_BULLISH_ACTIVE', 'OB_BEARISH_ACTIVE', 'PRICE_IN_OB_BULL', 'PRICE_IN_OB_BEAR',
  'FVG_BULLISH', 'FVG_BEARISH', 'EQH_SWEPT', 'EQL_SWEPT',
  'HMM_STATE_IS_RETEST', 'HMM_STATE_IS_POST_BOS', 'HMM_STATE_IS_RANGING',
  'MARKET_TRENDING', 'ABOVE_200EMA', 'CANDLE_MOMENTUM_BULL', 'CANDLE_MOMENTUM_BEAR',
  'ATR_NORMAL', 'HIGH_VOLUME',
  'SESSION_LONDON', 'SESSION_NY', 'SESSION_LONDON_OPEN_KZ', 'SESSION_NY_KZ',
]

export default function TheoryDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [instrument, setInstrument] = useState('')
  const [timeframe, setTimeframe] = useState('H1')
  const [evalResult, setEvalResult] = useState<EvaluateResult | null>(null)
  const [showAddFactor, setShowAddFactor] = useState(false)
  const [factorCode, setFactorCode]     = useState(C_CODE_KEYS[0])
  const [factorType, setFactorType]     = useState(FACTOR_TYPES[0])
  const [decisionPt, setDecisionPt]     = useState('5')
  const [factorTf, setFactorTf]         = useState('H1')
  const [isRequired, setIsRequired]     = useState(false)
  const [patternId,  setPatternId]      = useState('')

  const { data: patterns = [] } = useQuery({
    queryKey: ['patterns'],
    queryFn: api.listPatterns,
  })

  const isHmmFactor = factorCode === 'HMM_STATE_SEQ_MATCH'

  const { data, isLoading, error } = useQuery<TheoryDetail>({
    queryKey: ['theory', id],
    queryFn: () => api.getTheoryDetail(id!),
    enabled: !!id,
  })

  useEffect(() => {
    if (data && !instrument) setInstrument(data.theory.instrument)
  }, [data])

  const mutation = useMutation({
    mutationFn: () => api.evaluateTheory(id!, instrument || (data?.theory.instrument ?? ''), timeframe),
    onSuccess: (result) => setEvalResult(result),
  })

  const addFactorMutation = useMutation({
    mutationFn: () => api.addFactor(id!, {
      factorCode:    factorCode,
      factorType:    factorType,
      decisionPoint: parseInt(decisionPt) || 0,
      isRequired:    isRequired,
      timeframe:     factorTf,
      sortOrder:     (data?.factors.length ?? 0),
      ...(isHmmFactor && patternId ? { patternId } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['theory', id] })
      setShowAddFactor(false)
    },
  })

  const removeFactorMutation = useMutation({
    mutationFn: (factorId: string) => api.removeFactor(id!, factorId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['theory', id] }),
  })

  if (isLoading) {
    return (
      <div className="page-container">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', padding: '24px 0' }}>
          <span className="spinner spinner--md" />
          Loading theory…
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="page-container">
        <div className="alert-error">
          Failed to load theory.{' '}
          <Link to="/theories" className="underline">Back to Theories</Link>
        </div>
      </div>
    )
  }

  const { theory, factors } = data
  const dirColor = theory.direction === 'LONG' ? 'var(--buy)' : theory.direction === 'SHORT' ? 'var(--sell)' : 'var(--warning)'
  const dirBg    = theory.direction === 'LONG' ? 'var(--buy-bg)' : theory.direction === 'SHORT' ? 'var(--sell-bg)' : 'var(--warn-bg)'
  const effectiveInstrument = instrument || theory.instrument

  return (
    <div className="page-container" style={{ maxWidth: '1000px' }}>
      {/* Back link */}
      <div>
        <Link to="/theories" className="btn-secondary" style={{ width: 'fit-content' }}>
          <ArrowLeft size={14} /> Back to Theories
        </Link>
      </div>

      {/* Theory meta card */}
      <div className="card">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="page-heading">{theory.name}</h1>
            {theory.description && (
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>{theory.description}</p>
            )}
          </div>
          <span
            className="badge mono flex-shrink-0"
            style={{
              background: dirBg,
              color: dirColor,
              border: `1px solid ${dirColor}40`,
              fontSize: '13px',
              padding: '4px 14px',
              fontWeight: 700,
            }}
          >
            {theory.direction}
          </span>
        </div>
        <div className="flex flex-wrap gap-4 text-sm" style={{ color: 'var(--text-muted)', marginTop: '12px' }}>
          <span>Instrument: <span className="font-medium" style={{ color: 'var(--text)' }}>{theory.instrument}</span></span>
          <span>Version: <span className="font-medium" style={{ color: 'var(--text)' }}>v{theory.version}</span></span>
          <span>Threshold: <span className="font-medium" style={{ color: 'var(--text)' }}>{theory.threshold}</span></span>
          <span>Min Confidence: <span className="font-medium" style={{ color: 'var(--text)' }}>{theory.minConfidence}%</span></span>
        </div>
      </div>

      {/* Factors section */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="flex items-center justify-between" style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
          <span className="font-semibold" style={{ color: 'var(--text)' }}>Factors</span>
          <button
            onClick={() => setShowAddFactor(v => !v)}
            className="btn-primary"
          >
            {showAddFactor ? 'Cancel' : '+ Add Factor'}
          </button>
        </div>

        {showAddFactor && (
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="form-group">
                <label className="form-label">C-Code / Factor</label>
                <select
                  value={factorCode}
                  onChange={e => { setFactorCode(e.target.value); setPatternId('') }}
                  className="form-input"
                  style={{ minWidth: '220px', width: 'auto' }}
                >
                  {C_CODE_KEYS.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </div>

              {isHmmFactor && (
                <div className="form-group">
                  <label className="form-label">Pattern</label>
                  <select
                    value={patternId}
                    onChange={e => setPatternId(e.target.value)}
                    className="form-input"
                    style={{ minWidth: '200px', width: 'auto' }}
                  >
                    <option value="">— pilih pattern —</option>
                    {patterns.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.stateSeqRepr})
                      </option>
                    ))}
                  </select>
                  {patternId && (() => {
                    const p = patterns.find(x => x.id === patternId)
                    if (!p) return null
                    const states = (p.stateSeqRepr ?? '').match(/S(\d)/g) ?? []
                    return (
                      <div style={{ marginTop: 4 }}>
                        {states.length > 0 && (
                          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginBottom: 4 }}>
                            {states.map((s, i) => {
                              const n = parseInt(s[1])
                              const color = STATE_PALETTE[n] ?? '#94a3b8'
                              return (
                                <span key={i} style={{
                                  background: `${color}22`, color,
                                  border: `1px solid ${color}55`,
                                  borderRadius: 3, padding: '1px 6px',
                                  fontSize: 11, fontFamily: 'monospace', fontWeight: 700,
                                }}>{s}</span>
                              )
                            })}
                          </div>
                        )}
                        {p.description && (
                          <div style={{
                            fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5,
                            padding: '6px 10px', borderRadius: 5,
                            background: 'var(--surface-2)', border: '1px solid var(--border)',
                            maxWidth: 360,
                          }}>
                            {p.description}
                          </div>
                        )}
                      </div>
                    )
                  })()}
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Type</label>
                <select
                  value={factorType}
                  onChange={e => setFactorType(e.target.value)}
                  className="form-input"
                  style={{ width: 'auto' }}
                >
                  {FACTOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Decision Pts</label>
                <input
                  type="number"
                  value={decisionPt}
                  onChange={e => setDecisionPt(e.target.value)}
                  className="form-input"
                  style={{ width: '72px' }}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Timeframe</label>
                <select
                  value={factorTf}
                  onChange={e => setFactorTf(e.target.value)}
                  className="form-input"
                  style={{ width: 'auto' }}
                >
                  {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Required</label>
                <input type="checkbox" checked={isRequired} onChange={e => setIsRequired(e.target.checked)} style={{ marginTop: '8px' }} />
              </div>
              <div className="form-group" style={{ justifyContent: 'flex-end' }}>
                <button
                  onClick={() => addFactorMutation.mutate()}
                  disabled={addFactorMutation.isPending}
                  className="btn-primary disabled:opacity-60"
                >
                  {addFactorMutation.isPending ? 'Adding…' : 'Add'}
                </button>
              </div>
            </div>
            {addFactorMutation.isError && (
              <div className="alert-error" style={{ marginTop: '8px', fontSize: '12px' }}>{String(addFactorMutation.error)}</div>
            )}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                {['Factor Code', 'Type', 'Decision Points', 'Required', 'Operator', 'Threshold', 'Timeframe', ''].map(col => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {factors.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-state">No factors defined.</div>
                  </td>
                </tr>
              ) : (
                factors.map((f: TheoryFactor) => (
                  <tr key={f.id}>
                    <td className="font-mono" style={{ color: 'var(--accent)' }}>{f.factorCode}</td>
                    <td>{f.factorType}</td>
                    <td>{f.decisionPoint}</td>
                    <td>
                      <span
                        className="px-1.5 py-0.5 rounded text-xs font-medium"
                        style={f.isRequired
                          ? { background: 'var(--buy-bg)', color: 'var(--buy)' }
                          : { background: 'rgba(100,116,139,0.15)', color: 'var(--text-muted)' }
                        }
                      >
                        {f.isRequired ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>—</td>
                    <td style={{ color: 'var(--text-muted)' }}>—</td>
                    <td style={{ color: 'var(--text-muted)' }}>{f.timeframe ?? '—'}</td>
                    <td>
                      <button
                        onClick={() => removeFactorMutation.mutate(f.id)}
                        disabled={removeFactorMutation.isPending}
                        className="btn-remove-state disabled:opacity-40"
                        title="Remove factor"
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Evaluate Now */}
      <div className="card flex flex-col gap-4">
        <div className="section-title">Evaluate Now</div>

        <div className="flex flex-wrap gap-3 items-end">
          <div className="form-group">
            <label className="form-label">Instrument</label>
            <input
              type="text"
              value={effectiveInstrument}
              onChange={e => setInstrument(e.target.value)}
              className="form-input"
              style={{ width: '120px' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Timeframe</label>
            <select
              value={timeframe}
              onChange={e => setTimeframe(e.target.value)}
              className="form-input"
              style={{ width: 'auto' }}
            >
              {TIMEFRAMES.map(tf => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="btn-primary disabled:opacity-60"
            >
              {mutation.isPending ? 'Evaluating…' : 'Evaluate'}
            </button>
          </div>
        </div>

        {mutation.isError && (
          <div className="alert-error">
            {mutation.error instanceof Error ? mutation.error.message : 'Evaluation failed'}
          </div>
        )}

        {evalResult && (
          <div className="card-sm flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <DecisionBadge decision={evalResult.decision} />
            </div>
            <div className="flex flex-wrap gap-5 text-sm">
              <div>
                <div className="stat-label">Composite Score</div>
                <div className="font-semibold mono" style={{ color: 'var(--text)' }}>{evalResult.compositeScore.toFixed(3)}</div>
              </div>
              <div>
                <div className="stat-label">P(WIN)</div>
                <div className="font-semibold mono" style={{ color: 'var(--text)' }}>{(evalResult.pWin * 100).toFixed(1)}%</div>
              </div>
              {evalResult.tradeLogId && (
                <div>
                  <div className="stat-label">Trade Log ID</div>
                  <div className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{evalResult.tradeLogId}</div>
                </div>
              )}
            </div>
            {evalResult.stateSeqRepr && (
              <div>
                <div className="stat-label" style={{ marginBottom: '6px' }}>State Sequence</div>
                <StateSeqChips repr={evalResult.stateSeqRepr} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
