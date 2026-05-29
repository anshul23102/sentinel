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
  const [page, setPage]               = useState('overview')
  const [showWelcome, setShowWelcome] = useState(true)
  const ws                            = useWebSocket()

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
  const Page  = pages[page]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#04050d', position: 'relative', overflow: 'hidden' }}>

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

      <main style={{ flex: 1, marginLeft: 220, overflowY: 'auto', position: 'relative', zIndex: 1 }}>
        <div key={page} className="page-wrapper">
          <Page {...ws} />
        </div>
      </main>

      {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} />}
      <ToastNotifications anomalies={ws.anomalies} />
    </div>
  )
}
