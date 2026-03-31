import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type Theory } from '../lib/api'
import { Link } from 'react-router-dom'
import { Plus, ClipboardList, Trash2 } from 'lucide-react'
import { useState, useMemo } from 'react'

type SortKey = 'newest' | 'oldest' | 'az' | 'za'

function TheoryRow({ t, onDelete }: { t: Theory; onDelete: (id: string) => void }) {
  const dirColor =
    t.direction === 'LONG'  ? 'var(--buy)'     :
    t.direction === 'SHORT' ? 'var(--sell)'    : 'var(--warning)'

  const dirBg =
    t.direction === 'LONG'  ? 'var(--buy-bg)'  :
    t.direction === 'SHORT' ? 'var(--sell-bg)' : 'var(--warn-bg)'

  return (
    <div className="card-sm" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      {/* Left: name + meta — clickable */}
      <Link
        to={`/theories/${t.id}`}
        style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}
      >
        <span className={t.isActive ? 'dot dot--live' : 'dot dot--muted'} title={t.isActive ? 'Active' : 'Inactive'} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: '14px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {t.name}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {t.instrument} · v{t.version}
          </div>
        </div>
      </Link>

      {/* Right: badges + delete */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
        <span className="badge" style={{ background: dirBg, color: dirColor, border: `1px solid ${dirColor}30` }}>
          {t.direction}
        </span>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Threshold</div>
            <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>{t.threshold}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Min P</div>
            <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent)' }}>{t.minConfidence}%</div>
          </div>
        </div>
        <button
          onClick={() => onDelete(t.id)}
          className="btn-icon-danger"
          title="Delete theory"
          style={{ marginLeft: 4 }}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="card-sm" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pointerEvents: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%' }} />
        <div>
          <div className="skeleton" style={{ width: '180px', height: '14px', marginBottom: '6px' }} />
          <div className="skeleton" style={{ width: '100px', height: '11px' }} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '10px' }}>
        <div className="skeleton" style={{ width: '60px', height: '22px', borderRadius: '999px' }} />
        <div className="skeleton" style={{ width: '80px', height: '34px' }} />
      </div>
    </div>
  )
}

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'newest', label: 'Terbaru' },
  { key: 'oldest', label: 'Terlama' },
  { key: 'az',     label: 'A → Z'  },
  { key: 'za',     label: 'Z → A'  },
]

export default function Theories() {
  const qc = useQueryClient()
  const [sort, setSort] = useState<SortKey>('newest')

  const { data: theories = [], isLoading } = useQuery({
    queryKey: ['theories'],
    queryFn: api.listTheories,
  })

  const deleteMut = useMutation({
    mutationFn: api.deleteTheory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['theories'] }),
  })

  function handleDelete(id: string) {
    if (!window.confirm('Hapus theory ini? Semua backtest & factor terkait ikut terhapus.')) return
    deleteMut.mutate(id)
  }

  const sorted = useMemo(() => {
    const list = [...theories]
    if (sort === 'newest') return list.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    if (sort === 'oldest') return list.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
    if (sort === 'az')     return list.sort((a, b) => a.name.localeCompare(b.name))
    if (sort === 'za')     return list.sort((a, b) => b.name.localeCompare(a.name))
    return list
  }, [theories, sort])

  return (
    <div className="page-container">
      <div className="page-topbar">
        <h1 className="page-heading">Theories</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Sort buttons */}
          <div style={{ display: 'flex', gap: 4 }}>
            {SORT_OPTIONS.map(opt => (
              <button
                key={opt.key}
                onClick={() => setSort(opt.key)}
                style={{
                  padding: '4px 10px', fontSize: 11, fontWeight: 600, borderRadius: 4,
                  cursor: 'pointer', border: '1px solid',
                  borderColor: sort === opt.key ? 'var(--accent)' : 'var(--border)',
                  background:  sort === opt.key ? 'var(--accent)20' : 'transparent',
                  color:       sort === opt.key ? 'var(--accent)'   : 'var(--text-muted)',
                  transition: 'all 0.12s',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Link to="/builder" className="btn-primary">
            <Plus size={15} aria-hidden="true" /> New Theory
          </Link>
        </div>
      </div>

      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)}
        </div>
      )}

      {!isLoading && sorted.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {sorted.map(t => <TheoryRow key={t.id} t={t} onDelete={handleDelete} />)}
        </div>
      )}

      {!isLoading && theories.length === 0 && (
        <div className="empty-state">
          <ClipboardList size={40} style={{ color: 'var(--text-faint)', opacity: 0.5 }} aria-hidden="true" />
          <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No theories yet</div>
          <div style={{ fontSize: '13px', color: 'var(--text-faint)' }}>Create your first trading theory to get started.</div>
          <Link to="/builder" className="btn-primary" style={{ marginTop: '8px' }}>
            <Plus size={15} /> Create Theory
          </Link>
        </div>
      )}
    </div>
  )
}
