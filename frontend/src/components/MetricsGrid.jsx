import { useState, useRef } from 'react'

const STATUS = {
  healthy:  { color: '#10b981', glow: 'rgba(16,185,129,0.2)',  label: 'Healthy' },
  degraded: { color: '#f59e0b', glow: 'rgba(245,158,11,0.2)',  label: 'Degraded' },
  critical: { color: '#ef4444', glow: 'rgba(239,68,68,0.25)',  label: 'Critical' },
}

export default function MetricsGrid({ health, timeseries }) {
  const recent = timeseries.slice(-5)
  const rps = recent.length ? Math.round(recent.reduce((s, t) => s + (t.req_count || 0), 0) / recent.length) : 0
  const errors = recent.reduce((s, t) => s + (t.errors || 0), 0)
  const latency = recent.length ? Math.round(recent.reduce((s, t) => s + (t.avg_latency || 0), 0) / recent.length) : 0
  const endpoints = Object.entries(health)

  return (
    <div>
      {/* Top KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 16 }}>
        <KPICard label="Requests / sec" value={rps} color="#2563eb" icon="⚡" />
        <KPICard label="Avg Latency" value={latency} unit="ms" color="#7c3aed" icon="⏱" warn={latency > 400} />
        <KPICard label="Errors (5s)" value={errors} color="#ef4444" icon="✕" warn={errors > 5} />
      </div>

      {/* Endpoint cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(195px,1fr))', gap: 10 }}>
        {endpoints.length === 0
          ? <Placeholder />
          : endpoints.map(([ep, s]) => <EndpointCard key={ep} endpoint={ep} stats={s} />)
        }
      </div>
    </div>
  )
}

function KPICard({ label, value, unit, color, icon, warn }) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${warn ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.07)'}`,
        borderRadius: 16, padding: '18px 20px',
        transition: 'all 0.25s',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? `0 8px 32px ${warn ? 'rgba(239,68,68,0.15)' : `${color}20`}` : 'none',
        cursor: 'default',
      }}
    >
      <div style={{ fontSize: 20, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-1px', color: warn ? '#ef4444' : 'white' }}>
        {value}
        {unit && <span style={{ fontSize: 14, fontWeight: 500, color: 'rgba(255,255,255,0.35)', marginLeft: 4 }}>{unit}</span>}
      </div>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function EndpointCard({ endpoint, stats }) {
  const [hovered, setHovered] = useState(false)
  const cardRef = useRef(null)
  const s = STATUS[stats.status] || STATUS.healthy
  const short = endpoint.replace('/api/', '')

  const handleMouseMove = (e) => {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width - 0.5
    const y = (e.clientY - rect.top) / rect.height - 0.5
    cardRef.current.style.transform = `perspective(600px) rotateX(${-y * 8}deg) rotateY(${x * 8}deg) translateY(-2px)`
  }

  const handleMouseLeave = () => {
    if (cardRef.current) cardRef.current.style.transform = 'none'
    setHovered(false)
  }

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${hovered ? s.color + '40' : 'rgba(255,255,255,0.07)'}`,
        borderRadius: 14, padding: '14px 16px',
        transition: 'border 0.2s, box-shadow 0.2s',
        boxShadow: hovered ? `0 8px 32px ${s.glow}, inset 0 1px 0 rgba(255,255,255,0.05)` : 'none',
        cursor: 'default', position: 'relative', overflow: 'hidden',
        transformStyle: 'preserve-3d',
      }}
    >
      {/* Top accent line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, transparent, ${s.color}, transparent)`,
        opacity: stats.status === 'healthy' ? 0.3 : 1,
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.85)', fontFamily: 'SF Mono, monospace' }}>
          /{short}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px',
          color: s.color, background: `${s.color}15`,
          padding: '2px 8px', borderRadius: 20,
        }}>
          {s.label}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {[
          { label: 'Avg', val: `${stats.avg_latency_ms}ms`, warn: stats.avg_latency_ms > 400 },
          { label: 'P95', val: `${stats.p95_latency_ms}ms`, warn: stats.p95_latency_ms > 800 },
          { label: 'Errors', val: `${(stats.error_rate * 100).toFixed(1)}%`, warn: stats.error_rate > 0.1 },
          { label: 'n', val: stats.sample_size, warn: false },
        ].map(m => (
          <div key={m.label}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 2 }}>{m.label}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: m.warn ? '#ef4444' : 'rgba(255,255,255,0.75)' }}>{m.val}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Placeholder() {
  return (
    <div style={{
      gridColumn: '1/-1', padding: 32, textAlign: 'center',
      color: 'rgba(255,255,255,0.2)', fontSize: 13,
    }}>
      Collecting data…
    </div>
  )
}
