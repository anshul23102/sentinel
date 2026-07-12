import { useState, useCallback } from 'react'
import Markdown from '../components/Markdown'

const SEVERITY_STYLE = {
  critical: { color: '#f87171', bg: 'rgba(248,113,113,0.1)',  border: 'rgba(248,113,113,0.3)',  dot: '#f87171' },
  high:     { color: '#fb923c', bg: 'rgba(251,146,60,0.08)',  border: 'rgba(251,146,60,0.25)',  dot: '#fb923c' },
  medium:   { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.22)', dot: '#fbbf24' },
  low:      { color: '#a78bfa', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.2)', dot: '#a78bfa' },
}

const TYPE_LABEL = {
  latency_spike:   { label: 'Latency Spike', color: '#22d3ee', bg: 'rgba(34,211,238,0.1)',    border: 'rgba(34,211,238,0.22)' },
  error_surge:     { label: 'Error Surge',   color: '#f87171', bg: 'rgba(248,113,113,0.1)',  border: 'rgba(248,113,113,0.22)' },
  cascade_failure: { label: 'Cascade',       color: '#c084fc', bg: 'rgba(192,132,252,0.1)',  border: 'rgba(192,132,252,0.22)' },
}

const FILTERS = ['all', 'critical', 'cascade_failure', 'latency_spike', 'error_surge']

export default function Incidents({ anomalies, aiAnalyses }) {
  const [filter, setFilter] = useState('all')
  const [showExportMenu, setShowExportMenu] = useState(false)

  const handleExport = async (format) => {
  setShowExportMenu(false)
  try {
    const res = await fetch(`http://localhost:8000/api/incidents/export?format=${format}`)
    if (!res.ok) throw new Error('Export failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sentinel_incidents.${format}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert('Export failed. Make sure the backend is running.')
  }
}

  const filtered = filter === 'all' ? anomalies
    : filter === 'critical' ? anomalies.filter(a => a.severity === 'critical')
    : anomalies.filter(a => a.anomaly_type === filter)

  const counts = {
    all:             anomalies.length,
    critical:        anomalies.filter(a => a.severity === 'critical').length,
    cascade_failure: anomalies.filter(a => a.anomaly_type === 'cascade_failure').length,
    latency_spike:   anomalies.filter(a => a.anomaly_type === 'latency_spike').length,
    error_surge:     anomalies.filter(a => a.anomaly_type === 'error_surge').length,
  }
  return (
    <div style={{ padding: '64px 60px', maxWidth: 960 }}>

      {/* Header */}
      <div style={{ marginBottom: 44, textAlign: 'center' }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 14 }}>
          Observability
        </div>
        <h1 style={{
          fontSize: 48, fontWeight: 900, letterSpacing: '-2px', lineHeight: 1.1, marginBottom: 14,
          background: 'linear-gradient(135deg, #ffffff 20%, #c4b5fd 55%, #67e8f9 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        }}>
          Incidents
        </h1>
        <p style={{ fontSize: 15, color: 'rgba(255,255,255,0.38)', lineHeight: 1.7, maxWidth: 420, margin: '0 auto' }}>
          AI-diagnosed anomalies with root cause chains and actionable fix steps
        </p>
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 28, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.22)', textTransform: 'uppercase', letterSpacing: '0.7px', marginRight: 4 }}>Filter</span>
        {FILTERS.map(f => {
          const active = filter === f
          const count  = counts[f]
          return (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: '5px 13px', borderRadius: 20, fontSize: 11, fontWeight: active ? 600 : 400,
              border:     `1px solid ${active ? 'rgba(167,139,250,0.4)' : 'rgba(255,255,255,0.09)'}`,
              background: active ? 'rgba(139,92,246,0.15)' : 'transparent',
              color:      active ? '#c4b5fd' : 'rgba(255,255,255,0.42)',
              cursor: 'pointer', transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span>{f === 'all' ? 'All' : f === 'critical' ? 'Critical' : TYPE_LABEL[f]?.label || f}</span>
              {count > 0 && (
                <span style={{
                  fontSize: 9, fontWeight: 700, minWidth: 16, height: 16, borderRadius: 8,
                  background: active ? 'rgba(196,181,253,0.25)' : 'rgba(255,255,255,0.1)',
                  color: active ? '#ddd6fe' : 'rgba(255,255,255,0.5)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px',
                }}>{count}</span>
              )}
            </button>
          )
        })}
        <div
  style={{
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    position: 'relative',
  }}
>
  <button
  onClick={() => setShowExportMenu(!showExportMenu)}
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '7px 14px',
    borderRadius: 8,
    fontSize: 12,
    fontWeight: 600,
    background: showExportMenu ? 'rgba(139,92,246,0.2)' : 'rgba(139,92,246,0.08)',
    border: '1px solid rgba(139,92,246,0.35)',
    color: '#c4b5fd',
    cursor: 'pointer',
    transition: 'all 0.18s',
    letterSpacing: '0.3px',
  }}
  onMouseEnter={e => e.currentTarget.style.background = 'rgba(139,92,246,0.2)'}
  onMouseLeave={e => e.currentTarget.style.background = showExportMenu ? 'rgba(139,92,246,0.2)' : 'rgba(139,92,246,0.08)'}
>
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" strokeWidth="2.5">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
  Export
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" strokeWidth="2.5"
    style={{ transform: showExportMenu ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
</button>

  {showExportMenu && (
    <div
      style={{
        position: 'absolute',
        top: '40px',
        right: 0,
        background: '#1f1f2e',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8,
        padding: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        zIndex: 100,
      }}
    >
  <button onClick={() => handleExport('csv')} style={{
  padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
  background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)',
  color: '#c4b5fd', cursor: 'pointer',
}}>
  📄 CSV
</button>
<button onClick={() => handleExport('json')} style={{
  padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
  background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)',
  color: '#c4b5fd', cursor: 'pointer', width: '100%',
}}>
  {'{ }'} JSON
</button>
    </div>
  )}

  <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)' }}>
    {filtered.length} incident{filtered.length !== 1 ? 's' : ''}
  </span>
