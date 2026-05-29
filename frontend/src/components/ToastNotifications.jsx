import { useState, useEffect, useRef } from 'react'

const TYPE_CONFIG = {
  cascade_failure: { label: 'Cascade',  icon: '⚡', color: '#f87171', bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.35)' },
  latency_spike:   { label: 'Latency',  icon: '⏱', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',   border: 'rgba(251,191,36,0.3)'  },
  error_surge:     { label: 'Errors',   icon: '🔴', color: '#f87171', bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.35)' },
}

export default function ToastNotifications({ anomalies }) {
  const [toasts, setToasts]   = useState([])
  const seenIds               = useRef(new Set())
  const counterRef            = useRef(0)

  useEffect(() => {
    if (!anomalies?.length) return
    const latest = anomalies[0]
    // Use detected_at + endpoint as dedup key (anomaly may not have id yet on init)
    const key = `${latest.detected_at}-${latest.endpoint}`
    if (seenIds.current.has(key)) return
    seenIds.current.add(key)

    // Only show critical or if error_surge on important endpoints
    if (latest.severity !== 'critical' && latest.anomaly_type !== 'cascade_failure') return

    const id = ++counterRef.current
    setToasts(prev => [{ ...latest, _tid: id }, ...prev].slice(0, 4))

    // Auto-dismiss after 6s
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t._tid !== id))
    }, 6000)
  }, [anomalies])

  const dismiss = (tid) => setToasts(prev => prev.filter(t => t._tid !== tid))

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 28, right: 28,
      display: 'flex', flexDirection: 'column', gap: 10,
      zIndex: 200,
    }}>
      {toasts.map((t, i) => {
        const cfg = TYPE_CONFIG[t.anomaly_type] || TYPE_CONFIG.error_surge
        return (
          <div
            key={t._tid}
            style={{
              width: 340, borderRadius: 14,
              background: 'rgba(7,8,12,0.97)',
              border: `1px solid ${cfg.border}`,
              backdropFilter: 'blur(24px)',
              boxShadow: `0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px ${cfg.border}`,
              overflow: 'hidden',
              animation: 'toastSlide 0.35s cubic-bezier(0.22,1,0.36,1)',
            }}
          >
            {/* Top color strip */}
            <div style={{ height: 2, background: `linear-gradient(90deg, ${cfg.color}, transparent)` }} />

            <div style={{ padding: '14px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
                {/* Icon */}
                <div style={{
                  width: 32, height: 32, borderRadius: 9, flexShrink: 0,
                  background: cfg.bg, border: `1px solid ${cfg.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14,
                }}>
                  {cfg.icon}
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                    <span style={{
                      fontSize: 11, fontWeight: 800, color: cfg.color,
                      textTransform: 'uppercase', letterSpacing: '0.4px',
                    }}>
                      {cfg.label} Detected
                    </span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.4)',
                      background: 'rgba(255,255,255,0.06)', padding: '1px 7px', borderRadius: 20,
                      textTransform: 'uppercase', letterSpacing: '0.4px',
                    }}>
                      {t.severity}
                    </span>
                  </div>

                  <div style={{
                    fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)',
                    fontFamily: "'JetBrains Mono', monospace", marginBottom: 4,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {t.endpoint === 'multiple' ? 'Multiple endpoints' : t.endpoint}
                  </div>

                  <div style={{
                    fontSize: 11, color: 'rgba(255,255,255,0.45)', lineHeight: 1.5,
                    overflow: 'hidden', display: '-webkit-box',
                    WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  }}>
                    {t.description}
                  </div>
                </div>

                {/* Dismiss */}
                <button
                  onClick={() => dismiss(t._tid)}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'rgba(255,255,255,0.25)', fontSize: 15, padding: '2px 4px',
                    flexShrink: 0, lineHeight: 1, transition: 'color 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = 'rgba(255,255,255,0.6)'}
                  onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.25)'}
                >
                  ✕
                </button>
              </div>

              {/* Countdown bar */}
              <div style={{ marginTop: 12, height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                <div style={{
                  height: '100%', borderRadius: 2,
                  background: cfg.color,
                  animation: 'toastDrain 6s linear forwards',
                }} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
