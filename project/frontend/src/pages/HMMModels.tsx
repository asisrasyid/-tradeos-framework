import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type OhlcSyncStatus, type HmmStateInfo, type HmmRecentBar } from '../lib/api'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cpu, BarChart2, RefreshCw, Database, Search, ArrowRight, Plus, X, Check, BookOpen } from 'lucide-react'

// ── OHLC Sync Status Badge ────────────────────────────────────────────────────
function SyncStatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    ok:      { bg: 'var(--buy-bg)',  color: 'var(--buy)'  },
    syncing: { bg: 'var(--warn-bg)', color: 'var(--warning)' },
    error:   { bg: 'var(--sell-bg)', color: 'var(--sell)' },
    idle:    { bg: 'rgba(100,116,139,0.12)', color: 'var(--text-muted)' },
  }
  const { bg, color } = map[status] ?? map.idle
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: '2px 8px',
      borderRadius: 4, background: bg, color,
    }}>
      {status.toUpperCase()}
    </span>
  )
}

// ── State colour palette (S0–S7) ──────────────────────────────────────────────
const STATE_PALETTE = [
  '#10B981', '#EF4444', '#F59E0B', '#3B82F6',
  '#8B5CF6', '#F97316', '#06B6D4', '#EC4899',
]
const stateColor = (s: number) => STATE_PALETTE[s % STATE_PALETTE.length]

// ── Feature bar (mini horizontal bar showing value intensity) ─────────────────
function FeatureBar({ name, desc, value }: { name: string; desc: string; value: number }) {
  // Normalise to 0–100% for visual — clamp at ±3 for momentum_z, 0–1 for others
  const isMomentum = name === 'momentum_z' || name === 'htf_slope'
  const pct = isMomentum
    ? Math.round(((value + 3) / 6) * 100)
    : Math.round(Math.min(Math.max(value, 0), 1) * 100)
  const clamped = Math.min(Math.max(pct, 0), 100)
  const color = isMomentum
    ? (value >= 0 ? 'var(--buy)' : 'var(--sell)')
    : (clamped > 66 ? 'var(--buy)' : clamped > 33 ? 'var(--warning)' : 'var(--sell)')

  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{name}</span>
        <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>{desc}</span>
        <span style={{ color, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ height: 4, background: 'var(--surface-2)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${clamped}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

// ── Create Pattern Modal ──────────────────────────────────────────────────────
const ALL_STATES = ['0','1','2','3','4','5','6','7']

function CreatePatternModal({
  initialState,
  timeframe,
  onClose,
}: {
  initialState: number
  timeframe: string
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [code, setCode]   = useState(`PATTERN_S${initialState}`)
  const [name, setName]   = useState('')
  const [tf,   setTf]     = useState(timeframe)
  const [seq,  setSeq]    = useState<string[]>([String(initialState)])

  const addState    = () => setSeq(s => [...s, '0'])
  const removeState = (i: number) => setSeq(s => s.filter((_, idx) => idx !== i))
  const updateState = (i: number, v: string) => setSeq(s => s.map((x, idx) => idx === i ? v : x))
  const seqRepr     = seq.map(s => `S${s}`).join('')

  const save = useMutation({
    mutationFn: () => api.createPattern({
      code,
      name,
      description: null,
      patternType: 'state_sequence',
      timeframe: tf,
      stateSequence: JSON.stringify(seq.map(Number)),
      stateSeqRepr: seqRepr,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patterns'] })
      onClose()
    },
  })

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 10, padding: 24, width: '100%', maxWidth: 480,
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>Buat Pattern Baru</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={16} />
          </button>
        </div>

        {/* Code */}
        <div className="form-group" style={{ marginBottom: 12 }}>
          <label className="form-label">Code</label>
          <input
            className="form-input mono"
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder="REVERSAL_BULL_S3S1"
          />
        </div>

        {/* Name */}
        <div className="form-group" style={{ marginBottom: 12 }}>
          <label className="form-label">Name</label>
          <input
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Reversal Bullish di Support"
          />
        </div>

        {/* Timeframe */}
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label">Timeframe</label>
          <select className="form-input" value={tf} onChange={e => setTf(e.target.value)}>
            {['M1','M5','M15','M30','H1','H4','D1'].map(t => <option key={t}>{t}</option>)}
          </select>
        </div>

        {/* Sequence builder */}
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label">
            State Sequence —{' '}
            <span className="mono" style={{ color: 'var(--accent)', fontWeight: 700 }}>{seqRepr}</span>
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginTop: 6 }}>
            {seq.map((s, i) => {
              const color = STATE_PALETTE[Number(s) % STATE_PALETTE.length]
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  {i > 0 && <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>→</span>}
                  <select
                    value={s}
                    onChange={e => updateState(i, e.target.value)}
                    style={{
                      background: `${color}20`, border: `1px solid ${color}60`,
                      color, borderRadius: 4, padding: '4px 8px',
                      fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700,
                      outline: 'none', cursor: 'pointer',
                    }}
                  >
                    {ALL_STATES.map(st => (
                      <option key={st} value={st} style={{ background: 'var(--surface)', color: 'var(--text)' }}>
                        S{st}
                      </option>
                    ))}
                  </select>
                  {seq.length > 1 && (
                    <button
                      onClick={() => removeState(i)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-faint)', padding: '2px', lineHeight: 1,
                      }}
                    ><X size={11} /></button>
                  )}
                </div>
              )
            })}
            <button
              onClick={addState}
              className="btn-secondary"
              style={{ height: 30, padding: '0 10px', fontSize: 12 }}
            >
              <Plus size={11} /> State
            </button>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 6 }}>
            Urutkan state dari kiri ke kanan sesuai urutan kemunculannya di chart.
          </div>
        </div>

        {save.isError && (
          <div className="alert-error" style={{ marginBottom: 10, fontSize: 12 }}>
            {String(save.error)}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn-secondary" onClick={onClose}>Batal</button>
          <button
            className="btn-primary"
            disabled={!code || !name || save.isPending}
            onClick={() => save.mutate()}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            {save.isPending
              ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Saving…</>
              : <><Check size={13} /> Simpan Pattern</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

// ── State card ────────────────────────────────────────────────────────────────
function StateCard({ info, onUse }: { info: HmmStateInfo; onUse: (s: number) => void }) {
  const color = stateColor(info.state)
  return (
    <div style={{
      border: `1px solid ${color}40`,
      borderRadius: 8,
      padding: '12px 14px',
      background: `${color}08`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            background: color, color: '#fff', borderRadius: 4,
            padding: '2px 8px', fontSize: 12, fontWeight: 700,
            fontFamily: 'var(--font-mono)',
          }}>S{info.state}</span>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{info.label}</span>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{info.frequency}% freq</span>
      </div>
      {info.features.map(f => (
        <FeatureBar key={f.name} {...f} />
      ))}
      <button
        onClick={() => onUse(info.state)}
        style={{
          marginTop: 8, width: '100%', padding: '5px 0', fontSize: 11,
          fontWeight: 600, borderRadius: 4, cursor: 'pointer',
          background: `${color}20`, border: `1px solid ${color}50`, color,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}
      >
        Gunakan di Pattern <ArrowRight size={11} />
      </button>
    </div>
  )
}

// ── Recent sequence strip ─────────────────────────────────────────────────────
function RecentSequence({ bars }: { bars: HmmRecentBar[] }) {
  const [hovered, setHovered] = useState<number | null>(null)
  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginBottom: 8 }}>
        {bars.map((b, i) => {
          const color = stateColor(b.state)
          return (
            <div
              key={i}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              style={{
                width: 22, height: 22, borderRadius: 3,
                background: `${color}${hovered === i ? 'ee' : '55'}`,
                border: `1px solid ${color}80`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 9, fontWeight: 700, color, cursor: 'default',
                fontFamily: 'var(--font-mono)',
                transition: 'all 0.1s',
              }}
            >
              {b.state}
            </div>
          )
        })}
      </div>
      {hovered !== null && bars[hovered] && (
        <div style={{
          fontSize: 11, color: 'var(--text-muted)', padding: '4px 8px',
          background: 'var(--surface-2)', borderRadius: 4, display: 'inline-block',
        }}>
          Bar {bars[hovered].bar_index} · S{bars[hovered].state} · {bars[hovered].label} ·{' '}
          {new Date(bars[hovered].time).toLocaleString()}
        </div>
      )}
      <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 4 }}>
        ← older · newer → · hover untuk detail
      </div>
    </div>
  )
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface DraftPattern {
  seq:        number[]   // state numbers
  code:       string
  name:       string
  decisionPts: number
  isRequired: boolean
}

