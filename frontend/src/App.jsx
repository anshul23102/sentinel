import { useState, useEffect, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import Endpoints from './pages/Endpoints'
import Incidents from './pages/Incidents'
import Assistant from './pages/Assistant'
import WelcomeModal from './components/WelcomeModal'
import SparkField from './components/SparkField'
import ToastNotifications from './components/ToastNotifications'
import { Moon, Sun } from 'lucide-react'
function getInitialTheme() {
  if (typeof window === 'undefined') return 'dark'
  const saved = window.localStorage.getItem('sentinel-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function AlertBanner({ health }) {
  const criticals = Object.entries(health).filter(([, s]) => s.status === 'critical')
  const [dismissed, setDismissed] = useState(false)
  const prevRef = useRef(0)

  // Re-show banner whenever the critical count increases (new incident)
  useEffect(() => {
    if (criticals.length > prevRef.current) setDismissed(false)
    prevRef.current = criticals.length
  })  // intentionally no dep array — runs every render, uses ref to compare

  if (criticals.length === 0 || dismissed) return null

  const names = criticals.slice(0, 3).map(([ep]) => ep.replace('/api/', '')).join(', ')

  return (
    <div style={{
      position: 'fixed', top: 0, left: 220, right: 0, zIndex: 100,
      animation: 'alertSlide 0.3s cubic-bezier(0.22,1,0.36,1)',
    }}>
      <div style={{
        background: 'linear-gradient(90deg, rgba(139,92,246,0.18), rgba(167,139,250,0.12), rgba(139,92,246,0.18))',
        borderBottom: '1px solid rgba(139,92,246,0.4)',
        backdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 24px',
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%', background: '#a78bfa', flexShrink: 0,
          boxShadow: '0 0 8px rgba(167,139,250,1)', animation: 'pulse 0.9s infinite',
        }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#c4b5fd', letterSpacing: '0.3px' }}>
          INCIDENT ACTIVE
        </span>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)' }}>
          {criticals.length} critical endpoint{criticals.length > 1 ? 's' : ''} detected:
        </span>
        <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#e2d9fb', fontWeight: 600 }}>
          {names}{criticals.length > 3 ? ` +${criticals.length - 3} more` : ''}
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setDismissed(true)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.3)', fontSize: 16, lineHeight: 1,
            padding: '2px 6px', borderRadius: 4, transition: 'color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'rgba(255,255,255,0.7)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.3)'}
        >
          ✕
        </button>
      </div>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState('overview')
  const [showWelcome, setShowWelcome] = useState(true)
  const [theme, setTheme] = useState(getInitialTheme)
  const ws = useWebSocket()

  const isDark = theme === 'dark'

  const toggleTheme = () => {
    setTheme(isDark ? 'light' : 'dark')
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    window.localStorage.setItem('sentinel-theme', theme)
  }, [theme])

  useEffect(() => {
    const move = (e) => {
      document.documentElement.style.setProperty('--cx', `${e.clientX}px`)
      document.documentElement.style.setProperty('--cy', `${e.clientY}px`)
    }
    window.addEventListener('mousemove', move, { passive: true })
    return () => window.removeEventListener('mousemove', move)
  }, [])

  // Keyboard shortcuts: 1-4 for pages, Escape to close welcome
  useEffect(() => {
    const PAGE_KEYS = { '1': 'overview', '2': 'endpoints', '3': 'incidents', '4': 'assistant' }
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (PAGE_KEYS[e.key]) { setPage(PAGE_KEYS[e.key]); return }
      if (e.key === 'Escape') setShowWelcome(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const pages = { overview: Overview, endpoints: Endpoints, incidents: Incidents, assistant: Assistant }
  const Page = pages[page]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--app-bg)', color: 'var(--app-text)', position: 'relative', overflow: 'hidden', transition: 'background 0.3s ease, color 0.3s ease' }}>

      <SparkField />
      <div className="cursor-glow" style={{ zIndex: 0 }} />

      {/* Top shimmer — violet to cyan */}
      <div style={{
        position: 'fixed', top: 0, left: 220, right: 0, height: 1, zIndex: 2, pointerEvents: 'none',
        background: 'linear-gradient(90deg, transparent 0%, rgba(124,58,237,0.7) 25%, rgba(167,139,250,0.5) 50%, rgba(6,182,212,0.45) 75%, transparent 100%)',
        animation: 'lineShimmer 6s ease-in-out infinite',
      }} />

      {/* Ambient orbs */}
      <div style={{
        position: 'fixed', width: 800, height: 800, top: '-18%', left: '5%',
        background: 'radial-gradient(circle, rgba(124,58,237,0.12) 0%, transparent 60%)',
        borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
        animation: 'drift1 32s ease-in-out infinite',
      }} />
      <div style={{
        position: 'fixed', width: 600, height: 600, bottom: '-8%', right: '0%',
        background: 'radial-gradient(circle, rgba(6,182,212,0.07) 0%, transparent 60%)',
        borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
        animation: 'drift2 42s ease-in-out infinite',
      }} />
      <div style={{
        position: 'fixed', width: 400, height: 400, bottom: '22%', left: '32%',
        background: 'radial-gradient(circle, rgba(34,211,238,0.04) 0%, transparent 60%)',
        borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
      }} />
      <div style={{
        position: 'fixed', width: 300, height: 300, top: '35%', right: '18%',
        background: 'radial-gradient(circle, rgba(139,92,246,0.05) 0%, transparent 60%)',
        borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
      }} />

      {/* Grid texture */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
        backgroundImage: `
          linear-gradient(rgba(255,255,255,0.014) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.014) 1px, transparent 1px)
        `,
        backgroundSize: '52px 52px',
      }} />

      <Sidebar page={page} setPage={setPage} anomalyCount={ws.anomalies.length} connected={ws.connected} demoMode={ws.demoMode} health={ws.health} />

      <AlertBanner health={ws.health} />

      <main style={{ flex: 1, marginLeft: 220, overflowY: 'auto', position: 'relative', zIndex: 1, background: theme === 'dark' ? 'transparent' : 'transparent' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 28px 12px', position: 'sticky', top: 0, zIndex: 3, background: theme === 'dark' ? 'rgba(4,5,13,0.75)' : 'rgba(255,255,255,0.6)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderBottom: theme === 'dark' ? 'none' : '1px solid rgba(148,163,184,0.18)' }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--app-muted)', marginBottom: 4 }}>Operations Center</div>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px', color: 'var(--app-text)' }}>NexusCommerce</div>
          </div>
          <div
            className='bg-blue-400 p-10'
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          >
            {/* Toggle theme button */}
            <button
              onClick={toggleTheme}
              role="switch"
              aria-checked={isDark}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              style={{
                position: "relative",
                display: "flex",
                height: "36px",
                width: "68px",
                flexShrink: 0,
                alignItems: "center",
                borderRadius: "9999px",
                border: "1px solid",
                padding: "3px",
                transition: "all 500ms ease-out",
                border: isDark
                  ? "1px solid rgba(167, 139, 250, 0.25)" // violet-400/25
                  : "1px solid rgba(253, 230, 138, 0.7)", // amber-200/70

                background: isDark
                  ? "linear-gradient(to bottom right, #1e1b4b, #2e1065, #0f172a)"
                  : "linear-gradient(to bottom right, #fffbeb, #f0f9ff, #f5f3ff)",

                boxShadow: isDark
                  ? "0 0 0 1px rgba(139,92,246,0.08), 0 4px 16px rgba(76,29,149,0.45)"
                  : "0 2px 10px rgba(251,191,36,0.28)",

                transition: "all 500ms ease-out",
              }}

            >
              {/* Ambient stars — dark mode only */}
              <span
                style={{
                  position: "absolute",
                  left: "10px",
                  top: "7px",
                  width: "3px",
                  height: "3px",
                  borderRadius: "9999px",
                  backgroundColor: "#fff",
                  opacity: isDark ? 0.7 : 0,
                  transition: "opacity 500ms",
                }}
              />
              <span
                style={{
                  position: "absolute",
                  left: "18px",
                  top: "13px",
                  width: "2px",
                  height: "2px",
                  borderRadius: "9999px",
                  backgroundColor: "#fff",
                  opacity: isDark ? 0.5 : 0,
                  transition: "opacity 500ms 100ms", // duration + delay
                }}
              />
              <span
                style={{
                  position: "absolute",
                  left: "12px",
                  top: "19px",
                  width: "2px",
                  height: "2px",
                  borderRadius: "9999px",
                  backgroundColor: "#fff",
                  opacity: isDark ? 0.6 : 0,
                  transition: "opacity 500ms 150ms", // duration + delay
                }}
              />
              {/* Sun rays — light mode only */}
              <span
                style={{
                  position: "absolute",
                  right: "9px",
                  top: "50%",
                  width: "1.5px",
                  height: "12px",
                  transform: "translateY(-50%)",
                  borderRadius: "9999px",
                  backgroundColor: "#fcd34d", // amber-300
                  opacity: isDark ? 0 : 0.8,
                  transition: "opacity 500ms",
                }}
              />
              <span
                style={{
                  position: "absolute",
                  right: "5px",
                  top: "50%",
                  width: "12px",
                  height: "1.5px",
                  transform: "translateY(-50%)",
                  borderRadius: "9999px",
                  backgroundColor: "#fcd34d", // amber-300
                  opacity: isDark ? 0 : 0.8,
                  transition: "opacity 500ms",
                }}
              />
              {/* Sliding thumb */}
              <div
                style={{
                  position: "relative",
                  zIndex: 10,
                  display: "flex",
                  width: "26px",
                  height: "26px",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "9999px",

                  transform: isDark
                    ? "translateX(36px)"
                    : "translateX(0)",

                  background: isDark
                    ? "linear-gradient(to bottom right, #f1f5f9, #cbd5e1)"
                    : "linear-gradient(to bottom right, #fcd34d, #fb923c)",

                  boxShadow: isDark
                    ? "0 2px 8px rgba(0,0,0,0.45), inset 0 1px 1px rgba(255,255,255,0.6)"
                    : "0 2px 8px rgba(217,119,6,0.5), inset 0 1px 1px rgba(255,255,255,0.5)",

                  transition: "all 500ms ease-out",
                }}
              >
                <Moon
                  style={{
                    position: "absolute",
                    width: "14px",
                    height: "14px",
                    color: "#312e81", // indigo-900

                    transform: isDark
                      ? "rotate(0deg) scale(1)"
                      : "rotate(-90deg) scale(0)",

                    opacity: isDark ? 1 : 0,

                    transition: "all 300ms",
                  }}
                />
                <Sun
                  style={{
                    position: "absolute",
                    width: "14px",
                    height: "14px",
                    color: "#ffffff",

                    transform: isDark
                      ? "rotate(90deg) scale(0)"
                      : "rotate(0deg) scale(1)",

                    opacity: isDark ? 0 : 1,

                    transition: "all 300ms",
                  }}
                />
              </div>
            </button>
          </div>

        </div>
        <div key={page} className="page-wrapper" style={{ padding: '0 24px 24px' }}>
          <div style={{ background: theme === 'dark' ? 'transparent' : 'rgba(255,255,255,0.56)', border: theme === 'dark' ? 'none' : `1px solid var(--app-panel-border)`, borderRadius: 24, boxShadow: theme === 'dark' ? 'none' : `0 18px 44px var(--app-shadow)`, padding: 18, backdropFilter: theme === 'dark' ? 'none' : 'blur(24px)', WebkitBackdropFilter: theme === 'dark' ? 'none' : 'blur(24px)' }}>
            <Page {...ws} />
          </div>
        </div>
      </main>

      {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} theme={theme} />}
      <ToastNotifications anomalies={ws.anomalies} />
    </div>
  )
}