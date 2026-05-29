import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(7,8,12,0.97)',
      border: '1px solid rgba(139,92,246,0.25)',
      borderRadius: 10, padding: '10px 14px', fontSize: 12,
      backdropFilter: 'blur(16px)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    }}>
      <div style={{ color: 'rgba(255,255,255,0.28)', marginBottom: 6, fontSize: 11 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.stroke, fontWeight: 600, fontSize: 13 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
          {p.dataKey === 'avg_latency' ? 'ms' : p.dataKey === 'error_rate' ? '%' : ' rps'}
        </div>
      ))}
    </div>
  )
}

export default function LiveChart({ timeseries }) {
  const data = timeseries.map(t => ({
    ...t,
    time:        t.second?.slice(14, 19) || '',
    avg_latency: Math.round(t.avg_latency || 0),
    p95_latency: Math.round((t.p95_latency || t.avg_latency || 0)),
    error_rate:  t.req_count > 0 ? +(((t.errors || 0) / t.req_count) * 100).toFixed(1) : 0,
    req_count:   t.req_count || 0,
  })).slice(-60)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>

      <ChartCard title="Response Latency" unit="ms" color="#22d3ee" sub="SLA 200ms">
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id="lgLatency" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip />} />
            <ReferenceLine y={200} stroke="rgba(251,191,36,0.35)" strokeDasharray="4 4" label={{ value: 'SLA', position: 'right', fontSize: 9, fill: 'rgba(251,191,36,0.6)' }} />
            <Area type="monotone" dataKey="avg_latency" name="Avg Latency" stroke="#22d3ee" strokeWidth={2} fill="url(#lgLatency)" dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Error Rate" unit="%" color="#f87171" sub="threshold 5%">
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id="lgError" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f87171" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#f87171" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, (dataMax) => Math.max(dataMax * 1.2, 10)]} />
            <Tooltip content={<Tip />} />
            <ReferenceLine y={5} stroke="rgba(251,191,36,0.35)" strokeDasharray="4 4" label={{ value: '5%', position: 'right', fontSize: 9, fill: 'rgba(251,191,36,0.6)' }} />
            <Area type="monotone" dataKey="error_rate" name="Error" stroke="#f87171" strokeWidth={2} fill="url(#lgError)" dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Request Volume" unit="rps" color="#a78bfa" sub="target ~30">
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id="lgRps" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.18)', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip />} />
            <Area type="monotone" dataKey="req_count" name="Requests" stroke="#a78bfa" strokeWidth={2} fill="url(#lgRps)" dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

    </div>
  )
}

function ChartCard({ title, unit, color, sub, children }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.022)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderTop: `1px solid ${color}22`,
      borderRadius: 14, padding: '14px 14px 8px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.6)' }}>{title}</span>
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)' }}>· {unit}</span>
        {sub && <span style={{ marginLeft: 'auto', fontSize: 9, color: 'rgba(255,255,255,0.2)' }}>{sub}</span>}
      </div>
      {children}
    </div>
  )
}
