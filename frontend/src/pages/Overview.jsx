import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import LiveChart from '../components/LiveChart'
import ServiceGraph from '../components/ServiceGraph'
import HealthHeatmap from '../components/HealthHeatmap'

const SCENARIOS = {
  normal:             { label: 'Normal',        color: '#a78bfa', desc: 'Healthy baseline: ~80ms, <1% errors' },
  db_slowdown:        { label: 'DB Slowdown',   color: '#fbbf24', desc: 'Connection pool exhaustion, checkout cascade' },
  memory_leak:        { label: 'Memory Leak',   color: '#fb923c', desc: 'Heap growth, search and products degrade slowly' },
  rate_limit_cascade: { label: 'Rate Limit',    color: '#f87171', desc: 'Auth 429s, login failures across users' },
  network_partition:  { label: 'Net Partition', color: '#e879f9', desc: 'Inventory unreachable, 60% checkout fails' },
}

const BASELINE = { latency: 80, errorRate: 1.0 }

function useFlash(value, threshold = 0.1) {
  const [flash, setFlash]  = useState(false)
  const prevRef            = useRef(value)
  useEffect(() => {
    const prev = prevRef.current
    if (prev !== 0 && Math.abs((value - prev) / prev) > threshold) {
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 500)
      return () => clearTimeout(t)
    }
    prevRef.current = value
  }, [value, threshold])
  return flash
}

function computeScore(health) {
  const entries = Object.values(health)
  if (entries.length === 0) return 100
  const criticals = entries.filter(h => h.status === 'critical').length
  const degraded  = entries.filter(h => h.status === 'degraded').length
  return Math.max(0, 100 - criticals * 18 - degraded * 7)
}

function TiltCard({ children, style = {}, warn = false, flash = false }) {
  const ref = useRef(null)
  const onMove = (e) => {
    const el = ref.current; if (!el) return
    const r  = el.getBoundingClientRect()
    const rx = (((e.clientY - r.top)  / r.height) - 0.5) * -10
    const ry = (((e.clientX - r.left) / r.width)  - 0.5) *  10
    el.style.transform = `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(4px)`
  }
  const onLeave = () => { if (ref.current) ref.current.style.transform = 'none' }

  return (
    <div
      ref={ref}
      className="tilt-card"
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        padding: '22px 24px', borderRadius: 16,
        background: warn ? 'rgba(139,92,246,0.08)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${warn ? 'rgba(139,92,246,0.28)' : 'rgba(255,255,255,0.07)'}`,
        boxShadow: warn
          ? '0 0 28px rgba(139,92,246,0.12), inset 0 1px 0 rgba(255,255,255,0.06)'
          : 'inset 0 1px 0 rgba(255,255,255,0.03)',
        transition: 'background 0.4s ease, border-color 0.4s ease, box-shadow 0.4s ease',
        animation: flash ? 'kpiFlash 0.45s ease' : 'none',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function Delta({ current, baseline }) {
  if (!current || current === 0) return null
  const pct = Math.round(((current - baseline) / baseline) * 100)
  if (Math.abs(pct) < 15) return null
  const up = pct > 0
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 20,
      background: up ? 'rgba(248,113,113,0.15)' : 'rgba(52,211,153,0.12)',
      color:      up ? '#fca5a5' : '#6ee7b7',
      border:     up ? '1px solid rgba(248,113,113,0.25)' : '1px solid rgba(52,211,153,0.2)',
      letterSpacing: '0.3px',
      animation: 'fadeIn 0.3s ease',
    }}>
      {up ? '+' : ''}{pct}%
    </span>
  )
}