// ── Create Theory Modal (all-in-one with inline pattern builder) ───────────────
function CreateTheoryModal({
  instrument,
  timeframe,
  availableStates,
  onClose,
}: {
  instrument:      string
  timeframe:       string
  availableStates: HmmStateInfo[]   // dari stateProfile hasil inspect
  onClose:         () => void
}) {
  const qc       = useQueryClient()
  const navigate = useNavigate()

  // ── Theory fields ──────────────────────────────────────────────────────────
  const [step,        setStep]        = useState<'form' | 'done'>('form')
  const [name,        setName]        = useState('')
  const [direction,   setDirection]   = useState<'LONG'|'SHORT'|'BOTH'>('LONG')
  const [threshold,   setThreshold]   = useState(10)
  const [minConf,     setMinConf]     = useState(60)
  const [description, setDescription] = useState('')
  const [createdId,   setCreatedId]   = useState('')
  const [error,       setError]       = useState('')
  const [saving,      setSaving]      = useState(false)

  // ── Pattern builder ────────────────────────────────────────────────────────
  const [buildSeq,    setBuildSeq]    = useState<number[]>([])
  const [buildCode,   setBuildCode]   = useState('')
  const [buildName,   setBuildName]   = useState('')
  const [buildDp,     setBuildDp]     = useState(10)
  const [buildReq,    setBuildReq]    = useState(true)
  const [patterns,    setPatterns]    = useState<DraftPattern[]>([])
  const [buildError,  setBuildError]  = useState('')

  const DIR_CFG = {
    LONG:  { color: 'var(--buy)',     bg: 'var(--buy-bg)',  label: '↑ Long' },
    SHORT: { color: 'var(--sell)',    bg: 'var(--sell-bg)', label: '↓ Short' },
    BOTH:  { color: 'var(--warning)', bg: 'var(--warn-bg)', label: '↕ Both' },
  }

  const addStateToSeq  = (s: number) => setBuildSeq(prev => [...prev, s])
  const removeFromSeq  = (i: number) => setBuildSeq(prev => prev.filter((_, idx) => idx !== i))
  const clearBuildForm = () => { setBuildSeq([]); setBuildCode(''); setBuildName(''); setBuildError('') }

  const addPatternToDraft = () => {
    if (buildSeq.length < 1) { setBuildError('Minimal 1 state'); return }
    if (!buildCode.trim())   { setBuildError('Code wajib diisi'); return }
    if (!buildName.trim())   { setBuildError('Name wajib diisi'); return }
    setPatterns(prev => [...prev, {
      seq: buildSeq, code: buildCode.trim(), name: buildName.trim(),
      decisionPts: buildDp, isRequired: buildReq,
    }])
    clearBuildForm()
  }

  const removePattern = (i: number) => setPatterns(prev => prev.filter((_, idx) => idx !== i))

  const handleCreate = async () => {
    if (!name.trim()) { setError('Nama theory wajib diisi'); return }
    setError(''); setSaving(true)
    try {
      const theory = await api.createTheory({
        name, description, instrument, direction,
        threshold, minConfidence: minConf,
      })
      // Save each draft pattern → DB, then add as factor
      for (let i = 0; i < patterns.length; i++) {
        const dp = patterns[i]
        const seqRepr = dp.seq.map(s => `S${s}`).join('')
        const saved = await api.createPattern({
          code: dp.code, name: dp.name, description: null,
          patternType: 'state_sequence', timeframe,
          stateSequence: JSON.stringify(dp.seq),
          stateSeqRepr: seqRepr,
        })
        await api.addFactor(theory.id, {
          factorCode: 'HMM_STATE_SEQ_MATCH',
          factorType: 'state_sequence_match',
          decisionPoint: dp.decisionPts,
          isRequired: dp.isRequired,
          timeframe, sortOrder: i,
          patternId: (saved as { id: string }).id,
        })
      }
      qc.invalidateQueries({ queryKey: ['theories', 'patterns'] })
      setCreatedId(theory.id)
      setStep('done')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Gagal membuat theory')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 24, width: '100%', maxWidth: 680,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)', maxHeight: '92vh', overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>Buat Theory Baru</div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>{instrument} · {timeframe}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={16} />
          </button>
        </div>

        {step === 'done' ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{
              width: 52, height: 52, borderRadius: '50%', background: 'var(--buy-bg)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
            }}>
              <Check size={24} style={{ color: 'var(--buy)' }} />
            </div>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6 }}>Theory Berhasil Dibuat!</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
              <span className="mono" style={{ color: 'var(--accent)' }}>{name}</span>
              {patterns.length > 0 && <> · {patterns.length} pattern tersimpan</>}
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn-secondary" onClick={onClose}>Tutup</button>
              <button className="btn-primary" onClick={() => { onClose(); navigate(`/theories/${createdId}`) }}
                style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                Lihat Theory <ArrowRight size={13} />
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* ── Theory Info ── */}
            <div className="form-group" style={{ marginBottom: 12 }}>
              <label className="form-label">Nama Theory <span style={{ color: 'var(--sell)' }}>*</span></label>
              <input className="form-input" value={name} autoFocus
                onChange={e => setName(e.target.value)}
                placeholder="misal: Reversal Bullish di Support M15" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Direction</label>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['LONG','SHORT','BOTH'] as const).map(d => {
                    const cfg = DIR_CFG[d]; const active = direction === d
                    return (
                      <button key={d} onClick={() => setDirection(d)} style={{
                        flex: 1, padding: '6px 0', fontSize: 11, fontWeight: 700,
                        borderRadius: 5, cursor: 'pointer',
                        border: `1px solid ${active ? cfg.color : 'var(--border)'}`,
                        background: active ? cfg.bg : 'transparent',
                        color: active ? cfg.color : 'var(--text-muted)', transition: 'all 0.12s',
                      }}>{cfg.label}</button>
                    )
                  })}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Score Threshold</label>
                <input type="number" className="form-input mono" value={threshold}
                  onChange={e => setThreshold(Number(e.target.value))} min={1} max={100} />
              </div>
              <div className="form-group">
                <label className="form-label">Min Win %</label>
                <input type="number" className="form-input mono" value={minConf}
                  onChange={e => setMinConf(Number(e.target.value))} min={50} max={100} step={0.5} />
              </div>
            </div>

            {/* ── Divider ── */}
            <div style={{ borderTop: '1px solid var(--border)', margin: '14px 0 16px' }} />
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.5px' }}>
              PATTERN BUILDER — klik state untuk tambah ke urutan
            </div>

            {/* ── State palette (from inspect) ── */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {(availableStates.length > 0 ? availableStates : Array.from({ length: 8 }, (_, i) => ({ state: i, label: `S${i}`, frequency: 0, features: [] }))).map(s => {
                const color = STATE_PALETTE[s.state % STATE_PALETTE.length]
                return (
                  <button
                    key={s.state}
                    onClick={() => addStateToSeq(s.state)}
                    title={s.label}
                    style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center',
                      padding: '6px 10px', borderRadius: 6, cursor: 'pointer',
                      background: `${color}18`, border: `1px solid ${color}50`,
                      color, transition: 'all 0.1s', minWidth: 60,
                    }}
                  >
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 13 }}>S{s.state}</span>
                    <span style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 1, textAlign: 'center', maxWidth: 70, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {s.label.replace(/^(Mixed State |S\d+ ?)/, '').slice(0, 14) || s.label.slice(0, 14)}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* ── Current sequence being built ── */}
            <div style={{
              background: 'var(--surface-2)', borderRadius: 8, padding: '12px 14px', marginBottom: 12,
              border: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 8 }}>
                Urutan sequence (klik state di atas untuk tambah, klik chip untuk hapus):
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', minHeight: 32 }}>
                {buildSeq.length === 0 ? (
                  <span style={{ color: 'var(--text-faint)', fontSize: 12, fontStyle: 'italic' }}>
                    Belum ada state dipilih…
                  </span>
                ) : buildSeq.map((s, i) => {
                  const color = STATE_PALETTE[s % STATE_PALETTE.length]
                  return (
                    <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {i > 0 && <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>→</span>}
                      <button
                        onClick={() => removeFromSeq(i)}
                        title="Hapus"
                        style={{
                          background: `${color}22`, border: `1px solid ${color}66`,
                          borderRadius: 4, padding: '3px 10px', cursor: 'pointer',
                          fontFamily: 'monospace', fontWeight: 700, fontSize: 13, color,
                        }}
                      >S{s}</button>
                    </span>
                  )
                })}
                {buildSeq.length > 0 && (
                  <button onClick={clearBuildForm}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-faint)', fontSize: 11, marginLeft: 4 }}>
                    reset
                  </button>
                )}
              </div>

              {/* Code + Name + controls */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 8, marginTop: 10, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Code</label>
                  <input className="form-input mono" value={buildCode}
                    onChange={e => setBuildCode(e.target.value)} placeholder="REVERSAL_BULL" style={{ fontSize: 12 }} />
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Nama Pattern</label>
                  <input className="form-input" value={buildName}
                    onChange={e => setBuildName(e.target.value)} placeholder="Reversal Bullish" style={{ fontSize: 12 }} />
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Pts</label>
                  <input type="number" className="form-input mono" value={buildDp}
                    onChange={e => setBuildDp(Number(e.target.value))} min={1} max={100}
                    style={{ width: 56, fontSize: 12 }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 1 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>
                    <input type="checkbox" checked={buildReq} onChange={e => setBuildReq(e.target.checked)} />
                    Required
                  </label>
                  <button className="btn-primary" onClick={addPatternToDraft}
                    style={{ fontSize: 12, padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Plus size={12} /> Tambah
                  </button>
                </div>
              </div>
              {buildError && <div style={{ color: 'var(--sell)', fontSize: 11, marginTop: 6 }}>{buildError}</div>}
            </div>

            {/* ── Pattern table ── */}
            {patterns.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                  Pattern yang akan ditambahkan ke theory ({patterns.length}):
                </div>
                <table className="data-table" style={{ fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th>Sequence</th>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Pts</th>
                      <th>Req</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {patterns.map((p, i) => (
                      <tr key={i}>
                        <td>
                          <div style={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
                            {p.seq.map((s, si) => {
                              const color = STATE_PALETTE[s % STATE_PALETTE.length]
                              return (
                                <span key={si} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                  {si > 0 && <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>→</span>}
                                  <span style={{
                                    background: `${color}22`, color, border: `1px solid ${color}55`,
                                    borderRadius: 3, padding: '1px 6px',
                                    fontFamily: 'monospace', fontWeight: 700, fontSize: 11,
                                  }}>S{s}</span>
                                </span>
                              )
                            })}
                          </div>
                        </td>
                        <td className="mono" style={{ color: 'var(--accent)', fontSize: 11 }}>{p.code}</td>
                        <td style={{ fontSize: 11 }}>{p.name}</td>
                        <td className="mono">{p.decisionPts}</td>
                        <td>
                          <span style={{
                            fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 3,
                            background: p.isRequired ? 'var(--buy-bg)' : 'var(--surface-2)',
                            color: p.isRequired ? 'var(--buy)' : 'var(--text-faint)',
                          }}>{p.isRequired ? 'YES' : 'NO'}</span>
                        </td>
                        <td>
                          <button onClick={() => removePattern(i)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-faint)' }}>
                            <X size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label">Deskripsi (opsional)</label>
              <textarea className="form-input" rows={2} value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Jelaskan setup, kondisi market, logika entry…" />
            </div>

            {error && <div className="alert-error" style={{ marginBottom: 12, fontSize: 12 }}>{error}</div>}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={onClose}>Batal</button>
              <button className="btn-primary" disabled={!name.trim() || saving} onClick={handleCreate}
                style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                {saving
                  ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Menyimpan…</>
                  : <><BookOpen size={13} /> Buat Theory {patterns.length > 0 ? `+ ${patterns.length} Pattern` : ''}</>
                }
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Auto-derive best-practice setup from HMM state profile ───────────────────
interface AutoSetup {
  direction:  'LONG' | 'SHORT' | 'BOTH'
  bullState:  HmmStateInfo | null
  bearState:  HmmStateInfo | null
  neutralState: HmmStateInfo | null
  patterns:   DraftPattern[]
  threshold:  number
  minConf:    number
}

function deriveAutoSetup(states: HmmStateInfo[]): AutoSetup {
  if (states.length === 0) {
    return { direction: 'BOTH', bullState: null, bearState: null, neutralState: null, patterns: [], threshold: 10, minConf: 62 }
  }

  const feat = (s: HmmStateInfo, name: string) =>
    s.features.find(f => f.name === name)?.value ?? 0

  const enriched = states.map(s => ({
    ...s,
    momentum: feat(s, 'momentum_z'),
    slope:    feat(s, 'htf_slope'),
    body:     feat(s, 'body_dom'),
    atr:      feat(s, 'ATR_pct'),
    // composite score: momentum × 0.6 + slope × 0.4
    score: feat(s, 'momentum_z') * 0.6 + feat(s, 'htf_slope') * 0.4,
  }))

  const sorted = [...enriched].sort((a, b) => b.score - a.score)
  const bullState = sorted[0]
  const bearState = sorted[sorted.length - 1]

  // Neutral = lowest |momentum|, excluding bull/bear extremes
  const neutralCandidates = enriched
    .filter(s => s.state !== bullState.state && s.state !== bearState.state)
    .sort((a, b) => Math.abs(a.momentum) - Math.abs(b.momentum))
  const neutralState = neutralCandidates[0] ?? null

  // Determine direction based on score spread
  const bullScore = bullState.score
  const bearScore = -bearState.score
  let direction: 'LONG' | 'SHORT' | 'BOTH' = 'BOTH'
  if (bullScore > 0.25 && bullScore > bearScore * 1.25) direction = 'LONG'
  else if (bearScore > 0.25 && bearScore > bullScore * 1.25) direction = 'SHORT'

  const patterns: DraftPattern[] = []
  const basePts = 10

  if (direction !== 'SHORT') {
    const seq = neutralState ? [neutralState.state, bullState.state] : [bullState.state]
    const seqStr = seq.map(s => `S${s}`).join('')
    patterns.push({
      seq,
      code: `AUTO_LONG_${seqStr}`,
      name: `Auto Long — ${neutralState ? `${neutralState.label} → ` : ''}${bullState.label}`,
      decisionPts: basePts,
      isRequired: true,
    })
  }

  if (direction !== 'LONG') {
    const seq = neutralState ? [neutralState.state, bearState.state] : [bearState.state]
    const seqStr = seq.map(s => `S${s}`).join('')
    patterns.push({
      seq,
      code: `AUTO_SHORT_${seqStr}`,
      name: `Auto Short — ${neutralState ? `${neutralState.label} → ` : ''}${bearState.label}`,
      decisionPts: basePts,
      isRequired: true,
    })
  }

  const threshold = Math.round(patterns.reduce((s, p) => s + p.decisionPts, 0) * 0.75)

  return {
    direction,
    bullState,
    bearState,
    neutralState,
    patterns,
    threshold: Math.max(threshold, 7),
    minConf: 62,
  }
}

// ── Auto Create Theory Modal ──────────────────────────────────────────────────
function AutoCreateTheoryModal({
  instrument,
  timeframe,
  availableStates,
  onClose,
}: {
  instrument:      string
  timeframe:       string
  availableStates: HmmStateInfo[]
  onClose:         () => void
}) {
  const qc       = useQueryClient()
  const navigate = useNavigate()

  const setup = deriveAutoSetup(availableStates)

  const [name,      setName]      = useState(`Auto Theory — ${instrument} ${timeframe}`)
  const [direction, setDirection] = useState<'LONG'|'SHORT'|'BOTH'>(setup.direction)
  const [threshold, setThreshold] = useState(setup.threshold)
  const [minConf,   setMinConf]   = useState(setup.minConf)
  const [saving,    setSaving]    = useState(false)
  const [error,     setError]     = useState('')
  const [createdId, setCreatedId] = useState('')

  const DIR_CFG = {
    LONG:  { color: 'var(--buy)',     bg: 'var(--buy-bg)',  label: '↑ Long' },
    SHORT: { color: 'var(--sell)',    bg: 'var(--sell-bg)', label: '↓ Short' },
    BOTH:  { color: 'var(--warning)', bg: 'var(--warn-bg)', label: '↕ Both' },
  }

  const handleCreate = async () => {
    if (!name.trim()) { setError('Nama theory wajib diisi'); return }
    if (setup.patterns.length === 0) { setError('Tidak ada pattern yang bisa digenerate. Inspect model dulu.'); return }
    setError(''); setSaving(true)
    try {
      const theory = await api.createTheory({
        name, description: `[Auto-generated] ${instrument} ${timeframe} · direction: ${direction}`,
        instrument, direction, threshold, minConfidence: minConf,
      })
      for (let i = 0; i < setup.patterns.length; i++) {
        const dp = setup.patterns[i]
        const seqRepr = dp.seq.map(s => `S${s}`).join('')
        const saved = await api.createPattern({
          code: dp.code, name: dp.name, description: null,
          patternType: 'state_sequence', timeframe,
          stateSequence: JSON.stringify(dp.seq),
          stateSeqRepr: seqRepr,
        })
        await api.addFactor(theory.id, {
          factorCode: 'HMM_STATE_SEQ_MATCH',
          factorType: 'state_sequence_match',
          decisionPoint: dp.decisionPts,
          isRequired: dp.isRequired,
          timeframe, sortOrder: i,
          patternId: (saved as { id: string }).id,
        })
      }
      qc.invalidateQueries({ queryKey: ['theories', 'patterns'] })
      setCreatedId(theory.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Gagal membuat theory')
    } finally {
      setSaving(false)
    }
  }

  const stateChip = (s: HmmStateInfo | null, role: string, roleColor: string) => {
    if (!s) return null
    const color = STATE_PALETTE[s.state % STATE_PALETTE.length]
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 6, background: `${color}10`, border: `1px solid ${color}30` }}>
        <span style={{ fontSize: 9, fontWeight: 700, color: roleColor, textTransform: 'uppercase', letterSpacing: '0.5px', minWidth: 44 }}>{role}</span>
        <span style={{ background: color, color: '#fff', borderRadius: 3, padding: '1px 7px', fontSize: 11, fontWeight: 700, fontFamily: 'monospace' }}>S{s.state}</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>{s.label}</span>
        <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{s.frequency}%</span>
      </div>
    )
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, width: '100%', maxWidth: 560, boxShadow: '0 24px 64px rgba(0,0,0,0.5)', maxHeight: '92vh', overflowY: 'auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>⚡ Auto Create Theory</div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>{instrument} · {timeframe} · {availableStates.length} states</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={16} /></button>
        </div>

        {createdId ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--buy-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px' }}>
              <Check size={24} style={{ color: 'var(--buy)' }} />
            </div>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6 }}>Theory Berhasil Dibuat!</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
              <span className="mono" style={{ color: 'var(--accent)' }}>{name}</span>
              {' '}· {setup.patterns.length} pattern tersimpan
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn-secondary" onClick={onClose}>Tutup</button>
              <button className="btn-primary" onClick={() => { onClose(); navigate(`/theories/${createdId}`) }} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                Lihat Theory <ArrowRight size={13} />
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* State role analysis */}
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.5px' }}>ANALISIS STATE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
              {stateChip(setup.bullState, 'Bull ↑', 'var(--buy)')}
              {stateChip(setup.bearState, 'Bear ↓', 'var(--sell)')}
              {stateChip(setup.neutralState, 'Neutral', 'var(--text-muted)')}
            </div>

            {/* Auto-generated patterns preview */}
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.5px' }}>PATTERN YANG AKAN DIBUAT</div>
            {setup.patterns.length === 0 ? (
              <div style={{ color: 'var(--sell)', fontSize: 12, marginBottom: 14 }}>
                Tidak cukup data state. Lakukan Inspect States terlebih dahulu.
              </div>
            ) : (
              <div style={{ marginBottom: 18 }}>
                {setup.patterns.map((p, i) => {
                  const isLong = p.code.includes('LONG')
                  const color = isLong ? 'var(--buy)' : 'var(--sell)'
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', marginBottom: 5 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 36 }}>{isLong ? '↑ LONG' : '↓ SHORT'}</span>
                      <div style={{ display: 'flex', gap: 3, alignItems: 'center', flex: 1 }}>
                        {p.seq.map((s, si) => {
                          const c = STATE_PALETTE[s % STATE_PALETTE.length]
                          return (
                            <span key={si} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                              {si > 0 && <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>→</span>}
                              <span style={{ background: `${c}22`, color: c, border: `1px solid ${c}55`, borderRadius: 3, padding: '1px 6px', fontFamily: 'monospace', fontWeight: 700, fontSize: 11 }}>S{s}</span>
                            </span>
                          )
                        })}
                      </div>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--accent)' }}>{p.code}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{p.decisionPts} pts</span>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Theory name */}
            <div className="form-group" style={{ marginBottom: 12 }}>
              <label className="form-label">Nama Theory <span style={{ color: 'var(--sell)' }}>*</span></label>
              <input className="form-input" value={name} autoFocus onChange={e => setName(e.target.value)} />
            </div>

            {/* Direction + params */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 10, marginBottom: 16, alignItems: 'flex-end' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Direction</label>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['LONG','SHORT','BOTH'] as const).map(d => {
                    const cfg = DIR_CFG[d]; const active = direction === d
                    return (
                      <button key={d} onClick={() => setDirection(d)} style={{
                        flex: 1, padding: '6px 0', fontSize: 11, fontWeight: 700, borderRadius: 5, cursor: 'pointer',
                        border: `1px solid ${active ? cfg.color : 'var(--border)'}`,
                        background: active ? cfg.bg : 'transparent',
                        color: active ? cfg.color : 'var(--text-muted)', transition: 'all 0.12s',
                      }}>{cfg.label}</button>
                    )
                  })}
                </div>
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Score</label>
                <input type="number" className="form-input mono" value={threshold} onChange={e => setThreshold(Number(e.target.value))} min={1} max={100} style={{ width: 64 }} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Win %</label>
                <input type="number" className="form-input mono" value={minConf} onChange={e => setMinConf(Number(e.target.value))} min={50} max={100} step={0.5} style={{ width: 64 }} />
              </div>
            </div>

            {error && <div className="alert-error" style={{ marginBottom: 12, fontSize: 12 }}>{error}</div>}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={onClose}>Batal</button>
              <button
                className="btn-primary"
                disabled={!name.trim() || saving || setup.patterns.length === 0}
                onClick={handleCreate}
                style={{ display: 'flex', alignItems: 'center', gap: 5 }}
              >
                {saving
                  ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Membuat…</>
                  : <>⚡ Auto Create Theory</>
                }
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function HMMModels() {
  const qc = useQueryClient()
  const [instrument, setInstrument] = useState('XAUUSDm')
  const [timeframe,  setTimeframe]  = useState('M15')
  const [inspectInst, setInspectInst] = useState('XAUUSDm')
  const [inspectTf,   setInspectTf]   = useState('M15')
  const [inspectEnabled, setInspectEnabled] = useState(false)
  const [patternModal,  setPatternModal]  = useState<number | null>(null)
  const [theoryModal,   setTheoryModal]   = useState(false)
  const [autoTheoryModal, setAutoTheoryModal] = useState(false)
  const [dateFrom,       setDateFrom]       = useState('2025-01-01')
  const [dateTo,         setDateTo]         = useState(new Date().toISOString().slice(0, 10))
  const [trainDataSource, setTrainDataSource] = useState<'db' | 'mt5'>('db')

  const { data: models = [], isLoading } = useQuery({
    queryKey: ['hmm-models'],
    queryFn: api.listHmmModels,
  })

  const { data: ohlcStatus, isLoading: ohlcLoading, refetch: refetchOhlc } = useQuery({
    queryKey: ['ohlc-data-status'],
    queryFn: api.ohlcDataStatus,
    refetchInterval: 15_000,
  })

  const train = useMutation({
    mutationFn: () => api.trainHmm({
      instrument, timeframe,
      dateFrom: new Date(dateFrom),
      dateTo: new Date(dateTo),
      dataSource: trainDataSource,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hmm-models'] }),
  })

  const syncAll = useMutation({
    mutationFn: () => api.ohlcDataSync(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ohlc-data-status'] })
      refetchOhlc()
    },
  })

  const syncOne = useMutation({
    mutationFn: ({ inst, tf }: { inst: string; tf: string }) =>
      api.ohlcDataSync(inst, tf),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ohlc-data-status'] }),
  })

  const syncs: OhlcSyncStatus[] = ohlcStatus?.syncs ?? []

  const { data: stateProfile, isLoading: profileLoading, refetch: refetchProfile } = useQuery({
    queryKey: ['hmm-state-profile', inspectInst, inspectTf],
    queryFn: () => api.hmmStateProfile(inspectInst, inspectTf),
    enabled: inspectEnabled,
    staleTime: 60_000,
  })

  const handleUseInPattern = (state: number) => {
    setPatternModal(state)
  }

  return (
    <div className="page-container">
      {patternModal !== null && (
        <CreatePatternModal
          initialState={patternModal}
          timeframe={inspectTf}
          onClose={() => setPatternModal(null)}
        />
      )}
      {theoryModal && (
        <CreateTheoryModal
          instrument={inspectInst}
          timeframe={inspectTf}
          availableStates={stateProfile?.states ?? []}
          onClose={() => setTheoryModal(false)}
        />
      )}
      {autoTheoryModal && (
        <AutoCreateTheoryModal
          instrument={inspectInst}
          timeframe={inspectTf}
          availableStates={stateProfile?.states ?? []}
          onClose={() => setAutoTheoryModal(false)}
        />
      )}
      <div className="page-topbar">
        <h1 className="page-heading">HMM Models</h1>
        {models.length > 0 && (
          <span className="badge badge--neutral">
            {models.length} model{models.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── OHLC Data Status ────────────────────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={15} style={{ color: 'var(--accent)' }} />
            <span className="section-title" style={{ margin: 0 }}>OHLC Data Store</span>
          </div>
          <button
            onClick={() => syncAll.mutate()}
            disabled={syncAll.isPending}
            className="btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12 }}
            title="Sync semua timeframe sekarang"
          >
            <RefreshCw size={12} className={syncAll.isPending ? 'animate-spin' : ''} />
            {syncAll.isPending ? 'Syncing…' : 'Sync All'}
          </button>
        </div>

        {ohlcLoading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading data status…</div>
        ) : syncs.length === 0 ? (
          <div style={{
            padding: '16px', textAlign: 'center', borderRadius: 6,
            background: 'var(--surface-2)', color: 'var(--text-muted)', fontSize: 13,
          }}>
            <Database size={24} style={{ opacity: 0.4, marginBottom: 8, display: 'block', margin: '0 auto 8px' }} />
            Belum ada data tersimpan. Sidecar Python akan mulai sync otomatis saat startup.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th>TF</th>
                  <th>Total Bars</th>
                  <th>Last Bar</th>
                  <th>Last Sync</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {syncs.map(s => (
                  <tr key={`${s.instrument}-${s.timeframe}`}>
                    <td className="mono" style={{ fontWeight: 700 }}>{s.instrument}</td>
                    <td className="mono" style={{ color: 'var(--accent)' }}>{s.timeframe}</td>
                    <td className="mono" style={{ fontWeight: 600 }}>
                      {s.total_bars.toLocaleString()}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {s.last_bar ? new Date(s.last_bar).toLocaleString() : '—'}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {s.last_sync ? new Date(s.last_sync).toLocaleString() : '—'}
                    </td>
                    <td><SyncStatusBadge status={s.status} /></td>
                    <td>
                      <button
                        onClick={() => syncOne.mutate({ inst: s.instrument, tf: s.timeframe })}
                        disabled={syncOne.isPending}
                        title={`Sync ${s.instrument} ${s.timeframe}`}
                        style={{
                          fontSize: 11, padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                          background: 'var(--surface-2)', border: '1px solid var(--border)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <RefreshCw size={10} style={{ display: 'inline', marginRight: 3 }} />
                        Sync
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {syncAll.isSuccess && (
          <div className="alert-success" style={{ marginTop: 10, fontSize: 12 }}>
            Sync selesai — +{syncAll.data?.total_bars_added ?? 0} bars baru
          </div>
        )}
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-faint)' }}>
          Auto-sync aktif saat sidecar berjalan: M1=1min · M5=5min · M15=15min · M30=30min · H1=60min
        </div>
      </div>

      {/* ── Train form ──────────────────────────────────────────────────── */}
      <div className="card">
        <div className="section-title">Train New Model</div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '12px',
            alignItems: 'end',
          }}
        >
          <div className="form-group">
            <label className="form-label">Instrument</label>
            {trainDataSource === 'mt5' ? (
              <input
                className="form-input mono"
                value={instrument}
                onChange={e => setInstrument(e.target.value)}
                placeholder="e.g. XAUUSD, EURUSD"
              />
            ) : (
              <select className="form-input" value={instrument} onChange={e => setInstrument(e.target.value)}>
                {['XAUUSDm', 'XAUUSDc', 'XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100'].map(i => <option key={i}>{i}</option>)}
              </select>
            )}
          </div>
          <div className="form-group">
            <label className="form-label">Timeframe</label>
            <select className="form-input" value={timeframe} onChange={e => setTimeframe(e.target.value)}>
              {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map(t => <option key={t}>{t}</option>)}
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
            <div style={{ display: 'flex', gap: 5 }}>
              {(['db','mt5'] as const).map(src => (
                <button key={src} type="button" onClick={() => setTrainDataSource(src)} style={{
                  flex: 1, padding: '6px 0', fontSize: 11, fontWeight: 700,
                  borderRadius: 4, cursor: 'pointer', border: '1px solid', transition: 'all 0.15s',
                  borderColor: trainDataSource === src ? 'var(--accent)' : 'var(--border)',
                  background:  trainDataSource === src ? 'var(--accent)20' : 'transparent',
                  color:       trainDataSource === src ? 'var(--accent)' : 'var(--text-muted)',
                }}>
                  {src === 'db' ? '🗄 DB' : '📡 MT5'}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
              {trainDataSource === 'db' ? 'PostgreSQL (default)' : 'Langsung dari MT5'}
            </div>
          </div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <button
              className="btn-primary"
              disabled={train.isPending}
              onClick={() => train.mutate()}
              style={{ width: '100%' }}
            >
              {train.isPending
                ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Queuing…</>
                : <><Cpu size={13} /> Train Model</>
              }
            </button>
          </div>
        </div>

        {train.isSuccess && (
          <div className="alert-success" style={{ marginTop: '12px' }}>
            Training job queued · <span className="mono font-semibold">{train.data}</span>
          </div>
        )}

        <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-faint)', lineHeight: 1.6 }}>
          BIC-based K selection (K = 4–8). DB = gunakan OHLC cache PostgreSQL, MT5 = fetch langsung dari terminal.
          Training runs as background job via Hangfire.
        </div>
      </div>

      {/* ── State Inspector ─────────────────────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Search size={15} style={{ color: 'var(--accent)' }} />
            <span className="section-title" style={{ margin: 0 }}>State Inspector</span>
            <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
              — lihat karakter tiap state untuk membuat pattern
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          <div className="form-group" style={{ minWidth: 130, margin: 0 }}>
            <label className="form-label">Instrument</label>
            <select className="form-input" value={inspectInst} onChange={e => setInspectInst(e.target.value)}>
              {['XAUUSDm', 'XAUUSDc', 'XAUUSD', 'EURUSD', 'GBPUSD'].map(i => <option key={i}>{i}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ minWidth: 100, margin: 0 }}>
            <label className="form-label">Timeframe</label>
            <select className="form-input" value={inspectTf} onChange={e => setInspectTf(e.target.value)}>
              {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <button
            className="btn-primary"
            onClick={() => { setInspectEnabled(true); setTimeout(() => refetchProfile(), 50) }}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <Search size={13} /> Inspect States
          </button>
          <button
            className="btn-secondary"
            onClick={() => setTheoryModal(true)}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <BookOpen size={13} /> Buat Theory
          </button>
          <button
            className="btn-primary"
            disabled={!stateProfile}
            onClick={() => setAutoTheoryModal(true)}
            title={!stateProfile ? 'Inspect States dulu untuk enable Auto Create' : 'Generate theory otomatis dari analisis HMM'}
            style={{ display: 'flex', alignItems: 'center', gap: 5, opacity: stateProfile ? 1 : 0.45 }}
          >
            ⚡ Auto Create Theory
          </button>
          {stateProfile && (
            <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
              Model: <span className="mono">{stateProfile.model_version}</span> · {stateProfile.n_states} states
            </span>
          )}
        </div>

        {profileLoading && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Menganalisa state model…</div>
        )}

        {stateProfile && !profileLoading && (
          <>
            {/* Recent sequence */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                Sequence 60 Bar Terakhir
              </div>
              <RecentSequence bars={stateProfile.recent_sequence} />
            </div>

            {/* State cards grid */}
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 10 }}>
              Profil Tiap State — klik "Gunakan di Pattern" untuk langsung buat pattern
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 10,
            }}>
              {stateProfile.states.map(s => (
                <StateCard key={s.state} info={s} onUse={handleUseInPattern} />
              ))}
            </div>

            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-faint)', lineHeight: 1.7 }}>
              <strong>Cara baca:</strong> ATR_pct (volatilitas), momentum_z (arah & kekuatan, + = bullish),
              swing_prox (kedekatan ke S/R, tinggi = dekat level), body_dom (kekuatan candle),
              htf_slope (arah HTF, + = uptrend), liq_prox (dekat zona likuiditas).
            </div>
          </>
        )}

        {!inspectEnabled && (
          <div style={{
            padding: '20px', textAlign: 'center', color: 'var(--text-faint)', fontSize: 13,
            background: 'var(--surface-2)', borderRadius: 6,
          }}>
            Pilih instrument & timeframe lalu klik <strong>Inspect States</strong> untuk melihat karakter tiap state HMM.
          </div>
        )}
      </div>

      {/* ── Models table ────────────────────────────────────────────────── */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Instrument</th>
              <th scope="col">TF</th>
              <th scope="col">K States</th>
              <th scope="col">BIC Score</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} style={{ padding: '12px 14px' }}>
                      <div className="skeleton" style={{ height: '13px', width: j === 0 ? '80px' : '60px' }} />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!isLoading && models.map(m => (
              <tr key={m.id}>
                <td className="mono" style={{ color: 'var(--accent)', fontWeight: 700 }}>{m.version}</td>
                <td className="mono" style={{ fontWeight: 600 }}>{m.instrument}</td>
                <td className="mono" style={{ color: 'var(--text-muted)' }}>{m.timeframe}</td>
                <td className="mono" style={{ fontWeight: 600 }}>{m.nStates}</td>
                <td className="mono" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                  {m.bicScore?.toFixed(2) ?? '—'}
                </td>
                <td>
                  <span className={`badge ${m.isActive ? 'badge--buy' : 'badge--neutral'}`}>
                    {m.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
            {!isLoading && models.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <div className="empty-state">
                    <BarChart2 size={32} style={{ color: 'var(--text-faint)', opacity: 0.5 }} aria-hidden="true" />
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No trained models yet</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>
                      Configure parameters above and click Train Model.
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
