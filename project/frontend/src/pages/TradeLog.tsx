import { useQuery } from '@tanstack/react-query'
import { api, type Trade } from '../lib/api'
import { useState } from 'react'
import { ListOrdered, ChevronLeft, ChevronRight } from 'lucide-react'

function OutcomeBadge({ outcome }: { outcome?: string }) {
  if (!outcome) return <span style={{ color: 'var(--text-faint)' }}>—</span>
  const map: Record<string, string> = {
    WIN:  'badge--buy',
    LOSS: 'badge--sell',
  }
  return (
    <span className={`badge ${map[outcome] ?? 'badge--warn'}`}>
      {outcome}
    </span>
  )
}

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === 'LONG'
  return (
    <span
      className="mono"
      style={{
        fontWeight: 700,
        fontSize: '12px',
        color: isLong ? 'var(--buy)' : 'var(--sell)',
        letterSpacing: '0.3px',
      }}
    >
      {direction}
    </span>
  )
}

export default function TradeLog() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['trades', page],
    queryFn: () => api.listTrades(page),
  })

  const { data: recap } = useQuery({
    queryKey: ['trade-recap'],
    queryFn: () => api.getRecap(),
  })

  const totalPages = data ? Math.ceil(data.total / data.pageSize) : 0

  return (
    <div className="page-container">
      <div className="page-topbar">
        <h1 className="page-heading">Trade Log</h1>
        {data && (
          <span className="badge badge--neutral">
            {data.total.toLocaleString()} trades
          </span>
        )}
      </div>

      {/* Stats row */}
      {recap && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
            gap: '10px',
          }}
        >
          <div className="stat-card">
            <div className="stat-label">Total</div>
            <div className="stat-value">{recap.total.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Wins</div>
            <div className="stat-value" style={{ color: 'var(--buy)' }}>{recap.wins}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Losses</div>
            <div className="stat-value" style={{ color: 'var(--sell)' }}>{recap.losses}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Win Rate</div>
            <div className="stat-value" style={{ color: 'var(--accent)' }}>{recap.winRate}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Pips</div>
            <div
              className="stat-value"
              style={{ color: recap.totalPips >= 0 ? 'var(--buy)' : 'var(--sell)' }}
            >
              {recap.totalPips >= 0 ? '+' : ''}{recap.totalPips.toFixed(1)}
            </div>
          </div>
        </div>
      )}

      {/* Trade table */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Instrument</th>
              <th scope="col">TF</th>
              <th scope="col">Direction</th>
              <th scope="col">Score</th>
              <th scope="col">P(WIN)</th>
              <th scope="col">Outcome</th>
              <th scope="col">Pips</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} style={{ padding: '12px 14px' }}>
                      <div className="skeleton" style={{ height: '13px', width: j === 0 ? '120px' : j === 1 ? '70px' : '50px' }} />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!isLoading && data?.items.map((t: Trade) => (
              <tr key={t.id}>
                <td style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {new Date(t.signalTime).toLocaleString()}
                </td>
                <td className="mono" style={{ fontWeight: 600 }}>{t.instrument}</td>
                <td className="mono" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>{t.timeframe}</td>
                <td><DirectionBadge direction={t.direction} /></td>
                <td className="mono" style={{ fontWeight: 600 }}>{t.compositeScore}</td>
                <td className="mono" style={{ color: 'var(--accent)' }}>
                  {t.pWinAtSignal ? `${(t.pWinAtSignal * 100).toFixed(1)}%` : '—'}
                </td>
                <td><OutcomeBadge outcome={t.outcome} /></td>
                <td
                  className="mono"
                  style={{
                    fontWeight: 600,
                    color: (t.pnlPips ?? 0) >= 0 ? 'var(--buy)' : 'var(--sell)',
                    fontSize: '12px',
                  }}
                >
                  {t.pnlPips !== undefined
                    ? `${t.pnlPips >= 0 ? '+' : ''}${t.pnlPips.toFixed(1)}`
                    : '—'}
                </td>
              </tr>
            ))}
            {!isLoading && (!data?.items || data.items.length === 0) && (
              <tr>
                <td colSpan={8}>
                  <div className="empty-state">
                    <ListOrdered size={32} style={{ color: 'var(--text-faint)', opacity: 0.5 }} aria-hidden="true" />
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No trades yet</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>
                      Trade logs will appear here after the engine generates signals.
                    </div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > data.pageSize && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '12px',
            color: 'var(--text-muted)',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <span>
            Page <span style={{ fontWeight: 600, color: 'var(--text)' }}>{page}</span> of {totalPages}
            {' '}· {data.total.toLocaleString()} total
          </span>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary"
              style={{ height: '30px', padding: '0 10px', fontSize: '12px', gap: '4px' }}
            >
              <ChevronLeft size={13} /> Prev
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= totalPages}
              className="btn-secondary"
              style={{ height: '30px', padding: '0 10px', fontSize: '12px', gap: '4px' }}
            >
              Next <ChevronRight size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
