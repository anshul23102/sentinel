import { useRef, useEffect } from 'react'
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts'

const INFO = {
  '/api/checkout':      { desc: 'Payment processing and order creation', team: 'Payments',  sla: 200, icon: '💳', method: 'POST' },
  '/api/products':      { desc: 'Product catalog, listings and detail',  team: 'Catalog',   sla: 150, icon: '📦', method: 'GET'  },
  '/api/users/profile': { desc: 'User account data and preferences',     team: 'Identity',  sla: 100, icon: '👤', method: 'GET'  },
  '/api/cart':          { desc: 'Shopping cart state management',        team: 'Cart',      sla: 120, icon: '🛒', method: 'POST' },
  '/api/inventory':     { desc: 'Real-time stock level queries',         team: 'Warehouse', sla: 180, icon: '🏭', method: 'GET'  },
  '/api/auth/login':    { desc: 'OAuth2 authentication and token issue', team: 'Identity',  sla: 100, icon: '🔐', method: 'POST' },
  '/api/orders':        { desc: 'Order history and fulfillment status',  team: 'Orders',    sla: 150, icon: '📋', method: 'GET'  },
  '/api/search':        { desc: 'Full-text product and category search', team: 'Search',    sla: 200, icon: '🔍', method: 'GET'  },
}

const STATUS_STYLE = {
  critical: { color: '#fca5a5', bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.28)', dot: '#f87171' },
  degraded: { color: '#fde68a', bg: 'rgba(251,191,36,0.1)',   border: 'rgba(251,191,36,0.25)',  dot: '#fbbf24' },
  healthy:  { color: '#6ee7b7', bg: 'rgba(52,211,153,0.1)',   border: 'rgba(52,211,153,0.22)',  dot: '#34d399' },
}

const MAX_HISTORY = 20