function CriticalCard({ critical, health }) {
  const ref = useRef(null)
  const isAlert = critical > 0

  const onMove = (e) => {
    const el = ref.current; if (!el) return
    const r  = el.getBoundingClientRect()
    const rx = (((e.clientY - r.top)  / r.height) - 0.5) * -10
    const ry = (((e.clientX - r.left) / r.width)  - 0.5) *  10
    el.style.transform = `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(4px)`
  }
  const onLeave = () => { if (ref.current) ref.current.style.transform = 'none' }

  const affectedList = Object.entries(health)
    .filter(([, s]) => s.status === 'critical')
    .map(([ep]) => ep.replace('/api/', ''))
    .slice(0, 2)

  return (
    <div
      ref={ref}
      className="tilt-card"
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        padding: '22px 24px', borderRadius: 16,
        background: isAlert ? 'rgba(139,92,246,0.13)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${isAlert ? 'rgba(139,92,246,0.45)' : 'rgba(255,255,255,0.07)'}`,
        boxShadow: isAlert
          ? '0 0 40px rgba(139,92,246,0.22), 0 0 80px rgba(139,92,246,0.1), inset 0 1px 0 rgba(255,255,255,0.1)'
          : 'inset 0 1px 0 rgba(255,255,255,0.03)',
        animation: isAlert ? 'criticalPulse 2s ease-in-out infinite' : 'none',
        transition: 'background 0.4s ease, border-color 0.4s ease, box-shadow 0.4s ease',
        position: 'relative', overflow: 'hidden',
      }}
    >
      {isAlert && (
        <div style={{
          position: 'absolute', inset: -1, borderRadius: 16,
          border: '1px solid rgba(167,139,250,0.6)',
          animation: 'ringPulse 1.8s ease-in-out infinite',
          pointerEvents: 'none',
        }} />
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: isAlert ? 'rgba(196,181,253,0.7)' : 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.7px' }}>
          Critical
        </div>
        {isAlert && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '2px 9px', borderRadius: 20,
            background: 'rgba(139,92,246,0.25)', border: '1px solid rgba(167,139,250,0.5)',
          }}>
            <div style={{
              width: 5, height: 5, borderRadius: '50%', background: '#c4b5fd',
              boxShadow: '0 0 6px rgba(196,181,253,1)', animation: 'pulse 1s infinite',
            }} />
            <span style={{ fontSize: 9, fontWeight: 800, color: '#ddd6fe', letterSpacing: '0.8px' }}>ALERT</span>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: 8 }}>
        <span
          key={critical}
          style={{
            fontSize: 34, fontWeight: 800, letterSpacing: '-1.5px',
            color: isAlert ? '#ffffff' : 'rgba(255,255,255,0.45)',
            animation: 'kpiCount 0.3s ease',
            display: 'inline-block',
            textShadow: isAlert ? '0 0 24px rgba(196,181,253,0.8)' : 'none',
          }}
        >{critical}</span>
        <span style={{ fontSize: 12, color: isAlert ? 'rgba(196,181,253,0.6)' : 'rgba(255,255,255,0.22)', fontWeight: 500 }}>
          {critical === 1 ? 'endpoint' : 'endpoints'}
        </span>
      </div>

      <div style={{ fontSize: 11, color: isAlert ? 'rgba(196,181,253,0.85)' : 'rgba(255,255,255,0.3)', lineHeight: 1.5 }}>
        {isAlert
          ? affectedList.length > 0
            ? affectedList.join(', ') + (critical > 2 ? ` +${critical - 2} more` : '') + ' down'
            : `${critical} service${critical > 1 ? 's' : ''} down`
          : 'All services nominal'
        }
      </div>
    </div>
  )
}

