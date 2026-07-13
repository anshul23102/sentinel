const NAV = [
  {
    id: 'overview',
    label: 'Overview',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
      </svg>
    ),
  },
  {
    id: 'endpoints',
    label: 'Endpoints',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
  },
  {
    id: 'incidents',
    label: 'Incidents',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
    ),
    badge: true,
  },
  {
    id: 'assistant',
    label: 'AI Assistant',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
  },
]

function computeScore(health) {
  const entries = Object.values(health)
  if (entries.length === 0) return 100
  const criticals = entries.filter(h => h.status === 'critical').length
  const degraded  = entries.filter(h => h.status === 'degraded').length
  return Math.max(0, 100 - criticals * 18 - degraded * 7)
}

export default function Sidebar({ page, setPage, anomalyCount, connected, demoMode, health = {} }) {
  const score     = computeScore(health)
  const scoreColor = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'

  return (
    <div style={{
      position: 'fixed', left: 0, top: 0, bottom: 0, width: 220,
      background: 'var(--app-surface-strong)',
      backdropFilter: 'blur(28px)',
      WebkitBackdropFilter: 'blur(28px)',
      borderRight: '1px solid var(--app-border)',
      display: 'flex', flexDirection: 'column',
      zIndex: 50,
      color: 'var(--app-text)',
      transition: 'background 0.3s ease, border-color 0.3s ease',
    }}>

      {/* Brand */}
      <div style={{ padding: '26px 20px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9,
            background: 'linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 22px rgba(139,92,246,0.5)',
            flexShrink: 0,
          }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--app-text)', letterSpacing: '-0.2px' }}>Sentinel</div>
            <div style={{ fontSize: 10, color: 'var(--app-muted-strong)', marginTop: 1 }}>API Intelligence</div>
          </div>
        </div>

        {/* Status pill with health score */}
        <div style={{
          padding: '11px 13px', borderRadius: 11,
          background: 'var(--app-pill-bg)',
          border: '1px solid var(--app-pill-border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--app-nav-text)' }}>NexusCommerce</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: connected ? '#a78bfa' : 'rgba(255,255,255,0.25)',
                boxShadow: connected ? '0 0 8px rgba(167,139,250,1)' : 'none',
                animation: connected ? 'pulse 2s infinite' : 'none',
              }} />
              <span style={{ fontSize: 10, color: connected ? (demoMode ? '#fbbf24' : '#c4b5fd') : 'var(--app-muted-strong)', fontWeight: 600 }}>
                {connected ? (demoMode ? 'Demo' : 'Live') : 'Off'}
              </span>
            </div>
          </div>
          <div style={{ fontSize: 10, color: 'var(--app-muted)', marginBottom: 10 }}>
            Production · us-east-1
          </div>
          {/* Health Score bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: 10, color: 'var(--app-muted)', fontWeight: 500 }}>Health Score</span>
            <span style={{
              fontSize: 12, fontWeight: 800, color: scoreColor,
              textShadow: `0 0 10px ${scoreColor}66`,
              animation: 'scorePop 0.3s ease',
              // key trick done via parent re-render
            }}>{score}</span>
          </div>
          <div style={{ height: 3, background: 'var(--text-06)', borderRadius: 3 }}>
            <div style={{
              height: '100%', borderRadius: 3,
              width: `${score}%`,
              background: score >= 80
                ? 'linear-gradient(90deg, #34d399, #6ee7b7)'
                : score >= 50
                  ? 'linear-gradient(90deg, #fbbf24, #fde68a)'
                  : 'linear-gradient(90deg, #f87171, #fca5a5)',
              transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1), background 0.6s ease',
              boxShadow: `0 0 6px ${scoreColor}66`,
            }} />
          </div>
        </div>
      </div>

      {/* Pages label */}
      <div style={{ padding: '0 20px 10px' }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--app-muted-strong)', textTransform: 'uppercase', letterSpacing: '1px' }}>
          Pages
        </span>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {NAV.map((item, idx) => {
          const active = page === item.id
          return (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`nav-btn${active ? ' active' : ''}`}
            >
              <span style={{ flexShrink: 0, display: 'flex', opacity: active ? 1 : 0.6 }}>{item.icon}</span>
              {item.label}
              <span style={{
                marginLeft: 'auto', fontSize: 9, fontWeight: 600,
                color: 'var(--app-muted-strong)',
                background: 'var(--app-card-bg)', border: '1px solid var(--app-card-border)',
                borderRadius: 4, padding: '1px 5px', flexShrink: 0, fontFamily: 'monospace',
              }}>{idx + 1}</span>
              {item.badge && anomalyCount > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  background: 'rgba(139,92,246,0.18)',
                  color: '#c4b5fd',
                  border: '1px solid rgba(139,92,246,0.3)',
                  borderRadius: 20, padding: '1px 7px', flexShrink: 0,
                }}>{anomalyCount}</span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div style={{ padding: '16px 20px 24px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ fontSize: 10, color: 'var(--app-muted-strong)', lineHeight: 1.9, marginBottom: 8 }}>
          8 endpoints monitored<br />
          Llama 3.3 70B via Groq
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          fontSize: 9, color: 'var(--app-muted-strong)', fontFamily: 'monospace',
        }}>
          <span style={{ background: 'var(--text-06)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 3, padding: '1px 4px' }}>1-4</span>
          <span>navigate</span>
          <span style={{ marginLeft: 6, background: 'var(--text-06)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 3, padding: '1px 4px' }}>Esc</span>
          <span>dismiss</span>
        </div>
      </div>
    </div>
  )
}
