import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { api, type CreateTheoryBody } from '../lib/api'
import { ArrowLeft, BookOpen } from 'lucide-react'

const INSTRUMENTS = ['XAUUSDm', 'XAUUSDc', 'XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'NAS100']
const TIMEFRAMES  = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
const DIRECTIONS  = ['LONG', 'SHORT', 'BOTH']

const DIRECTION_CONFIG = {
  LONG:  { color: 'var(--buy)',     bg: 'var(--buy-bg)',  label: 'Long Only' },
  SHORT: { color: 'var(--sell)',    bg: 'var(--sell-bg)', label: 'Short Only' },
  BOTH:  { color: 'var(--warning)', bg: 'var(--warn-bg)', label: 'Both Directions' },
}

export default function TheoryBuilder() {
  const [form, setForm] = useState<CreateTheoryBody>({
    name:          '',
    description:   '',
    instrument:    'XAUUSDm',
    direction:     'LONG',
    threshold:     10,
    minConfidence: 60,
  })

  const qc       = useQueryClient()
  const navigate = useNavigate()

  const mutation = useMutation({
    mutationFn: api.createTheory,
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ['theories'] })
      navigate(`/theories/${t.id}`)
    },
  })

  const set = (field: keyof CreateTheoryBody) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm(f => ({ ...f, [field]: e.target.value }))

  const dirCfg = DIRECTION_CONFIG[form.direction as keyof typeof DIRECTION_CONFIG]

  return (
    <div className="page-container" style={{ maxWidth: '760px' }}>
      {/* Header */}
      <div className="page-topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Link
            to="/theories"
            className="btn-secondary"
            style={{ height: '32px', padding: '0 10px', fontSize: '12px', gap: '4px' }}
          >
            <ArrowLeft size={13} /> Theories
          </Link>
          <h1 className="page-heading">Theory Builder</h1>
        </div>
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Theory name */}
        <div className="form-group">
          <label className="form-label" htmlFor="theory-name">Theory Name</label>
          <input
            id="theory-name"
            className="form-input"
            value={form.name}
            onChange={set('name')}
            placeholder="e.g. Break & Retest Bullish — XAUUSD H1"
            autoFocus
          />
        </div>

        {/* Instrument / Direction / Default TF */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '12px',
          }}
        >
          <div className="form-group">
            <label className="form-label" htmlFor="theory-instrument">Instrument</label>
            <select
              id="theory-instrument"
              className="form-input"
              value={form.instrument}
              onChange={set('instrument')}
            >
              {INSTRUMENTS.map(i => <option key={i}>{i}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Direction</label>
            <div style={{ display: 'flex', gap: '6px' }}>
              {DIRECTIONS.map(d => {
                const cfg = DIRECTION_CONFIG[d as keyof typeof DIRECTION_CONFIG]
                const isActive = form.direction === d
                return (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, direction: d }))}
                    style={{
                      flex: 1,
                      height: '36px',
                      border: `1px solid ${isActive ? cfg.color : 'var(--border)'}`,
                      borderRadius: 'var(--radius-md)',
                      background: isActive ? cfg.bg : 'transparent',
                      color: isActive ? cfg.color : 'var(--text-muted)',
                      fontSize: '11px',
                      fontWeight: isActive ? 700 : 500,
                      cursor: 'pointer',
                      letterSpacing: '0.3px',
                      transition: 'all 0.12s ease',
                    }}
                  >
                    {d}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="theory-tf">Default Timeframe</label>
            <select
              id="theory-tf"
              className="form-input"
            >
              {TIMEFRAMES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>

        {/* Score threshold / Min confidence */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
          }}
        >
          <div className="form-group">
            <label className="form-label" htmlFor="theory-threshold">
              Score Threshold
              <span style={{ marginLeft: '6px', color: 'var(--text-faint)', fontWeight: 400 }}>
                (signals above this score are emitted)
              </span>
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                id="theory-threshold"
                type="number"
                className="form-input mono"
                value={form.threshold}
                onChange={set('threshold')}
                min={1}
                max={100}
                style={{ maxWidth: '100px' }}
              />
              <span className="mono" style={{ fontSize: '13px', color: 'var(--accent)', fontWeight: 700 }}>
                {form.threshold}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="theory-minconf">
              Min P(WIN) %
              <span style={{ marginLeft: '6px', color: 'var(--text-faint)', fontWeight: 400 }}>
                (minimum Bayesian win probability)
              </span>
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                id="theory-minconf"
                type="number"
                className="form-input mono"
                value={form.minConfidence}
                onChange={set('minConfidence')}
                min={50}
                max={100}
                step={0.5}
                style={{ maxWidth: '100px' }}
              />
              <span className="mono" style={{ fontSize: '13px', color: 'var(--buy)', fontWeight: 700 }}>
                {form.minConfidence}%
              </span>
            </div>
          </div>
        </div>

        {/* Description */}
        <div className="form-group">
          <label className="form-label" htmlFor="theory-desc">Description</label>
          <textarea
            id="theory-desc"
            className="form-input"
            rows={3}
            value={form.description}
            onChange={set('description')}
            placeholder="Describe the setup, market conditions, and entry logic…"
          />
        </div>

        {/* Direction badge preview */}
        {form.direction && dirCfg && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: dirCfg.bg,
              border: `1px solid ${dirCfg.color}30`,
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '13px',
            }}
          >
            <span style={{ color: dirCfg.color, fontWeight: 700 }}>{dirCfg.label}</span>
            <span style={{ color: 'var(--text-muted)' }}>·</span>
            <span style={{ color: 'var(--text-muted)' }}>{form.instrument}</span>
            {form.name && (
              <>
                <span style={{ color: 'var(--text-muted)' }}>·</span>
                <span style={{ color: 'var(--text)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {form.name}
                </span>
              </>
            )}
          </div>
        )}

        {mutation.isError && (
          <div className="alert-error">{String(mutation.error)}</div>
        )}

        <button
          className="btn-primary"
          style={{ width: '100%', height: '40px', fontSize: '14px' }}
          disabled={!form.name || mutation.isPending}
          onClick={() => mutation.mutate(form)}
        >
          {mutation.isPending
            ? <><span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} /> Creating…</>
            : <><BookOpen size={15} /> Create Theory</>
          }
        </button>
      </div>

      <div style={{ fontSize: '12px', color: 'var(--text-faint)', lineHeight: 1.7 }}>
        After creation, add factors (C-Codes + HMM state sequence) to define your entry conditions.
        You can then backtest and activate the theory for live signal monitoring.
      </div>
    </div>
  )
}