function LiveLogStream({ recentLogs }) {
  const logs = recentLogs.slice(0, 10)

  function statusColor(code) {
    if (code >= 500) return '#f87171'
    if (code >= 400) return '#fbbf24'
    return '#34d399'
  }

  function latColor(ms) {
    if (ms > 1000) return '#f87171'
    if (ms > 300)  return '#fbbf24'
    return 'rgba(255,255,255,0.45)'
  }

  return (
    <div style={{
      background: 'rgba(0,0,0,0.4)',
      border: '1px solid rgba(139,92,246,0.15)',
      borderRadius: 14, padding: '16px 18px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <div style={{ display: 'flex', gap: 5 }}>
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: 'rgba(248,113,113,0.8)' }} />
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: 'rgba(251,191,36,0.8)' }} />
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: 'rgba(52,211,153,0.8)' }} />
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.6px' }}>
          LIVE LOG STREAM
        </span>
        <div style={{
          marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%',
          background: '#a78bfa', boxShadow: '0 0 6px rgba(167,139,250,0.9)', animation: 'pulse 1.5s infinite',
        }} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {logs.length === 0 ? (
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', fontFamily: 'monospace', padding: '8px 0' }}>
            Waiting for logs...
          </div>
        ) : logs.map((log, i) => (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11, lineHeight: 1.6,
              animation: i === 0 ? 'logEntry 0.2s ease' : 'none',
              padding: '2px 0',
            }}
          >
            <span style={{ color: 'rgba(255,255,255,0.2)', flexShrink: 0, minWidth: 46 }}>
              {log.timestamp?.slice(11, 19) || '--:--:--'}
            </span>
            <span style={{
              color: statusColor(log.status_code), fontWeight: 700, flexShrink: 0, minWidth: 32,
              textShadow: `0 0 6px ${statusColor(log.status_code)}66`,
            }}>
              {log.status_code}
            </span>
            <span style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0, minWidth: 32, fontSize: 10 }}>
              {log.method}
            </span>
            <span style={{ color: 'rgba(167,139,250,0.9)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {log.endpoint}
            </span>
            <span style={{ color: latColor(log.latency_ms), flexShrink: 0, minWidth: 60, textAlign: 'right' }}>
              {Math.round(log.latency_ms)}ms
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

const DEMO_SEQUENCE = ['db_slowdown', 'rate_limit_cascade', 'network_partition', 'memory_leak', 'normal']
const DEMO_DURATION = 12 // seconds per scenario

// Simple linear slope via least-squares (for trend analysis)
function linearSlope(vals) {
  const n = vals.length
  if (n < 3) return 0
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0
  for (let i = 0; i < n; i++) {
    sumX += i; sumY += vals[i]; sumXY += i * vals[i]; sumX2 += i * i
  }
  return (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX) || 0
}

function PredictiveInsights({ timeseries, health }) {
  const insights = useMemo(() => {
    if (!timeseries || timeseries.length < 6) return []
    const recent = timeseries.slice(-10)
    const lats   = recent.map(d => d.avg_latency || 0)
    const errs   = recent.map(d => d.req_count > 0 ? (d.errors || 0) / d.req_count * 100 : 0)
    const latSlope = linearSlope(lats)
    const errSlope = linearSlope(errs)
    const curLat   = lats[lats.length - 1] || 0
    const curErr   = errs[errs.length - 1] || 0
    const results  = []

    if (latSlope > 12) {
      const sla = 200
      const minsLeft = Math.max(0.5, (sla - curLat) / (latSlope * 12))
      results.push({
        type: curLat > sla ? 'critical' : 'warning',
        icon: '⏱',
        title: curLat > sla ? 'SLA Breached' : `SLA breach in ~${minsLeft < 1 ? '<1' : Math.round(minsLeft)}m`,
        body: `Latency trending +${latSlope.toFixed(0)}ms/s · current ${Math.round(curLat)}ms vs 200ms SLA`,
      })
    }

    if (errSlope > 1.5 && curErr > 5) {
      results.push({
        type: 'critical',
        icon: '🔴',
        title: 'Error rate escalating',
        body: `Error rate at ${curErr.toFixed(1)}% and climbing +${errSlope.toFixed(1)}%/s — intervention needed`,
      })
    }

    const criticals = Object.values(health).filter(h => h.status === 'critical').length
    if (criticals > 0 && results.length === 0) {
      results.push({
        type: 'warning',
        icon: '⚡',
        title: `${criticals} service${criticals > 1 ? 's' : ''} in critical state`,
        body: 'Cascade failure risk elevated. Check service dependency graph below.',
      })
    }

    if (results.length === 0 && curLat < 120 && curErr < 2) {
      results.push({
        type: 'ok',
        icon: '✦',
        title: 'System stable',
        body: `All metrics nominal · ${Math.round(curLat)}ms avg latency · ${curErr.toFixed(1)}% error rate`,
      })
    }

    return results
  }, [timeseries, health])

  if (!insights.length) return null

  const COLOR = {
    critical: { bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.22)', text: '#fca5a5', icon: '#f87171' },
    warning:  { bg: 'rgba(251,191,36,0.07)',  border: 'rgba(251,191,36,0.2)',   text: '#fde68a', icon: '#fbbf24' },
    ok:       { bg: 'rgba(52,211,153,0.07)',   border: 'rgba(52,211,153,0.18)',  text: '#6ee7b7', icon: '#34d399' },
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 44 }}>
      {insights.map((ins, i) => {
        const c = COLOR[ins.type]
        return (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '13px 16px', borderRadius: 12,
            background: c.bg, border: `1px solid ${c.border}`,
            backdropFilter: 'blur(16px)',
            animation: 'fadeUp 0.3s ease',
          }}>
            <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>{ins.icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: c.text, marginBottom: 2 }}>{ins.title}</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.42)', lineHeight: 1.5 }}>{ins.body}</div>
            </div>
            <div style={{
              fontSize: 9, fontWeight: 700, color: c.icon, textTransform: 'uppercase', letterSpacing: '0.5px',
              padding: '2px 8px', borderRadius: 20, border: `1px solid ${c.border}`, flexShrink: 0,
            }}>AI Prediction</div>
          </div>
        )
      })}
    </div>
  )
}

