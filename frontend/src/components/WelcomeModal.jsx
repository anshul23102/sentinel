import { useState, useEffect } from 'react'

const FEATURES = [
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
    color: '#22d3ee',
    title: 'Real-time detection',
    desc: 'Z-score anomaly detection on a 60s sliding window at 30 req/s',
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
      </svg>
    ),
    color: '#a78bfa',
    title: 'AI root cause analysis',
    desc: 'Every anomaly diagnosed by Llama 3.3 70B with fix steps',
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
      </svg>
    ),
    color: '#34d399',
    title: 'Service dependency graph',
    desc: 'Live canvas graph shows cascade failure propagation paths',
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
    color: '#f472b6',
    title: 'Streaming AI chat',
    desc: 'Ask Sentinel AI anything — responses stream token-by-token',
  },
]

const STATS = [
  { label: 'Endpoints Monitored', value: 8,    suffix: '',    color: '#c4b5fd' },
  { label: 'Logs / Second',       value: 30,   suffix: ' rps', color: '#22d3ee' },
  { label: 'Failure Scenarios',   value: 5,    suffix: '',    color: '#f87171' },
  { label: 'AI Model',            value: '70B', suffix: '',   color: '#34d399' },
]

export default function WelcomeModal({ onClose, theme = 'dark' }) {
  const [animCount, setAnimCount] = useState([0, 0, 0, 0])
  const [page, setPage] = useState(0) // 0 = splash, 1 = features
  const isDark = theme !== 'light'

  // Animate number counters on mount — cancel RAF if modal closes before animation ends
  useEffect(() => {
    const targets  = [8, 30, 5, 70]
    const duration = 900
    const start    = performance.now()
    let rafId
    const tick = (now) => {
      const t      = Math.min((now - start) / duration, 1)
      const eased  = 1 - Math.pow(1 - t, 3)
      setAnimCount(targets.map(v => Math.round(v * eased)))
      if (t < 1) rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [])

  // Theme-aware tokens — mirrors the palette used across the rest of the app
  const c = {
    overlayBg:      isDark ? 'rgba(0,0,0,0.82)'        : 'rgba(15,15,26,0.42)',
    cardBg:         isDark ? 'rgba(5,6,14,0.98)'        : 'rgba(255,255,255,0.98)',
    cardBorder:     isDark ? 'rgba(255,255,255,0.1)'    : 'rgba(15,10,30,0.1)',
    cardShadow:     isDark
      ? '0 48px 120px rgba(0,0,0,0.8), 0 0 0 1px rgba(139,92,246,0.1)'
      : '0 32px 80px rgba(76,29,149,0.16), 0 0 0 1px rgba(124,58,237,0.08)',
    heading:        isDark ? '#ffffff' : '#0f0a1e',
    subtext:        isDark ? 'rgba(255,255,255,0.35)'   : 'rgba(15,10,30,0.45)',
    body:           isDark ? 'rgba(255,255,255,0.45)'   : 'rgba(15,10,30,0.55)',
    closeBg:        isDark ? 'rgba(255,255,255,0.07)'   : 'rgba(15,10,30,0.06)',
    closeBgHover:   isDark ? 'rgba(255,255,255,0.12)'   : 'rgba(15,10,30,0.1)',
    closeColor:     isDark ? 'rgba(255,255,255,0.4)'    : 'rgba(15,10,30,0.45)',
    closeColorHover:isDark ? '#ffffff'                  : '#0f0a1e',
    statBg:         isDark ? 'rgba(255,255,255,0.03)'   : 'rgba(124,58,237,0.05)',
    statBorder:     isDark ? 'rgba(255,255,255,0.08)'   : 'rgba(124,58,237,0.16)',
    statLabel:      isDark ? 'rgba(255,255,255,0.3)'    : 'rgba(15,10,30,0.42)',
    secondaryBg:    isDark ? 'rgba(255,255,255,0.04)'   : 'rgba(124,58,237,0.06)',
    secondaryBorder:isDark ? 'rgba(255,255,255,0.1)'    : 'rgba(124,58,237,0.18)',
    secondaryText:  isDark ? 'rgba(255,255,255,0.6)'    : 'rgba(15,10,30,0.62)',
    featuresHeading:isDark ? '#ffffff' : '#0f0a1e',
    backBtnText:    isDark ? 'rgba(255,255,255,0.4)'    : 'rgba(15,10,30,0.45)',
    featureRowBg:   isDark ? 'rgba(255,255,255,0.025)'  : 'rgba(124,58,237,0.04)',
    featureRowBorder: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(124,58,237,0.14)',
    featureTitle:   isDark ? 'rgba(255,255,255,0.88)'   : 'rgba(15,10,30,0.9)',
    featureDesc:    isDark ? 'rgba(255,255,255,0.4)'    : 'rgba(15,10,30,0.52)',
    tipBg:          isDark ? 'rgba(124,58,237,0.07)'    : 'rgba(124,58,237,0.08)',
    tipBorder:      isDark ? 'rgba(139,92,246,0.2)'     : 'rgba(124,58,237,0.24)',
    tipText:        isDark ? '#c4b5fd'                  : '#6d28d9',
    hintBorder:     isDark ? 'rgba(255,255,255,0.05)'   : 'rgba(15,10,30,0.08)',
    hintText:       isDark ? 'rgba(255,255,255,0.18)'   : 'rgba(15,10,30,0.32)',
    kbdBg:          isDark ? 'rgba(255,255,255,0.08)'   : 'rgba(15,10,30,0.06)',
    kbdBorder:      isDark ? 'rgba(255,255,255,0.1)'    : 'rgba(15,10,30,0.12)',
    glowOpacity:    isDark ? 0.15 : 0.08,
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: c.overlayBg,
      backdropFilter: 'blur(20px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
      animation: 'fadeIn 0.25s ease',
    }}>
      {/* Glow behind modal */}
      <div style={{
        position: 'absolute',
        width: 600, height: 600,
        background: `radial-gradient(circle, rgba(124,58,237,${c.glowOpacity}) 0%, transparent 65%)`,
        borderRadius: '50%', pointerEvents: 'none',
      }} />

      <div style={{
        background: c.cardBg,
        border: `1px solid ${c.cardBorder}`,
        borderRadius: 24, width: '100%', maxWidth: 600,
        overflow: 'hidden', position: 'relative',
        boxShadow: c.cardShadow,
      }}>

        {/* Top gradient bar */}
        <div style={{ height: 2, background: 'linear-gradient(90deg, #7c3aed 0%, #a78bfa 40%, #22d3ee 70%, transparent 100%)' }} />

        {page === 0 ? (
          <>
            {/* Splash */}
            <div style={{ padding: '38px 40px 28px' }}>
              {/* Logo + name */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 13,
                  background: 'linear-gradient(135deg, #7c3aed 0%, #a78bfa 55%, #22d3ee 100%)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 0 28px rgba(124,58,237,0.5)',
                }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                  </svg>
                </div>
                <div>
                  <div style={{
                    fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px',
                    background: isDark
                      ? 'linear-gradient(135deg, #ffffff 30%, #c4b5fd 70%, #67e8f9 100%)'
                      : 'linear-gradient(135deg, #0f0a1e 30%, #7c3aed 70%, #0891b2 100%)',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
                  }}>Sentinel</div>
                  <div style={{ fontSize: 11, color: c.subtext, marginTop: 1 }}>
                    AI-Powered API Intelligence
                  </div>
                </div>
                <button onClick={onClose} style={{
                  marginLeft: 'auto', width: 28, height: 28, borderRadius: '50%', border: 'none',
                  background: c.closeBg, color: c.closeColor,
                  cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = c.closeBgHover; e.currentTarget.style.color = c.closeColorHover }}
                onMouseLeave={e => { e.currentTarget.style.background = c.closeBg; e.currentTarget.style.color = c.closeColor }}
                >✕</button>
              </div>

              <div style={{ fontSize: 13, color: c.body, lineHeight: 1.75, marginBottom: 28, maxWidth: 480 }}>
                Production-grade API failure detection for NexusCommerce. Detects, diagnoses, and explains failures in real time using AI.
                <span style={{ color: isDark ? '#c4b5fd' : '#6d28d9', fontWeight: 600 }}> 8 services · 30 rps live traffic · Llama 3.3 70B.</span>
              </div>

              {/* Animated stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 28 }}>
                {STATS.map((s, i) => (
                  <div key={i} style={{
                    padding: '14px 12px', borderRadius: 12, textAlign: 'center',
                    background: c.statBg, border: `1px solid ${c.statBorder}`,
                  }}>
                    <div style={{
                      fontSize: 22, fontWeight: 900, letterSpacing: '-1px',
                      color: s.color, textShadow: `0 0 16px ${s.color}55`,
                    }}>
                      {i === 3 ? `${animCount[i]}B` : `${animCount[i]}${s.suffix}`}
                    </div>
                    <div style={{ fontSize: 9, color: c.statLabel, marginTop: 4, fontWeight: 500 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* CTA buttons */}
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={onClose} style={{
                  flex: 2, padding: '13px', borderRadius: 12, border: 'none',
                  background: 'linear-gradient(135deg, #7c3aed, #a78bfa 55%, #22d3ee)',
                  color: 'white', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                  boxShadow: '0 4px 24px rgba(124,58,237,0.35)',
                  transition: 'all 0.18s', letterSpacing: '-0.1px',
                }}
                onMouseEnter={e => e.currentTarget.style.boxShadow = '0 6px 32px rgba(124,58,237,0.5)'}
                onMouseLeave={e => e.currentTarget.style.boxShadow = '0 4px 24px rgba(124,58,237,0.35)'}
                >Launch Sentinel</button>
                <button onClick={() => setPage(1)} style={{
                  flex: 1, padding: '13px', borderRadius: 12,
                  border: `1px solid ${c.secondaryBorder}`,
                  background: c.secondaryBg,
                  color: c.secondaryText, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.15s',
                }}>See Features</button>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Features */}
            <div style={{ padding: '30px 40px 28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 22 }}>
                <div style={{ fontSize: 16, fontWeight: 800, color: c.featuresHeading }}>What's inside</div>
                <button onClick={() => setPage(0)} style={{
                  marginLeft: 'auto', fontSize: 12, color: c.backBtnText, background: 'none',
                  border: 'none', cursor: 'pointer', padding: '2px 6px',
                }}>← Back</button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
                {FEATURES.map((f, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 14,
                    padding: '14px 16px', borderRadius: 12,
                    background: c.featureRowBg, border: `1px solid ${c.featureRowBorder}`,
                    animation: `fadeUp 0.35s ease ${i * 0.07}s both`,
                  }}>
                    <div style={{
                      width: 34, height: 34, borderRadius: 10, flexShrink: 0,
                      background: `${f.color}18`, border: `1px solid ${f.color}30`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', color: f.color,
                    }}>
                      {f.icon}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: c.featureTitle, marginBottom: 3 }}>{f.title}</div>
                      <div style={{ fontSize: 12, color: c.featureDesc, lineHeight: 1.6 }}>{f.desc}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Quick start tip */}
              <div style={{
                padding: '12px 16px', borderRadius: 12,
                background: c.tipBg, border: `1px solid ${c.tipBorder}`,
                fontSize: 12, color: c.tipText, lineHeight: 1.6, marginBottom: 20,
              }}>
                <span style={{ fontWeight: 700 }}>Quick start:</span> Click "DB Slowdown" on the Overview page, then watch anomalies fire and AI diagnose them in real time.
              </div>

              <button onClick={onClose} style={{
                width: '100%', padding: '13px', borderRadius: 12, border: 'none',
                background: 'linear-gradient(135deg, #7c3aed, #a78bfa 55%, #22d3ee)',
                color: 'white', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                boxShadow: '0 4px 24px rgba(124,58,237,0.35)',
              }}>Start monitoring</button>
            </div>
          </>
        )}

        {/* Bottom hint */}
        <div style={{
          padding: '10px 40px 16px', borderTop: `1px solid ${c.hintBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          fontSize: 10, color: c.hintText,
        }}>
          <span>Press</span>
          <span style={{ background: c.kbdBg, border: `1px solid ${c.kbdBorder}`, borderRadius: 4, padding: '1px 6px', fontFamily: 'monospace' }}>Esc</span>
          <span>to dismiss</span>
        </div>
      </div>
    </div>
  )
}