export default function Endpoints({ health }) {
  // Rolling per-endpoint latency history: { [endpoint]: [{latency}] }
  const historyRef = useRef({})

  useEffect(() => {
    Object.entries(health).forEach(([ep, stats]) => {
      const prev = historyRef.current[ep] || []
      historyRef.current[ep] = [
        ...prev,
        { latency: stats.avg_latency_ms }
      ].slice(-MAX_HISTORY)
    })
  }, [health])

  const entries = Object.entries(health).sort(([, a], [, b]) =>
    ({ critical: 0, degraded: 1, healthy: 2 }[a.status] || 2) -
    ({ critical: 0, degraded: 1, healthy: 2 }[b.status] || 2)
  )

  const counts = {
    healthy:  entries.filter(([, s]) => s.status === 'healthy').length,
    degraded: entries.filter(([, s]) => s.status === 'degraded').length,
    critical: entries.filter(([, s]) => s.status === 'critical').length,
  }

  const overallUptime = entries.length
    ? Math.round(entries.reduce((sum, [, s]) => sum + (s.uptime_pct ?? 100), 0) / entries.length)
    : 100

  return (
    <div style={{ padding: '64px 60px', maxWidth: 980, width: '100%', boxSizing: 'border-box' }}>

      {/* Header */}
      <div style={{ marginBottom: 50, textAlign: 'center' }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-38)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 14 }}>
          Infrastructure
        </div>
        <h1 style={{
          fontSize: 48, fontWeight: 900, letterSpacing: '-2px', lineHeight: 1.1, marginBottom: 14,
          background: 'var(--heading-gradient)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        }}>
          API Endpoints
        </h1>
        <p style={{ fontSize: 15, color: 'var(--text-38)', lineHeight: 1.7 }}>
          {entries.length} monitored services — sorted by severity
        </p>
      </div>

      {/* Summary tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 36 }}>
        {[
          { label: 'Healthy',    count: counts.healthy,  sub: 'Operating normally',        st: 'healthy'  },
          { label: 'Degraded',   count: counts.degraded, sub: 'Elevated latency / errors',  st: 'degraded' },
          { label: 'Critical',   count: counts.critical, sub: 'Immediate action required',  st: 'critical' },
          { label: 'Avg Uptime', count: `${overallUptime}%`, sub: 'last 60s window',        st: overallUptime >= 99 ? 'healthy' : overallUptime >= 90 ? 'degraded' : 'critical' },
        ].map(s => {
          const ss = STATUS_STYLE[s.st]
          return (
            <div key={s.label} style={{
              padding: '18px 20px', borderRadius: 14,
              background: s.count > 0 || s.label === 'Avg Uptime' ? ss.bg : 'var(--bg-025)',
              border: `1px solid ${s.count > 0 ? ss.border : 'var(--text-06)'}`,
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-32)', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 8 }}>
                {s.label}
              </div>
              <div style={{
                fontSize: 28, fontWeight: 800, letterSpacing: '-1px',
                color: s.count > 0 || s.label === 'Avg Uptime' ? ss.color : 'var(--text-50)',
                textShadow: s.count > 0 ? `0 0 14px ${ss.dot}44` : 'none',
              }}>{s.count}</div>
              <div style={{ fontSize: 11, color: 'var(--text-30)', marginTop: 4 }}>{s.sub}</div>
            </div>
          )
        })}
      </div>

      {/* Endpoint list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {entries.length === 0
          ? (
            <div style={{
              textAlign: 'center', padding: 64,
              background: 'var(--bg-02)', border: '1px solid var(--text-06)', borderRadius: 16,
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-25)' }}>Collecting endpoint data...</div>
              <div style={{ fontSize: 11, color: 'var(--text-25)', marginTop: 8 }}>Logs start flowing within a few seconds</div>
            </div>
          )
          : entries.map(([ep, stats], i) => (
            <EndpointRow
              key={ep}
              endpoint={ep}
              stats={stats}
              index={i}
              latencyHistory={historyRef.current[ep] || []}
            />
          ))
        }
      </div>
    </div>
  )
}

function LatencySparkline({ data, status }) {
  if (data.length < 2) return (
    <div style={{ width: 140, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>building…</span>
    </div>
  )

  const color = status === 'critical' ? '#f87171' : status === 'degraded' ? '#fbbf24' : '#34d399'

  return (
    <div style={{ width: 140, height: 44 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 2, left: 2, bottom: 0 }}>
          <defs>
            <linearGradient id={`spark-${status}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="latency"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#spark-${status})`}
            dot={false}
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={{
              background: 'rgba(15,15,25,0.92)',
              border: `1px solid ${color}44`,
              borderRadius: 6,
              fontSize: 11,
              padding: '3px 8px',
              color: 'rgba(255,255,255,0.8)',
            }}
            formatter={(v) => [`${v}ms`, 'latency']}
            labelFormatter={() => ''}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function EndpointRow({ endpoint, stats, index, latencyHistory }) {
  const info   = INFO[endpoint] || { desc: 'API endpoint', team: 'Engineering', sla: 200, icon: '🔧', method: 'GET' }
  const ss     = STATUS_STYLE[stats.status] || STATUS_STYLE.healthy
  const isAlert = stats.status !== 'healthy'
  const latPct  = Math.min(100, (stats.avg_latency_ms / (info.sla * 3)) * 100)
  const slaOk   = stats.avg_latency_ms <= info.sla
  const slaBreached = stats.avg_latency_ms > info.sla
  const uptime  = stats.uptime_pct ?? 100
  const ref     = useRef(null)

  const latBarBg = latPct > 80
    ? 'linear-gradient(90deg, #dc2626, #f87171)'
    : latPct > 50
      ? 'linear-gradient(90deg, #d97706, #fbbf24)'
      : 'linear-gradient(90deg, #059669, #34d399)'

  const onMove = (e) => {
    const el = ref.current; if (!el) return
    const r  = el.getBoundingClientRect()
    const rx = (((e.clientY - r.top)  / r.height) - 0.5) * -4
    const ry = (((e.clientX - r.left) / r.width)  - 0.5) *  4
    el.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg)`
  }
  const onLeave = () => { if (ref.current) ref.current.style.transform = 'none' }

  return (
    <div
      ref={ref}
      className="tilt-card"
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        padding: '20px 22px', borderRadius: 14,
        background: isAlert ? `${ss.bg}` : 'rgba(255,255,255,0.022)',
        border: `1px solid ${isAlert ? ss.border : 'var(--text-06)'}`,
        boxShadow: isAlert ? `0 0 20px ${ss.dot}11` : 'none',
        animation: `fadeUp 0.4s ease ${index * 0.04}s both`,
        transition: 'box-shadow 0.4s ease, background 0.4s ease',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 20, alignItems: 'start' }}>

        {/* Left */}
        <div>
          {/* Endpoint header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 16 }}>{info.icon}</span>

            <span style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.3px',
              background: 'var(--text-06)', border: '1px solid rgba(255,255,255,0.1)',
              color: 'var(--text-50)', padding: '1px 8px', borderRadius: 5,
            }}>
              {info.method}
            </span>

            <span style={{ fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(255,255,255,0.92)' }}>
              {endpoint}
            </span>

            <span style={{
              fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px',
              color: ss.color, background: ss.bg, border: `1px solid ${ss.border}`,
              padding: '2px 9px', borderRadius: 20,
              textShadow: `0 0 8px ${ss.dot}55`,
            }}>
              {stats.status}
            </span>

            {isAlert && (
              <div style={{
                width: 6, height: 6, borderRadius: '50%', background: ss.dot,
                boxShadow: `0 0 6px ${ss.dot}`, animation: 'pulse 1.2s infinite',
              }} />
            )}
          </div>

          {/* Meta row */}
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.42)', marginBottom: 14, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span>{info.desc}</span>
            <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>
            <span style={{ color: '#c4b5fd', fontWeight: 500 }}>{info.team}</span>
            <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>
            <span>
              SLA <span style={{ fontWeight: 700, color: slaOk ? '#34d399' : '#f87171' }}>{info.sla}ms</span>
            </span>
            {slaBreached && (
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: '#f87171', background: 'rgba(248,113,113,0.1)',
                border: '1px solid rgba(248,113,113,0.25)',
                padding: '1px 8px', borderRadius: 20,
              }}>
                SLA BREACHED +{Math.round(stats.avg_latency_ms - info.sla)}ms
              </span>
            )}
          </div>

          {/* Latency bar */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-38)', marginBottom: 6 }}>
              <span>Response time vs SLA</span>
              <span style={{ fontWeight: 600, color: slaOk ? 'var(--text-50)' : '#f87171' }}>
                {stats.avg_latency_ms}ms avg
              </span>
            </div>
            <div style={{ height: 5, background: 'rgba(255,255,255,0.05)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
              <div style={{
                position: 'absolute', left: `${Math.min(100, (info.sla / (info.sla * 3)) * 100)}%`,
                top: 0, bottom: 0, width: 1, background: 'rgba(255,255,255,0.2)', zIndex: 1,
              }} />
              <div style={{
                height: '100%', borderRadius: 4, width: `${latPct}%`,
                background: latBarBg,
                transition: 'width 0.7s cubic-bezier(0.4,0,0.2,1)',
                boxShadow: latPct > 50 ? `0 0 8px ${latPct > 80 ? '#f8717166' : '#fbbf2466'}` : 'none',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(255,255,255,0.2)', marginTop: 4 }}>
              <span>0ms</span>
              <span style={{ color: 'rgba(255,255,255,0.28)' }}>SLA {info.sla}ms</span>
              <span>{info.sla * 3}ms</span>
            </div>
          </div>
        </div>

        {/* Right: sparkline + metric tiles */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 180 }}>

          {/* Sparkline */}
          <div style={{
            background: 'rgba(255,255,255,0.025)',
            border: `1px solid ${isAlert ? ss.border : 'rgba(255,255,255,0.06)'}`,
            borderRadius: 10,
            padding: '6px 8px 2px',
          }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: 'rgba(255,255,255,0.28)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 2 }}>
              Latency trend
            </div>
            <LatencySparkline data={latencyHistory} status={stats.status} />
          </div>

          {/* Metric tiles */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            {[
              { label: 'Error Rate',  val: `${(stats.error_rate * 100).toFixed(1)}%`, warn: stats.error_rate > 0.05, warnColor: '#f87171' },
              { label: 'P95 Latency', val: `${stats.p95_latency_ms}ms`, warn: stats.p95_latency_ms > info.sla * 2, warnColor: '#fbbf24' },
              { label: 'Avg Latency', val: `${stats.avg_latency_ms}ms`, warn: !slaOk, warnColor: '#f87171' },
              { label: 'Uptime',      val: `${uptime}%`, warn: uptime < 95, warnColor: uptime < 90 ? '#f87171' : '#fbbf24' },
            ].map(m => (
              <div key={m.label} style={{
                background: m.warn ? `rgba(${m.warnColor === '#f87171' ? '248,113,113' : '251,191,36'},0.08)` : 'rgba(255,255,255,0.025)',
                border: `1px solid ${m.warn ? (m.warnColor === '#f87171' ? 'rgba(248,113,113,0.2)' : 'rgba(251,191,36,0.18)') : 'rgba(255,255,255,0.06)'}`,
                borderRadius: 10, padding: '10px 12px',
              }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.42)', marginBottom: 5, fontWeight: 500 }}>{m.label}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: m.warn ? m.warnColor : 'rgba(255,255,255,0.78)' }}>{m.val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}