export default function Overview({ health, healthHistory, timeseries, anomalies, currentScenario, injectScenario, liveStats, recentLogs }) {
  const scenario = SCENARIOS[currentScenario] || SCENARIOS.normal

  const latency  = liveStats?.avgLatency  || 0
  const errPct   = liveStats?.errorRate   || 0
  const rps      = liveStats?.rps         || 0
  const maxLat   = liveStats?.maxLatency  || 0
  const critical = Object.values(health).filter(h => h.status === 'critical').length
  const score    = computeScore(health)
  const scoreColor = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'

  const latFlash = useFlash(latency, 0.2)
  const errFlash = useFlash(errPct, 0.2)

  // Demo auto-play
  const [demoRunning, setDemoRunning]   = useState(false)
  const [demoCountdown, setDemoCountdown] = useState(DEMO_DURATION)
  const [demoIdx, setDemoIdx]           = useState(0)
  const demoTickRef                     = useRef(null)

  const stopDemo = useCallback(() => {
    clearInterval(demoTickRef.current)
    demoTickRef.current = null
    setDemoRunning(false)
    setDemoCountdown(DEMO_DURATION)
    setDemoIdx(0)
  }, [])

  const startDemo = useCallback(() => {
    setDemoRunning(true)
    setDemoIdx(0)
    setDemoCountdown(DEMO_DURATION)
    injectScenario(DEMO_SEQUENCE[0])

    let idx = 0
    let tick = DEMO_DURATION

    demoTickRef.current = setInterval(() => {
      tick -= 1
      setDemoCountdown(tick)
      if (tick <= 0) {
        idx = (idx + 1) % DEMO_SEQUENCE.length
        tick = DEMO_DURATION
        setDemoIdx(idx)
        setDemoCountdown(DEMO_DURATION)
        injectScenario(DEMO_SEQUENCE[idx])
        // Stop after full cycle
        if (idx === 0) {
          clearInterval(demoTickRef.current)
          demoTickRef.current = null
          setDemoRunning(false)
          setDemoCountdown(DEMO_DURATION)
        }
      }
    }, 1000)
  }, [injectScenario])

  // Cleanup on unmount
  useEffect(() => () => { stopDemo() }, [stopDemo])

  const normalKpis = [
    {
      label: 'Requests / sec', value: rps, unit: 'rps', warn: false,
      sub: 'live across all services',
    },
    {
      label: 'Avg Latency', value: latency, unit: 'ms', warn: latency > 200,
      sub: maxLat > latency ? `peak ${maxLat}ms` : 'within SLA',
      delta: <Delta current={latency} baseline={BASELINE.latency} />,
      flash: latFlash,
    },
    {
      label: 'Error Rate', value: `${errPct}`, unit: '%', warn: errPct > 5,
      sub: errPct > 30 ? 'critical threshold' : errPct > 5 ? 'above threshold' : 'nominal',
      delta: <Delta current={errPct} baseline={BASELINE.errorRate} />,
      flash: errFlash,
    },
  ]

  return (
    <div style={{ padding: '64px 56px', maxWidth: 1020, width: '100%', boxSizing: 'border-box' }}>

      {/* Hero */}
      <div style={{ marginBottom: 52, textAlign: 'center' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, marginBottom: 18,
          padding: '5px 14px', borderRadius: 20,
          background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.18)',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%', background: '#a78bfa',
            boxShadow: '0 0 8px rgba(167,139,250,0.9)', animation: 'pulse 2s infinite',
          }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: '#c4b5fd', letterSpacing: '0.6px' }}>
            NexusCommerce · Production
          </span>
        </div>
        <h1 style={{
          fontSize: 48, fontWeight: 900, letterSpacing: '-2px', lineHeight: 1.1, marginBottom: 14,
          background: 'linear-gradient(135deg, #ffffff 20%, #c4b5fd 55%, #67e8f9 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        }}>
          System Overview
        </h1>
        <p style={{ fontSize: 15, color: 'rgba(255,255,255,0.38)', maxWidth: 440, margin: '0 auto', lineHeight: 1.7 }}>
          Real-time API health across NexusCommerce. 2.4M daily orders, 8 monitored services.
        </p>
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr) 1.12fr', gap: 14, marginBottom: 44 }}>
        {normalKpis.map((k, i) => (
          <TiltCard key={i} warn={k.warn} flash={k.flash}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.32)', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 11 }}>
              {k.label}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: 5, flexWrap: 'wrap' }}>
              <span
                key={k.value}
                style={{
                  fontSize: 34, fontWeight: 800, letterSpacing: '-1.5px',
                  color: k.warn ? '#c4b5fd' : 'white',
                  animation: 'kpiCount 0.3s ease',
                  display: 'inline-block',
                }}
              >{k.value}</span>
              {k.unit && <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.32)', fontWeight: 500 }}>{k.unit}</span>}
              {k.delta}
            </div>
            <div style={{ fontSize: 11, color: k.warn ? 'rgba(196,181,253,0.65)' : 'rgba(255,255,255,0.3)' }}>
              {k.sub}
            </div>
          </TiltCard>
        ))}

        <CriticalCard critical={critical} health={health} />
      </div>

      {/* Health Score + Scenario bar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2.2fr', gap: 14, marginBottom: 44 }}>

        {/* Health Score */}
        <div style={{
          padding: '20px 22px', borderRadius: 14,
          background: 'rgba(10,10,20,0.6)',
          border: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 8 }}>
            System Health
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 10 }}>
            <span key={score} style={{
              fontSize: 42, fontWeight: 900, letterSpacing: '-2px',
              color: scoreColor,
              textShadow: `0 0 28px ${scoreColor}66`,
              animation: 'kpiCount 0.3s ease',
              display: 'inline-block',
            }}>{score}</span>
            <span style={{ fontSize: 16, color: 'rgba(255,255,255,0.25)', fontWeight: 500 }}>/100</span>
          </div>
          <div style={{ height: 5, background: 'rgba(255,255,255,0.05)', borderRadius: 4 }}>
            <div style={{
              height: '100%', borderRadius: 4, width: `${score}%`,
              background: score >= 80
                ? 'linear-gradient(90deg, #10b981, #34d399)'
                : score >= 50
                  ? 'linear-gradient(90deg, #d97706, #fbbf24)'
                  : 'linear-gradient(90deg, #dc2626, #f87171)',
              transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1), background 0.6s ease',
              boxShadow: `0 0 8px ${scoreColor}55`,
            }} />
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 8 }}>
            {score === 100 ? 'All systems nominal' : score >= 80 ? 'Minor degradation' : score >= 50 ? 'Partial outage' : 'Major incident'}
          </div>
        </div>

        {/* Scenario bar */}
        <div style={{
          padding: '16px 20px', borderRadius: 14,
          background: 'rgba(10,10,20,0.6)',
          border: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%', background: scenario.color,
              boxShadow: `0 0 8px ${scenario.color}`,
            }} />
            <span style={{ fontSize: 12, fontWeight: 700, color: scenario.color }}>{scenario.label}</span>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.38)', flex: 1 }}>{scenario.desc}</span>

            {/* Demo auto-play button */}
            {demoRunning ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginBottom: 2 }}>
                    {demoIdx + 1}/{DEMO_SEQUENCE.length} · next in {demoCountdown}s
                  </div>
                  <div style={{ width: 120, height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2 }}>
                    <div style={{
                      height: '100%', borderRadius: 2, background: '#a78bfa',
                      width: `${((DEMO_DURATION - demoCountdown) / DEMO_DURATION) * 100}%`,
                      transition: 'width 1s linear',
                    }} />
                  </div>
                </div>
                <button
                  onClick={stopDemo}
                  style={{
                    padding: '5px 12px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                    border: '1px solid rgba(248,113,113,0.3)', background: 'rgba(248,113,113,0.1)',
                    color: '#fca5a5', cursor: 'pointer', transition: 'all 0.18s', flexShrink: 0,
                  }}
                >Stop</button>
              </div>
            ) : (
              <button
                onClick={startDemo}
                style={{
                  padding: '5px 14px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                  border: '1px solid rgba(167,139,250,0.3)', background: 'rgba(139,92,246,0.1)',
                  color: '#c4b5fd', cursor: 'pointer', transition: 'all 0.18s', flexShrink: 0,
                  display: 'flex', alignItems: 'center', gap: 5,
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(139,92,246,0.2)'; e.currentTarget.style.borderColor = 'rgba(167,139,250,0.5)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(139,92,246,0.1)'; e.currentTarget.style.borderColor = 'rgba(167,139,250,0.3)' }}
              >
                <svg width="9" height="9" viewBox="0 0 12 12" fill="#c4b5fd"><polygon points="2,1 11,6 2,11" /></svg>
                Auto Demo
              </button>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)', fontWeight: 600, letterSpacing: '0.6px', marginRight: 2 }}>SIMULATE</span>
            {Object.entries(SCENARIOS).map(([key, s]) => {
              const active = currentScenario === key
              return (
                <button key={key} onClick={() => { stopDemo(); injectScenario(key) }} style={{
                  padding: '6px 14px', borderRadius: 20, fontSize: 11, fontWeight: 500,
                  border:     `1px solid ${active ? `${s.color}66` : 'rgba(255,255,255,0.09)'}`,
                  background: active ? `${s.color}22` : 'transparent',
                  color:      active ? s.color : 'rgba(255,255,255,0.4)',
                  cursor: 'pointer', transition: 'all 0.18s',
                  boxShadow: active ? `0 0 14px ${s.color}33` : 'none',
                }}
                onMouseEnter={e => { if (!active) { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = 'rgba(255,255,255,0.7)' }}}
                onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(255,255,255,0.4)' }}}
                >{s.label}</button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Predictive Insights */}
      <PredictiveInsights timeseries={timeseries} health={health} />

      {/* Charts */}
      <div style={{ marginBottom: 44 }}>
        <SectionLabel>Live Metrics</SectionLabel>
        <LiveChart timeseries={timeseries} />
      </div>

      {/* Service Dependency Graph */}
      <div style={{ marginBottom: 44 }}>
        <SectionLabel>Service Dependency Map</SectionLabel>
        <ServiceGraph health={health} />
      </div>

      {/* Health Heatmap */}
      <div style={{ marginBottom: 44 }}>
        <SectionLabel>Endpoint Health History</SectionLabel>
        <HealthHeatmap healthHistory={healthHistory} />
      </div>

      {/* Live Log Stream */}
      <div style={{ marginBottom: 44 }}>
        <SectionLabel>Live Log Stream</SectionLabel>
        <LiveLogStream recentLogs={recentLogs} />
      </div>

      {/* Recent incidents */}
      <div>
        <SectionLabel>Recent Incidents</SectionLabel>
        {anomalies.length === 0 ? (
          <div style={{
            padding: '36px', borderRadius: 14, textAlign: 'center',
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.28)' }}>
              No incidents detected. All systems nominal.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {anomalies.slice(0, 4).map(a => <IncidentRow key={a.detected_at + a.endpoint} a={a} />)}
            {anomalies.length > 4 && (
              <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', padding: '8px 0', textAlign: 'center' }}>
                +{anomalies.length - 4} more. View in Incidents.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function IncidentRow({ a }) {
  const label = { latency_spike: 'Latency', error_surge: 'Error', cascade_failure: 'Cascade' }[a.anomaly_type] || 'Anomaly'
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 11,
        background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)',
        transition: 'background 0.15s', cursor: 'default',
        animation: 'fadeUp 0.3s ease',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(139,92,246,0.06)'}
      onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}
    >
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#a78bfa', flexShrink: 0, boxShadow: '0 0 6px rgba(167,139,250,0.8)' }} />
      <span style={{ fontSize: 10, fontWeight: 700, color: '#c4b5fd', background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)', padding: '2px 9px', borderRadius: 20, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'rgba(255,255,255,0.58)', flexShrink: 0 }}>{a.endpoint}</span>
      <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.38)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description}</span>
      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', flexShrink: 0 }}>{a.detected_at?.slice(11, 19)}</span>
    </div>
  )
}

function SectionLabel({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
      <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.28)', textTransform: 'uppercase', letterSpacing: '0.8px', whiteSpace: 'nowrap' }}>
        {children}
      </span>
      <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(139,92,246,0.2), transparent)' }} />
    </div>
  )
}
