import { useState } from 'react'

const TYPE = {
  latency_spike:   { label: 'Latency Spike',   color: '#f59e0b', glow: 'rgba(245,158,11,0.15)' },
  error_surge:     { label: 'Error Surge',      color: '#ef4444', glow: 'rgba(239,68,68,0.15)' },
  cascade_failure: { label: 'Cascade Failure',  color: '#ef4444', glow: 'rgba(239,68,68,0.2)'  },
}

export default function AnomalyFeed({ anomalies, aiAnalyses }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            Anomaly Feed
          </span>
          {anomalies.length > 0 && (
            <span style={{
              fontSize: 11, fontWeight: 700,
              background: anomalies.some(a => a.severity === 'critical') ? '#ef4444' : '#f59e0b',
              color: 'white', borderRadius: 20, padding: '1px 8px',
            }}>{anomalies.length}</span>
          )}
        </div>
      </div>

      {anomalies.length === 0 ? (
        <div style={{
          background: 'rgba(16,185,129,0.05)',
          border: '1px solid rgba(16,185,129,0.15)',
          borderRadius: 16, padding: '28px 24px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#10b981' }}>No anomalies detected</div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginTop: 4 }}>
            All endpoints operating within normal parameters
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {anomalies.slice(0, 12).map((a, i) => (
            <AnomalyRow key={`${a.detected_at}-${i}`} anomaly={a} analysis={aiAnalyses?.[a.id]} />
          ))}
        </div>
      )}
    </div>
  )
}

function AnomalyRow({ anomaly, analysis }) {
  const [open, setOpen] = useState(false)
  const t = TYPE[anomaly.anomaly_type] || TYPE.error_surge

  return (
    <div style={{
      background: open ? `rgba(255,255,255,0.04)` : 'rgba(255,255,255,0.025)',
      border: `1px solid ${open ? t.color + '30' : 'rgba(255,255,255,0.07)'}`,
      borderRadius: 12, overflow: 'hidden',
      transition: 'all 0.2s',
      boxShadow: open ? `0 4px 24px ${t.glow}` : 'none',
    }}>
      {/* Row header */}
      <div onClick={() => setOpen(!open)} style={{
        padding: '12px 16px', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        {/* Severity dot */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.color }} />
          {anomaly.severity === 'critical' && (
            <div style={{
              position: 'absolute', inset: -2, borderRadius: '50%',
              border: `1px solid ${t.color}`,
              animation: 'pulse-ring 1.5s ease-out infinite',
            }} />
          )}
        </div>

        {/* Badge */}
        <span style={{
          fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px',
          color: t.color, background: `${t.color}15`,
          padding: '2px 8px', borderRadius: 6, flexShrink: 0,
        }}>{t.label}</span>

        {/* Endpoint */}
        <span style={{ fontSize: 12, fontFamily: 'SF Mono, monospace', color: 'rgba(255,255,255,0.7)', flexShrink: 0 }}>
          {anomaly.endpoint === 'multiple' ? 'multiple' : anomaly.endpoint}
        </span>

        {/* Description */}
        <span style={{
          fontSize: 12, color: 'rgba(255,255,255,0.35)', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{anomaly.description}</span>

        {/* Time + chevron */}
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', flexShrink: 0 }}>
          {anomaly.detected_at?.slice(11, 19)}
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="2"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: '0.2s', flexShrink: 0 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Expanded details */}
      {open && (
        <div style={{ borderTop: '1px solid var(--text-06)', padding: 16 }}>
          {/* Root cause chain */}
          {anomaly.root_cause_chain?.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 10 }}>
                Root Cause Chain
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {anomaly.root_cause_chain.map((step, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 10, padding: '8px 12px',
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>{step.component}</div>
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>{step.signal}</div>
                      <div style={{ fontSize: 10, color: t.color, marginTop: 2, fontWeight: 600 }}>
                        {Math.round(step.confidence * 100)}% confidence
                      </div>
                    </div>
                    {i < anomaly.root_cause_chain.length - 1 && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Analysis */}
          {analysis ? (
            <div style={{
              background: 'rgba(37,99,235,0.08)',
              border: '1px solid rgba(37,99,235,0.2)',
              borderRadius: 12, padding: 14,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%',
                  background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>AI Diagnosis</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginLeft: 'auto' }}>
                  {analysis.model} · {analysis.analyzed_at?.slice(11, 19)}
                </span>
              </div>
              <pre style={{
                fontSize: 12, color: 'rgba(255,255,255,0.65)', lineHeight: 1.7,
                whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0,
              }}>{analysis.analysis}</pre>
            </div>
          ) : (
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 12, padding: '12px 14px',
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: 12, color: 'rgba(255,255,255,0.35)',
            }}>
              <div style={{
                width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
                border: '2px solid #2563eb', borderTopColor: 'transparent',
                animation: 'spin 0.8s linear infinite',
              }} />
              Analysing with AI…
            </div>
          )}
        </div>
      )}
    </div>
  )
}
