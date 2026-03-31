import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type MT5AccountInfo, type MT5Position, type MT5OrderResult } from '../lib/api'
import React, { useState } from 'react'
import { Wifi, WifiOff, TrendingUp, TrendingDown, X } from 'lucide-react'

// inputStyle replaced by .form-input class

// ── Account Panel ─────────────────────────────────────────────────────────────

function AccountStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="mono text-sm font-semibold" style={{ color: color ?? 'var(--text)' }}>{value}</div>
    </div>
  )
}

function AccountPanel({
  account,
  connected,
  onConnect,
  onDisconnect,
}: {
  account: MT5AccountInfo | undefined
  connected: boolean
  onConnect: (login: number, password: string, server: string) => void
  onDisconnect: () => void
}) {
  const [login,    setLogin]    = useState('')
  const [password, setPassword] = useState('')
  const [server,   setServer]   = useState('MetaQuotes-Demo')

  if (!connected || !account) {
    return (
      <div className="card">
        <div className="flex items-center gap-2" style={{ marginBottom: '16px' }}>
          <WifiOff size={16} style={{ color: 'var(--text-faint)' }} />
          <span className="font-medium" style={{ color: 'var(--text)' }}>Connect to MT5</span>
        </div>
        <div className="flex gap-3 flex-wrap">
          <div className="form-group" style={{ flex: '1', minWidth: '120px' }}>
            <label className="form-label">Login</label>
            <input
              type="number"
              placeholder="Login"
              className="form-input"
              value={login}
              onChange={e => setLogin(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ flex: '1', minWidth: '120px' }}>
            <label className="form-label">Password</label>
            <input
              type="password"
              placeholder="Password"
              className="form-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ flex: '2', minWidth: '180px' }}>
            <label className="form-label">Server</label>
            <input
              type="text"
              placeholder="Server"
              className="form-input"
              value={server}
              onChange={e => setServer(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <button
              className="btn-primary"
              onClick={() => login && password && onConnect(parseInt(login), password, server)}
            >
              <Wifi size={14} /> Connect
            </button>
          </div>
        </div>
      </div>
    )
  }

  const profitColor = account.profit >= 0 ? 'var(--buy)' : 'var(--sell)'

  return (
    <div className="card">
      <div className="flex items-center justify-between" style={{ marginBottom: '16px' }}>
        <div className="flex items-center gap-2">
          <span className="dot dot--buy animate-pulse" />
          <span className="font-semibold" style={{ color: 'var(--text)' }}>{account.name}</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>#{account.login} · {account.server}</span>
        </div>
        <button
          onClick={onDisconnect}
          className="btn-secondary"
        >
          <WifiOff size={12} /> Disconnect
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <AccountStat label="Balance"     value={`${account.currency} ${account.balance.toFixed(2)}`} />
        <AccountStat label="Equity"      value={`${account.currency} ${account.equity.toFixed(2)}`} />
        <AccountStat label="Margin"      value={`${account.currency} ${account.margin.toFixed(2)}`} />
        <AccountStat label="Free Margin" value={`${account.currency} ${account.freeMargin.toFixed(2)}`} />
        <AccountStat label="Profit"      value={`${account.currency} ${account.profit.toFixed(2)}`} color={profitColor} />
        <AccountStat label="Leverage"    value={`1:${account.leverage}`} />
      </div>
    </div>
  )
}

// ── Positions Table ───────────────────────────────────────────────────────────

function PositionsTable({
  positions,
  onClose,
  isClosing,
}: {
  positions: MT5Position[]
  onClose: (ticket: number) => void
  isClosing: boolean
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="font-medium" style={{ color: 'var(--text)' }}>Open Positions ({positions.length})</div>
      <div className="overflow-auto rounded-lg border" style={{ borderColor: 'var(--border)' }}>
        <table className="data-table">
          <thead>
            <tr>
              {['Ticket', 'Symbol', 'Type', 'Volume', 'Open Price', 'SL', 'TP', 'Profit', 'Swap', 'Opened', ''].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map(p => {
              const isBuy = p.type === 'BUY'
              const profitColor = p.profit >= 0 ? 'var(--buy)' : 'var(--sell)'
              return (
                <tr key={p.ticket}>
                  <td className="mono text-xs" style={{ color: 'var(--accent)' }}>{p.ticket}</td>
                  <td className="font-medium">{p.symbol}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: isBuy ? 'var(--buy)' : 'var(--sell)' }}>
                      {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                      {p.type}
                    </span>
                  </td>
                  <td className="mono">{p.volume.toFixed(2)}</td>
                  <td className="mono">{p.openPrice.toFixed(5)}</td>
                  <td className="mono text-xs" style={{ color: 'var(--text-muted)' }}>{p.sl > 0 ? p.sl.toFixed(5) : '—'}</td>
                  <td className="mono text-xs" style={{ color: 'var(--text-muted)' }}>{p.tp > 0 ? p.tp.toFixed(5) : '—'}</td>
                  <td className="mono font-semibold" style={{ color: profitColor }}>
                    {p.profit >= 0 ? '+' : ''}{p.profit.toFixed(2)}
                  </td>
                  <td className="mono text-xs" style={{ color: 'var(--text-faint)' }}>{p.swap.toFixed(2)}</td>
                  <td className="text-xs whitespace-nowrap" style={{ color: 'var(--text-faint)' }}>
                    {new Date(p.openTime).toLocaleString()}
                  </td>
                  <td>
                    <button
                      onClick={() => onClose(p.ticket)}
                      disabled={isClosing}
                      className="btn-danger disabled:opacity-40"
                      style={{ height: '26px', padding: '0 8px', fontSize: '11px' }}
                    >
                      <X size={11} /> Close
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {positions.length === 0 && (
          <div className="empty-state" style={{ padding: '32px 24px' }}>
            <TrendingUp size={28} style={{ color: 'var(--text-faint)', opacity: 0.4 }} aria-hidden="true" />
            <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No open positions</div>
            <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>Place an order below to open a position.</div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Order Panel ───────────────────────────────────────────────────────────────

function OrderPanel({ onOrder: _onOrder }: { onOrder: (symbol: string, action: 'BUY' | 'SELL', volume: number, slPips?: number, tpPips?: number, comment?: string) => void }) {
  const [symbol,  setSymbol]  = useState('XAUUSDc')
  const [action,  setAction]  = useState<'BUY' | 'SELL'>('BUY')
  const [volume,  setVolume]  = useState('0.01')
  const [slPips,  setSlPips]  = useState('')
  const [tpPips,  setTpPips]  = useState('')
  const [comment, setComment] = useState('TradeOS')
  const [result,  setResult]  = useState<MT5OrderResult | null>(null)

  const send = useMutation({
    mutationFn: () => api.mt5Order({
      symbol,
      action,
      volume:  parseFloat(volume) || 0.01,
      slPips:  slPips  ? parseFloat(slPips)  : undefined,
      tpPips:  tpPips  ? parseFloat(tpPips)  : undefined,
      comment: comment || 'TradeOS',
    }),
    onSuccess: (data) => setResult(data),
  })

  const isBuy = action === 'BUY'

  return (
    <div className="card flex flex-col gap-4">
      <div className="section-title">New Order</div>

      {/* Action toggle — keep semantic BUY/SELL colors */}
      <div className="flex gap-2">
        <button
          onClick={() => setAction('BUY')}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-semibold transition-colors"
          style={isBuy
            ? { background: 'var(--buy-bg)', color: 'var(--buy)', border: '1px solid var(--buy)' }
            : { color: 'var(--text-faint)', border: '1px solid var(--border)' }
          }
        >
          <TrendingUp size={14} /> BUY
        </button>
        <button
          onClick={() => setAction('SELL')}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-semibold transition-colors"
          style={!isBuy
            ? { background: 'var(--sell-bg)', color: 'var(--sell)', border: '1px solid var(--sell)' }
            : { color: 'var(--text-faint)', border: '1px solid var(--border)' }
          }
        >
          <TrendingDown size={14} /> SELL
        </button>
      </div>

      {/* Fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="form-group">
          <label className="form-label">Symbol</label>
          <select className="form-input" value={symbol} onChange={e => setSymbol(e.target.value)}>
            {['XAUUSDc', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUEURm', 'BTCUSDm', 'GBPJPYm'].map(s => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Volume (lots)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            className="form-input"
            value={volume}
            onChange={e => setVolume(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">SL (pips, optional)</label>
          <input
            type="number"
            step="1"
            min="0"
            placeholder="e.g. 50"
            className="form-input"
            value={slPips}
            onChange={e => setSlPips(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">TP (pips, optional)</label>
          <input
            type="number"
            step="1"
            min="0"
            placeholder="e.g. 100"
            className="form-input"
            value={tpPips}
            onChange={e => setTpPips(e.target.value)}
          />
        </div>
        <div className="form-group col-span-full sm:col-span-2">
          <label className="form-label">Comment</label>
          <input
            type="text"
            className="form-input"
            value={comment}
            onChange={e => setComment(e.target.value)}
          />
        </div>
      </div>

      {/* Submit — keep semantic BUY/SELL color */}
      <button
        onClick={() => { setResult(null); send.mutate() }}
        disabled={send.isPending}
        className="w-full py-2.5 rounded-md text-sm font-semibold text-white disabled:opacity-50 transition-colors"
        style={{ background: isBuy ? 'var(--buy)' : 'var(--sell)' }}
      >
        {send.isPending ? 'Sending…' : `Send ${action} Order`}
      </button>

      {/* Result */}
      {send.isError && (
        <div className="alert-error text-xs">
          {(send.error as Error).message}
        </div>
      )}
      {result && (
        <div className={result.success ? 'alert-success' : 'alert-error'} style={{ fontSize: '12px' }}>
          <div className="font-semibold">
            {result.success ? 'Order placed' : 'Order failed'} — {result.retcodeDesc}
          </div>
          {result.success && (
            <div className="mono" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              <div>Order ID: <span style={{ color: 'var(--text)' }}>{result.orderId}</span></div>
              <div>Symbol: <span style={{ color: 'var(--text)' }}>{result.symbol}</span> · {result.action} {result.volume} lots @ {result.price.toFixed(5)}</div>
              {result.sl > 0 && <div>SL: {result.sl.toFixed(5)} · TP: {result.tp.toFixed(5)}</div>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MT5Terminal() {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)

  // Auto-detect if MT5 is already connected on page load
  const { data: account } = useQuery({
    queryKey:        ['mt5-account'],
    queryFn:         () => api.mt5Account().then(d => { setConnected(true); return d }),
    refetchInterval: connected ? 3000 : false,
    retry:           false,
  })

  // Positions — poll every 3s when connected
  const { data: positions = [] } = useQuery({
    queryKey:       ['mt5-positions'],
    queryFn:        api.mt5Positions,
    refetchInterval: connected ? 3000 : false,
    enabled:        connected,
    retry:          false,
  })

  // Connect
  const connect = useMutation({
    mutationFn: (vars: { login: number; password: string; server: string }) =>
      api.mt5Connect(vars),
    onSuccess: () => {
      setConnected(true)
      qc.invalidateQueries({ queryKey: ['mt5-account'] })
      qc.invalidateQueries({ queryKey: ['mt5-positions'] })
    },
  })

  // Disconnect
  const disconnect = useMutation({
    mutationFn: api.mt5Disconnect,
    onSuccess: () => {
      setConnected(false)
      qc.removeQueries({ queryKey: ['mt5-account'] })
      qc.removeQueries({ queryKey: ['mt5-positions'] })
    },
  })

  // Close position
  const closePos = useMutation({
    mutationFn: (ticket: number) => api.mt5Close({ ticket }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mt5-positions'] }),
  })

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-topbar">
        <h1 className="page-heading">MT5 Terminal</h1>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <span
            className={`dot${connected ? ' animate-pulse' : ''}`}
            style={{ background: connected ? 'var(--buy)' : 'var(--text-faint)' }}
          />
          {connected ? 'Connected' : 'Not connected'}
        </div>
      </div>

      {/* Connection errors */}
      {connect.isError && (
        <div className="alert-error text-xs">
          Connection failed: {(connect.error as Error).message}
        </div>
      )}

      {/* Account panel */}
      <AccountPanel
        account={account}
        connected={connected}
        onConnect={(login, password, server) => connect.mutate({ login, password, server })}
        onDisconnect={() => disconnect.mutate()}
      />

      {/* Trading area (only when connected) */}
      {connected && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Positions — 2/3 width */}
          <div className="xl:col-span-2">
            <PositionsTable
              positions={positions}
              onClose={(ticket) => closePos.mutate(ticket)}
              isClosing={closePos.isPending}
            />
          </div>

          {/* Order form — 1/3 width */}
          <div>
            <OrderPanel
              onOrder={(symbol, action, volume, slPips, tpPips, comment) =>
                api.mt5Order({ symbol, action, volume, slPips, tpPips, comment })
              }
            />
          </div>
        </div>
      )}

      {/* Not connected placeholder */}
      {!connected && (
        <div className="empty-state">
          <WifiOff size={28} style={{ color: 'var(--text-faint)', opacity: 0.4 }} aria-hidden="true" />
          <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Not connected</div>
          <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>Connect to MT5 above to start trading.</div>
        </div>
      )}
    </div>
  )
}
