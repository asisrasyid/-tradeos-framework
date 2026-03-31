import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { api } from '../lib/api'

export default function Login() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)
  const setToken = useAuthStore(s => s.setToken)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await api.login(username, password)
      setToken(data.token)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg)',
        padding: '20px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Decorative background glow */}
      <div style={{
        position: 'absolute',
        top: '20%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '600px',
        height: '400px',
        background: 'radial-gradient(ellipse at center, rgba(59,130,246,0.08) 0%, transparent 70%)',
        pointerEvents: 'none',
        userSelect: 'none',
      }} />
      <div style={{
        position: 'absolute',
        bottom: '10%',
        right: '20%',
        width: '300px',
        height: '300px',
        background: 'radial-gradient(ellipse at center, rgba(167,139,250,0.05) 0%, transparent 70%)',
        pointerEvents: 'none',
        userSelect: 'none',
      }} />

      {/* Login card */}
      <div
        style={{
          width: '100%',
          maxWidth: '380px',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '16px',
          padding: 'clamp(24px, 5vw, 36px)',
          boxShadow: 'var(--shadow-xl)',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Logo section */}
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          {/* Icon mark */}
          <div style={{
            width: '48px', height: '48px',
            borderRadius: '12px',
            background: 'var(--accent-glow)',
            border: '1px solid rgba(59,130,246,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '4px',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <polyline points="2,17 8,11 12,15 22,7" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <polyline points="16,7 22,7 22,13" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontWeight: 800,
            fontSize: '22px',
            color: 'var(--accent)',
            letterSpacing: '-0.5px',
          }}>
            TradeOS
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', letterSpacing: '0.3px' }}>
            HMM + Bayesian AI · v5.3
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="form-group">
            <label
              htmlFor="login-username"
              className="form-label"
            >
              Username
            </label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoComplete="username"
              autoFocus
              className="form-input"
              placeholder="Enter username"
            />
          </div>

          <div className="form-group">
            <label
              htmlFor="login-password"
              className="form-label"
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="form-input"
              placeholder="Enter password"
            />
          </div>

          {error && (
            <div className="alert-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary"
            style={{
              width: '100%',
              height: '40px',
              fontSize: '14px',
              borderRadius: '10px',
              marginTop: '4px',
            }}
          >
            {loading ? (
              <>
                <span className="spinner spinner--sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} />
                Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Footer note */}
        <div style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-faint)' }}>
          Secure trading platform · All activity is logged
        </div>
      </div>
    </div>
  )
}