</div>
      </div>

      {filtered.length === 0 ? (
        <div style={{
          padding: '64px 48px', borderRadius: 16, textAlign: 'center',
          background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <div style={{ fontSize: 28, marginBottom: 16, opacity: 0.5 }}>✦</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'rgba(255,255,255,0.5)', marginBottom: 10 }}>
            {filter === 'all' ? 'No incidents detected' : `No ${filter} incidents`}
          </div>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.3)', lineHeight: 1.8, maxWidth: 340, margin: '0 auto' }}>
            Inject a failure from the Overview page to see AI diagnosis in action.
            Try <span style={{ color: '#c4b5fd', fontWeight: 600 }}>"DB Slowdown"</span> — incidents appear within 5 seconds.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map((a, i) => (
            <IncidentCard
              key={`${a.detected_at}-${i}`}
              anomaly={a}
              analysis={a.id != null ? aiAnalyses?.[a.id] : null}
              open={i < 2}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }, [text])
  return (
    <button onClick={copy} style={{
      padding: '3px 10px', borderRadius: 8, fontSize: 10, fontWeight: 600,
      border: `1px solid ${copied ? 'rgba(52,211,153,0.35)' : 'rgba(255,255,255,0.1)'}`,
      background: copied ? 'rgba(52,211,153,0.1)' : 'rgba(255,255,255,0.04)',
      color: copied ? '#6ee7b7' : 'rgba(255,255,255,0.4)',
      cursor: 'pointer', transition: 'all 0.18s', flexShrink: 0,
    }}>
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

function IncidentCard({ anomaly, analysis, open: defaultOpen, index }) {
  const [open, setOpen] = useState(defaultOpen)
  const typeInfo = TYPE_LABEL[anomaly.anomaly_type] || { label: 'Anomaly', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.2)' }
  const sevStyle = SEVERITY_STYLE[anomaly.severity] || SEVERITY_STYLE.low

  return (
    <div style={{
      background: open ? `${sevStyle.bg}` : 'rgba(255,255,255,0.025)',
      border: `1px solid ${open ? sevStyle.border : 'rgba(255,255,255,0.08)'}`,
      borderLeft: `3px solid ${open ? sevStyle.dot : 'rgba(255,255,255,0.1)'}`,
      borderRadius: 14, overflow: 'hidden',
      transition: 'all 0.22s ease',
      animation: `fadeUp 0.38s ease ${index * 0.04}s both`,
    }}>

      {/* Row */}
      <div
        onClick={() => setOpen(!open)}
        style={{ padding: '14px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}
      >
        {/* Severity dot */}
        <div style={{
          width: 7, height: 7, borderRadius: '50%', background: sevStyle.dot, flexShrink: 0,
          boxShadow: anomaly.severity === 'critical' ? `0 0 10px ${sevStyle.dot}` : 'none',
          animation: anomaly.severity === 'critical' ? 'pulse 1.4s infinite' : 'none',
        }} />

        {/* Type badge */}
        <span style={{
          fontSize: 10, fontWeight: 700, color: typeInfo.color,
          background: typeInfo.bg, border: `1px solid ${typeInfo.border}`,
          padding: '2px 9px', borderRadius: 20, flexShrink: 0,
        }}>{typeInfo.label}</span>

        {/* Severity badge */}
        <span style={{
          fontSize: 10, fontWeight: 600, textTransform: 'capitalize',
          color: sevStyle.color, background: sevStyle.bg, border: `1px solid ${sevStyle.border}`,
          padding: '2px 9px', borderRadius: 20, flexShrink: 0,
        }}>{anomaly.severity}</span>

        {/* Endpoint */}
        <span style={{
          fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
          color: 'rgba(255,255,255,0.7)', flexShrink: 0,
          cursor: 'text',
        }}
          onClick={e => { e.stopPropagation(); navigator.clipboard?.writeText(anomaly.endpoint) }}
          title="Click to copy"
        >
          {anomaly.endpoint === 'multiple' ? 'multiple endpoints' : anomaly.endpoint}
        </span>

        {/* Description */}
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {anomaly.description}
        </span>

        {/* Time */}
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', flexShrink: 0, fontFamily: 'monospace' }}>
          {anomaly.detected_at?.slice(11, 19)}
        </span>

        {/* Chevron */}
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="2"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: '0.22s', flexShrink: 0 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Expanded */}
      {open && (
        <div style={{ borderTop: `1px solid ${sevStyle.border}`, padding: '20px 20px' }}>

          {/* Root cause chain */}
          {anomaly.root_cause_chain?.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.9px', marginBottom: 12 }}>
                Root Cause Chain
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {anomaly.root_cause_chain.map((step, i) => {
                  const conf = Math.round(step.confidence * 100)
                  const confColor = conf >= 80 ? '#f87171' : conf >= 60 ? '#fbbf24' : '#a78bfa'
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 10, padding: '10px 14px',
                      }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.88)', marginBottom: 3 }}>{step.component}</div>
                        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginBottom: 6 }}>{step.signal}</div>
                        <div style={{
                          fontSize: 10, color: confColor, fontWeight: 700,
                          background: `${confColor}18`, border: `1px solid ${confColor}33`,
                          padding: '2px 8px', borderRadius: 20, display: 'inline-block',
                        }}>{conf}% confidence</div>
                      </div>
                      {i < anomaly.root_cause_chain.length - 1 && (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2">
                          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                        </svg>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* AI diagnosis */}
          {analysis ? (
            <div style={{
              background: 'rgba(139,92,246,0.06)',
              border: '1px solid rgba(139,92,246,0.18)',
              borderRadius: 12, padding: '16px 18px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
                <div style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: 'linear-gradient(135deg, #7c3aed, #a78bfa)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  boxShadow: '0 0 12px rgba(124,58,237,0.4)',
                }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>AI Diagnosis</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', marginRight: 'auto' }}>
                  {analysis.analyzed_at?.slice(11, 19)} · {analysis.model?.split('-')[0]}
                </span>
                <CopyButton text={analysis.analysis} />
              </div>
              <Markdown text={analysis.analysis} />
            </div>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '13px 16px', borderRadius: 12,
              background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.08)',
              fontSize: 13, color: 'rgba(255,255,255,0.4)',
            }}>
              <div style={{
                width: 14, height: 14, borderRadius: '50%',
                border: '2px solid #8b5cf6', borderTopColor: 'transparent',
                animation: 'spin 0.8s linear infinite', flexShrink: 0,
              }} />
              Analysing root cause with AI...
            </div>
          )}
        </div>
      )}
    </div>
  )
}
