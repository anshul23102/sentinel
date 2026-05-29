const ENDPOINTS = [
  '/api/checkout',
  '/api/products',
  '/api/users/profile',
  '/api/cart',
  '/api/inventory',
  '/api/auth/login',
  '/api/orders',
  '/api/search',
]

const STATUS_BG = {
  healthy:  '#34d399',
  degraded: '#fbbf24',
  critical: '#f87171',
  unknown:  'rgba(255,255,255,0.07)',
}

export default function HealthHeatmap({ healthHistory }) {
  // Pad to always show 40 columns
  const COLS = 40
  const padded = healthHistory.length >= COLS
    ? healthHistory.slice(-COLS)
    : [
        ...Array(COLS - healthHistory.length).fill(null),
        ...healthHistory,
      ]

  return (
    <div style={{
      background: 'rgba(0,0,0,0.25)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 14, padding: '14px 16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Endpoint Health History
        </span>
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>· last {COLS} readings (5s each)</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
          {[
            { s: 'healthy',  c: '#34d399' },
            { s: 'degraded', c: '#fbbf24' },
            { s: 'critical', c: '#f87171' },
          ].map(x => (
            <div key={x.s} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: x.c }} />
              {x.s}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {ENDPOINTS.map(ep => (
          <div key={ep} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 100, flexShrink: 0,
              fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
              color: 'rgba(255,255,255,0.35)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              textAlign: 'right',
            }}>
              {ep.replace('/api/', '')}
            </div>
            <div style={{ display: 'flex', gap: 2, flex: 1 }}>
              {padded.map((snap, ci) => {
                const status = snap?.data?.[ep]?.status || (snap === null ? null : 'unknown')
                return (
                  <div
                    key={ci}
                    title={snap ? `${new Date(snap.ts).toLocaleTimeString()} — ${status}` : ''}
                    style={{
                      flex: 1, height: 12, borderRadius: 2,
                      background: status === null ? 'rgba(255,255,255,0.03)' : STATUS_BG[status] || STATUS_BG.unknown,
                      opacity: status === null ? 0.3 : 0.85,
                      transition: 'background 0.5s ease',
                    }}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 8, fontSize: 9, color: 'rgba(255,255,255,0.15)', textAlign: 'right' }}>
        older {'←'} newer
      </div>
    </div>
  )
}
