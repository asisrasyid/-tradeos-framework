import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity, BookOpen, BarChart2, ListOrdered, FlaskConical,
  Brain, TrendingUp, LogOut, Monitor, ChevronLeft, ChevronRight,
  Sun, Moon, Menu, X,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'

const NAV = [
  { to: '/',         icon: Activity,      label: 'Live',         end: true },
  { to: '/theories', icon: BookOpen,      label: 'Theories' },
  { to: '/builder',  icon: TrendingUp,    label: 'Builder' },
  { to: '/patterns', icon: Brain,         label: 'Patterns' },
  { to: '/backtest', icon: FlaskConical,  label: 'Backtest' },
  { to: '/trades',   icon: ListOrdered,   label: 'Trade Log' },
  { to: '/hmm',      icon: BarChart2,     label: 'HMM Models' },
  { to: '/mt5',      icon: Monitor,       label: 'MT5 Terminal' },
]

/* ─── Sidebar styles ────────────────────────────────────────── */
const sidebarStyle: React.CSSProperties = {
  display:       'flex',
  flexDirection: 'column',
  background:    'var(--surface)',
  borderRight:   '1px solid var(--border)',
  overflow:      'hidden',
  position:      'relative',
  zIndex:        20,
  flexShrink:    0,
}

export default function AppLayout() {
  const logout   = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const { mode, setMode } = useThemeStore()

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('tradeos_sidebar') === 'collapsed'
  })
  const [isMobile, setIsMobile] = useState<boolean>(false)
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    setIsMobile(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  /* close drawer on Escape */
  useEffect(() => {
    if (!mobileDrawerOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileDrawerOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [mobileDrawerOpen])

  function toggleSidebar() {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem('tradeos_sidebar', next ? 'collapsed' : 'expanded')
  }

  function cycleTheme() {
    const order: Array<'light' | 'dark' | 'system'> = ['dark', 'light', 'system']
    const idx = order.indexOf(mode)
    setMode(order[(idx + 1) % 3])
  }

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  const ThemeIcon  = mode === 'light' ? Sun : mode === 'dark' ? Moon : Monitor
  const themeLabel = mode === 'light' ? 'Light' : mode === 'dark' ? 'Dark' : 'System'
  const sidebarW   = collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)'

  /* ── Mobile layout ── */
  if (isMobile) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg)' }}>

        {/* Mobile topbar */}
        <header style={{
          position: 'fixed', top: 0, left: 0, right: 0, height: 'var(--topbar-h)',
          background: 'var(--surface)', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 14px', zIndex: 101, boxShadow: 'var(--shadow-sm)',
        }}>
          <button
            aria-label="Open navigation menu"
            onClick={() => setMobileDrawerOpen(true)}
            className="sidebar-btn"
            style={{
              width: '36px', height: '36px',
              border: '1px solid var(--border)', borderRadius: '8px',
            }}
          >
            <Menu size={18} />
          </button>

          <div style={{ textAlign: 'center' }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontWeight: 700,
              fontSize: '15px', color: 'var(--accent)', letterSpacing: '-0.5px',
            }}>TradeOS</span>
          </div>

          <button
            aria-label={`Theme: ${themeLabel}`}
            onClick={cycleTheme}
            className="sidebar-btn"
            style={{
              width: '36px', height: '36px',
              border: '1px solid var(--border)', borderRadius: '8px',
            }}
          >
            <ThemeIcon size={16} />
          </button>
        </header>

        {/* Main content */}
        <main style={{
          flex: 1,
          overflow: 'auto',
          paddingTop: 'var(--topbar-h)',
          paddingBottom: '64px',
        }}>
          <Outlet />
        </main>

        {/* Bottom navigation */}
        <nav
          aria-label="Main navigation"
          style={{
            position: 'fixed', bottom: 0, left: 0, right: 0,
            height: '60px',
            background: 'var(--surface)',
            borderTop: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-around',
            zIndex: 100,
            boxShadow: '0 -4px 20px rgba(0,0,0,0.15)',
            paddingBottom: 'env(safe-area-inset-bottom)',
          }}
        >
          {NAV.slice(0, 6).map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end ?? false}
              aria-label={label}
              style={({ isActive }) => ({
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: '2px', padding: '6px 10px', borderRadius: '8px',
                color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                textDecoration: 'none', minWidth: '46px',
                background: isActive ? 'var(--accent-glow)' : 'transparent',
                fontSize: '9px', fontWeight: isActive ? 700 : 400,
                letterSpacing: '0.2px',
              })}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
          <button
            aria-label="More navigation items"
            onClick={() => setMobileDrawerOpen(true)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              gap: '2px', padding: '6px 10px', borderRadius: '8px',
              color: 'var(--text-muted)', background: 'transparent',
              border: 'none', cursor: 'pointer', fontSize: '9px', minWidth: '46px',
            }}
          >
            <Menu size={17} />
            <span>More</span>
          </button>
        </nav>

        {/* Overlay */}
        {mobileDrawerOpen && (
          <div
            aria-hidden="true"
            onClick={() => setMobileDrawerOpen(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              background: 'rgba(0,0,0,0.55)',
              backdropFilter: 'blur(3px)',
              WebkitBackdropFilter: 'blur(3px)',
              transition: 'opacity 0.2s',
            }}
          />
        )}

        {/* Slide-in drawer */}
        <aside
          aria-label="Navigation drawer"
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed', top: 0, left: 0, bottom: 0,
            width: 'min(280px, 85vw)', zIndex: 201,
            background: 'var(--surface)',
            borderRight: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column',
            boxShadow: 'var(--shadow-xl)',
            transform: mobileDrawerOpen ? 'translateX(0)' : 'translateX(-100%)',
            transition: 'transform 0.28s cubic-bezier(0.4,0,0.2,1)',
          }}
        >
          {/* Drawer header */}
          <div style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            minHeight: '56px',
          }}>
            <div>
              <div style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700,
                fontSize: '15px', color: 'var(--accent)', letterSpacing: '-0.5px',
              }}>TradeOS</div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '1px' }}>
                v5.3 · HMM + Bayesian AI
              </div>
            </div>
            <button
              aria-label="Close navigation drawer"
              onClick={() => setMobileDrawerOpen(false)}
              className="sidebar-btn"
              style={{
                width: '32px', height: '32px',
                border: '1px solid var(--border)', borderRadius: '8px',
              }}
            >
              <X size={15} />
            </button>
          </div>

          {/* Nav items */}
          <nav aria-label="App navigation" style={{ flex: 1, padding: '8px', overflowY: 'auto' }}>
            {NAV.map(({ to, icon: Icon, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end ?? false}
                onClick={() => setMobileDrawerOpen(false)}
                aria-label={label}
                className="sidebar-nav-link"
                style={({ isActive }) => ({
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '10px 12px', borderRadius: '8px',
                  textDecoration: 'none',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  background: isActive ? 'var(--accent-glow)' : 'transparent',
                  fontWeight: isActive ? 600 : 400, fontSize: '14px',
                  marginBottom: '2px',
                  boxShadow: isActive ? 'inset 3px 0 0 var(--accent)' : 'none',
                })}
              >
                {({ isActive }) => (
                  <>
                    <Icon size={17} style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)', flexShrink: 0 }} />
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button
              onClick={cycleTheme}
              className="sidebar-btn"
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '8px 10px', borderRadius: '8px',
                fontSize: '13px', width: '100%', textAlign: 'left',
              }}
            >
              <ThemeIcon size={15} />
              <span>{themeLabel} mode</span>
            </button>
            <button
              onClick={() => { setMobileDrawerOpen(false); handleLogout() }}
              className="sidebar-btn sidebar-btn--danger"
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '8px 10px', borderRadius: '8px',
                fontSize: '13px', width: '100%', textAlign: 'left',
              }}
            >
              <LogOut size={15} />
              <span>Sign Out</span>
            </button>
          </div>
        </aside>

      </div>
    )
  }

  /* ── Desktop layout ── */
  return (
    <div style={{ display: 'flex', height: '100%', background: 'var(--bg)' }}>

      {/* Sidebar */}
      <aside
        id="main-sidebar-nav"
        aria-label="Main navigation"
        style={{
          ...sidebarStyle,
          width:    sidebarW,
          minWidth: sidebarW,
          transition: `width 0.25s cubic-bezier(0.4,0,0.2,1),
                       min-width 0.25s cubic-bezier(0.4,0,0.2,1)`,
        }}
      >
        {/* Logo row */}
        <div style={{
          padding: collapsed ? '14px 0' : '14px 14px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          minHeight: '54px',
        }}>
          {!collapsed && (
            <div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                fontSize: '15px',
                color: 'var(--accent)',
                letterSpacing: '-0.5px',
              }}>
                TradeOS
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '1px', letterSpacing: '0.2px' }}>
                v5.3 · HMM + Bayesian AI
              </div>
            </div>
          )}
          <button
            onClick={toggleSidebar}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            aria-controls="main-sidebar-nav"
            className="sidebar-btn"
            style={{
              width: '28px', height: '28px',
              border: '1px solid var(--border)',
              borderRadius: '7px', flexShrink: 0,
            }}
          >
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, padding: '8px', overflowY: 'auto', overflowX: 'hidden' }}>
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              aria-label={collapsed ? label : undefined}
              title={collapsed ? label : undefined}
              className="sidebar-nav-link"
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center',
                gap: collapsed ? 0 : '10px',
                padding: collapsed ? '9px 0' : '9px 10px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                borderRadius: '8px',
                textDecoration: 'none',
                color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                background: isActive ? 'var(--accent-glow)' : 'transparent',
                fontWeight: isActive ? 600 : 400,
                fontSize: '13px',
                marginBottom: '2px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                boxShadow: isActive ? 'inset 3px 0 0 var(--accent)' : 'none',
              })}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={16}
                    aria-hidden="true"
                    style={{
                      flexShrink: 0,
                      color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                    }}
                  />
                  {!collapsed && <span>{label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div style={{
          padding: collapsed ? '10px 0' : '10px',
          borderTop: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', gap: '4px',
          alignItems: collapsed ? 'center' : 'stretch',
        }}>
          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            aria-label={`Current theme: ${themeLabel}. Click to change.`}
            title={`Theme: ${themeLabel}`}
            className="sidebar-btn"
            style={{
              display: 'flex', alignItems: 'center',
              gap: collapsed ? 0 : '8px',
              justifyContent: collapsed ? 'center' : 'flex-start',
              padding: collapsed ? '7px 0' : '7px 8px',
              borderRadius: '7px', fontSize: '12px', width: '100%',
            }}
          >
            <ThemeIcon size={14} style={{ flexShrink: 0 }} aria-hidden="true" />
            {!collapsed && <span>{themeLabel} mode</span>}
          </button>

          {/* Sign out */}
          <button
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
            className="sidebar-btn sidebar-btn--danger"
            style={{
              display: 'flex', alignItems: 'center',
              gap: collapsed ? 0 : '8px',
              justifyContent: collapsed ? 'center' : 'flex-start',
              padding: collapsed ? '7px 0' : '7px 8px',
              borderRadius: '7px', fontSize: '12px', width: '100%',
            }}
          >
            <LogOut size={14} style={{ flexShrink: 0 }} aria-hidden="true" />
            {!collapsed && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <main style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--bg)',
        position: 'relative',
      }}>
        <Outlet />
      </main>
    </div>
  )
}
