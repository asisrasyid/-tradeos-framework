import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Plus, Brain, X, Trash2 } from 'lucide-react'

type SortKey = 'az' | 'za' | 'tf' | 'newest'
const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'az',     label: 'A → Z'    },
  { key: 'za',     label: 'Z → A'    },
  { key: 'tf',     label: 'Timeframe'},
  { key: 'newest', label: 'Terbaru'  },
]

function TypeBadge({ type }: { type: string }) {
  if (type === 'state_sequence') return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 3,
      background: 'var(--accent)18', color: 'var(--accent)', border: '1px solid var(--accent)30' }}>
      HMM
    </span>
  )
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 3,
      background: 'var(--surface-2)', color: 'var(--text-faint)', border: '1px solid var(--border)' }}>
      {type}
    </span>
  )
}

const STATE_COLORS: Record<string, string> = {
  S0: '#10B981', S1: '#EF4444', S2: '#F59E0B',
  S3: '#3B82F6', S4: '#8B5CF6', S5: '#F97316',
}

function StateSeq({ repr }: { repr?: string }) {
  if (!repr) return null
  return (
    <div className="flex gap-1 flex-wrap">
      {repr.match(/S\d/g)?.map((st, i) => (
        <span
          key={i}
          className="state-chip"
          style={{
            background: `${STATE_COLORS[st] ?? '#94a3b8'}22`,
            color: STATE_COLORS[st] ?? '#94a3b8',
          }}
        >
          {st}
        </span>
      ))}
    </div>
  )
}

const STATES = ['0', '1', '2', '3', '4', '5', '6', '7']

export default function Patterns() {
  const qc = useQueryClient()
  const [sort, setSort] = useState<SortKey>('az')
  const [typeFilter, setTypeFilter] = useState<'all' | 'state_sequence'>('all')

  const { data: patterns = [], isLoading } = useQuery({
    queryKey: ['patterns'],
    queryFn: api.listPatterns,
  })

  const deleteMut = useMutation({
    mutationFn: api.deletePattern,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['patterns'] }),
  })

  function handleDelete(id: string, code: string) {
    if (!window.confirm(`Hapus pattern "${code}"?`)) return
    deleteMut.mutate(id)
  }

  const sorted = useMemo(() => {
    let list = [...patterns]
    if (typeFilter === 'state_sequence') list = list.filter(p => p.patternType === 'state_sequence')
    if (sort === 'az') return list.sort((a, b) => a.code.localeCompare(b.code))
    if (sort === 'za') return list.sort((a, b) => b.code.localeCompare(a.code))
    if (sort === 'tf') return list.sort((a, b) => (a.timeframe ?? '').localeCompare(b.timeframe ?? ''))
    return list
  }, [patterns, sort, typeFilter])

  const [showForm, setShowForm] = useState(false)
  const [code,     setCode]     = useState('')
  const [name,     setName]     = useState('')
  const [tf,       setTf]       = useState('H1')
  const [seq,      setSeq]      = useState<string[]>(['0', '3', '4'])

  const addState    = () => setSeq(s => [...s, '0'])
  const removeState = (i: number) => setSeq(s => s.filter((_, idx) => idx !== i))
  const updateState = (i: number, v: string) => setSeq(s => s.map((x, idx) => idx === i ? v : x))
  const seqRepr     = seq.map(s => `S${s}`).join('')

  const [desc, setDesc] = useState('')

  const createMutation = useMutation({
    mutationFn: () => api.createPattern({
      code,
      name,
      description: desc || null,
      patternType: 'state_sequence',
      timeframe: tf,
      stateSequence: JSON.stringify(seq.map(Number)),
      stateSeqRepr: seqRepr,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patterns'] })
      setShowForm(false)
      setCode('')
      setName('')
      setDesc('')
    },
  })

  return (
    <div className="page-container">
      <div className="page-topbar">
        <h1 className="page-heading">HMM Patterns</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Type filter */}
          <div style={{ display: 'flex', gap: 3, background: 'var(--surface-2)', borderRadius: 5, padding: 2, border: '1px solid var(--border)' }}>
            {([['all', 'Semua'], ['state_sequence', 'HMM']] as const).map(([val, lbl]) => (
              <button key={val} onClick={() => setTypeFilter(val)} style={{
                padding: '3px 10px', fontSize: 11, fontWeight: 600, borderRadius: 3,
                cursor: 'pointer', border: 'none', transition: 'all 0.12s',
                background: typeFilter === val ? 'var(--accent)' : 'transparent',
                color:      typeFilter === val ? '#fff'          : 'var(--text-muted)',
              }}>{lbl}</button>
            ))}
          </div>
          {/* Sort buttons */}
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
          <button onClick={() => setShowForm(v => !v)} className={showForm ? 'btn-secondary' : 'btn-primary'}>
            {showForm ? <><X size={14} /> Cancel</> : <><Plus size={14} /> New Pattern</>}
          </button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="card" style={{ animation: 'fade-in 0.15s ease-out' }}>
          <div className="section-title">New Pattern</div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div className="form-group" style={{ gridColumn: 'span 2' }}>
              <label className="form-label">Code</label>
              <input
                value={code}
                onChange={e => setCode(e.target.value)}
                placeholder="BnR_BULL_S0S3S4"
                className="form-input mono"
              />
            </div>
            <div className="form-group" style={{ gridColumn: 'span 2' }}>
              <label className="form-label">Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Break and Retest Bullish"
                className="form-input"
              />
            </div>
            <div className="form-group" style={{ gridColumn: 'span 4' }}>
              <label className="form-label">Deskripsi <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>(opsional — jelaskan kondisi market yang diwakili pattern ini)</span></label>
              <textarea
                value={desc}
                onChange={e => setDesc(e.target.value)}
                rows={2}
                className="form-input"
                placeholder="Contoh: State S0 mewakili konsolidasi low-volatility, diikuti S3 yang menunjukkan momentum bullish breakout dari resistance…"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Timeframe</label>
              <select value={tf} onChange={e => setTf(e.target.value)} className="form-input">
                {['M1', 'M5', 'M15', 'H1', 'H4', 'D1'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          {/* State sequence builder */}
          <div className="form-group">
            <label className="form-label">
              State Sequence — Preview:{' '}
              <span className="mono font-semibold" style={{ color: 'var(--accent)' }}>{seqRepr}</span>
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
              {seq.map((s, i) => {
                const key = `S${s}`
                const color = STATE_COLORS[key] ?? '#94a3b8'
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <select
                      value={s}
                      onChange={e => updateState(i, e.target.value)}
                      style={{
                        background: `${color}20`,
                        border: `1px solid ${color}50`,
                        color: color,
                        borderRadius: 'var(--radius-sm)',
                        padding: '4px 8px',
                        fontSize: '12px',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        outline: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      {STATES.map(st => (
                        <option key={st} value={st} style={{ background: 'var(--surface)', color: 'var(--text)' }}>
                          S{st}
                        </option>
                      ))}
                    </select>
                    {seq.length > 1 && (
                      <button
                        onClick={() => removeState(i)}
                        className="btn-remove-state"
                        aria-label={`Remove S${s}`}
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                )
              })}
              <button
                onClick={addState}
                className="btn-secondary"
                style={{ height: '30px', padding: '0 12px', fontSize: '12px' }}
              >
                <Plus size={12} /> State
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '16px' }}>
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !code || !name}
              className="btn-primary"
            >
              {createMutation.isPending
                ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Saving…</>
                : 'Create Pattern'
              }
            </button>
            {createMutation.isError && (
              <span className="alert-error" style={{ padding: '4px 10px', fontSize: '12px' }}>
                {String(createMutation.error)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Patterns table */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Name</th>
              <th scope="col">Deskripsi</th>
              <th scope="col">TF</th>
              <th scope="col">Type</th>
              <th scope="col">Sequence</th>
              <th scope="col">Source</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} style={{ padding: '12px 14px' }}>
                      <div className="skeleton" style={{ height: '13px', width: j === 0 ? '120px' : '80px' }} />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!isLoading && sorted.map(p => (
              <tr key={p.id}>
                <td className="mono" style={{ color: 'var(--accent)', fontWeight: 700, fontSize: '12px' }}>
                  {p.code}
                </td>
                <td style={{ fontWeight: 500 }}>{p.name}</td>
                <td style={{ fontSize: '11px', color: 'var(--text-muted)', maxWidth: 240 }}>
                  {p.description
                    ? <span title={p.description} style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{p.description}</span>
                    : <span style={{ color: 'var(--text-faint)', fontStyle: 'italic' }}>—</span>
                  }
                </td>
                <td className="mono" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>{p.timeframe ?? '—'}</td>
                <td><TypeBadge type={p.patternType} /></td>
                <td>
                  {p.stateSeqRepr
                    ? <StateSeq repr={p.stateSeqRepr} />
                    : <span style={{ fontSize: 11, color: 'var(--text-faint)', fontStyle: 'italic' }}>no sequence</span>
                  }
                </td>
                <td style={{ fontSize: '12px', color: 'var(--text-faint)' }}>{p.source}</td>
                <td>
                  <button
                    onClick={() => handleDelete(p.id, p.code)}
                    className="btn-icon-danger"
                    title="Hapus pattern"
                    disabled={deleteMut.isPending}
                  >
                    <Trash2 size={12} />
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && sorted.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <div className="empty-state">
                    <Brain size={32} style={{ color: 'var(--text-faint)', opacity: 0.5 }} aria-hidden="true" />
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No patterns yet</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>
                      Create your first HMM state pattern above.
                    </div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
