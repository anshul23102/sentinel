import { useEffect, useRef } from 'react'

// Fixed node layout — logical dependency hierarchy
const NODES = [
  { id: '/api/auth/login',    label: 'Auth',      short: 'auth',      rx: 0.25, ry: 0.09 },
  { id: '/api/products',      label: 'Products',  short: 'products',  rx: 0.72, ry: 0.09 },
  { id: '/api/users/profile', label: 'Profile',   short: 'profile',   rx: 0.08, ry: 0.50 },
  { id: '/api/search',        label: 'Search',    short: 'search',    rx: 0.50, ry: 0.36 },
  { id: '/api/cart',          label: 'Cart',      short: 'cart',      rx: 0.58, ry: 0.60 },
  { id: '/api/inventory',     label: 'Inventory', short: 'inventory', rx: 0.88, ry: 0.48 },
  { id: '/api/checkout',      label: 'Checkout',  short: 'checkout',  rx: 0.46, ry: 0.84 },
  { id: '/api/orders',        label: 'Orders',    short: 'orders',    rx: 0.84, ry: 0.84 },
]

// A depends on B → arrow A -> B
const EDGES = [
  { from: '/api/users/profile', to: '/api/auth/login'    },
  { from: '/api/search',        to: '/api/products'      },
  { from: '/api/cart',          to: '/api/products'      },
  { from: '/api/inventory',     to: '/api/products'      },
  { from: '/api/checkout',      to: '/api/auth/login'    },
  { from: '/api/checkout',      to: '/api/cart'          },
  { from: '/api/checkout',      to: '/api/inventory'     },
  { from: '/api/orders',        to: '/api/checkout'      },
]

const STATUS = {
  healthy:  { line: '#34d399', glow: 'rgba(52,211,153,0.55)',   fill: '#0d3327', text: '#34d399', ring: 'rgba(52,211,153,0.2)'   },
  degraded: { line: '#fbbf24', glow: 'rgba(251,191,36,0.55)',  fill: '#2d1f03', text: '#fbbf24', ring: 'rgba(251,191,36,0.18)'  },
  critical: { line: '#f87171', glow: 'rgba(248,113,113,0.6)',  fill: '#2a0a0a', text: '#f87171', ring: 'rgba(248,113,113,0.22)' },
  unknown:  { line: '#6b7280', glow: 'rgba(107,114,128,0.3)',  fill: '#111318', text: '#9ca3af', ring: 'rgba(107,114,128,0.1)'  },
}

const NODE_R = 22

// Pre-build node/edge lookup maps once (module level, stable)
const NODE_MAP = Object.fromEntries(NODES.map(n => [n.id, n]))

export default function ServiceGraph({ health }) {
  const canvasRef    = useRef(null)
  const rafRef       = useRef(null)
  const particlesRef = useRef([])
  const timeRef      = useRef(0)
  // KEY FIX: health stored in a ref — animation loop reads latest health every frame
  // without the canvas effect needing to re-run on every health tick
  const healthRef    = useRef(health)

  // Keep ref in sync with prop (no effect re-run needed)
  healthRef.current = health

  // Init particles once on mount
  useEffect(() => {
    particlesRef.current = EDGES.flatMap((_, ei) =>
      Array.from({ length: 3 }, (_, pi) => ({
        edge:  ei,
        t:     (pi / 3 + ei * 0.13) % 1,
        speed: 0.0035 + Math.random() * 0.002,
        size:  2 + Math.random(),
      }))
    )
  }, [])

  // Canvas setup — runs ONCE on mount, never on health changes
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const dpr = window.devicePixelRatio || 1
    let W = canvas.offsetWidth
    let H = canvas.offsetHeight
    canvas.width  = W * dpr
    canvas.height = H * dpr
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)

    // Resize handler
    const onResize = () => {
      W = canvas.offsetWidth
      H = canvas.offsetHeight
      canvas.width  = W * dpr
      canvas.height = H * dpr
      ctx.scale(dpr, dpr)
    }
    window.addEventListener('resize', onResize, { passive: true })

    const getStatus = (id) => healthRef.current?.[id]?.status || 'unknown'
    const getColor  = (id) => STATUS[getStatus(id)] || STATUS.unknown

    const nodePos      = (n) => ({ x: n.rx * W, y: n.ry * H })
    const controlPoint = (p1, p2) => {
      const mx = (p1.x + p2.x) / 2
      const my = (p1.y + p2.y) / 2
      const dx = p2.x - p1.x
      const dy = p2.y - p1.y
      return { x: mx - dy * 0.18, y: my + dx * 0.18 }
    }
    const bezierPt = (p1, cp, p2, t) => ({
      x: (1-t)**2 * p1.x + 2*(1-t)*t * cp.x + t**2 * p2.x,
      y: (1-t)**2 * p1.y + 2*(1-t)*t * cp.y + t**2 * p2.y,
    })

    const draw = (timestamp) => {
      timeRef.current = timestamp * 0.001
      ctx.clearRect(0, 0, W, H)

      // ------ EDGES ------
      EDGES.forEach(edge => {
        const fromNode = NODE_MAP[edge.from]
        const toNode   = NODE_MAP[edge.to]
        if (!fromNode || !toNode) return
        const p1 = nodePos(fromNode), p2 = nodePos(toNode)
        const cp = controlPoint(p1, p2)

        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.quadraticCurveTo(cp.x, cp.y, p2.x, p2.y)
        ctx.strokeStyle = 'rgba(255,255,255,0.07)'
        ctx.lineWidth = 1.5
        ctx.setLineDash([4, 6])
        ctx.stroke()
        ctx.setLineDash([])

        // Arrowhead
        const ptEnd  = bezierPt(p1, cp, p2, 0.88)
        const ptEndM = bezierPt(p1, cp, p2, 0.83)
        const angle  = Math.atan2(ptEnd.y - ptEndM.y, ptEnd.x - ptEndM.x)
        const aLen = 7, aAng = 0.45
        ctx.beginPath()
        ctx.moveTo(ptEnd.x, ptEnd.y)
        ctx.lineTo(ptEnd.x - aLen * Math.cos(angle - aAng), ptEnd.y - aLen * Math.sin(angle - aAng))
        ctx.moveTo(ptEnd.x, ptEnd.y)
        ctx.lineTo(ptEnd.x - aLen * Math.cos(angle + aAng), ptEnd.y - aLen * Math.sin(angle + aAng))
        ctx.strokeStyle = 'rgba(255,255,255,0.18)'
        ctx.lineWidth = 1.2
        ctx.stroke()
      })

      // ------ PARTICLES ------
      particlesRef.current.forEach(p => {
        p.t += p.speed
        if (p.t > 1) p.t = 0
        const edge     = EDGES[p.edge]
        const fromNode = NODE_MAP[edge.from]
        const toNode   = NODE_MAP[edge.to]
        if (!fromNode || !toNode) return
        const p1 = nodePos(fromNode), p2 = nodePos(toNode)
        const cp = controlPoint(p1, p2)
        const pt = bezierPt(p1, cp, p2, p.t)
        const col = getColor(edge.from)

        // shadowBlur is cheaper than createRadialGradient — avoids gradient allocation per frame
        ctx.shadowColor = col.line
        ctx.shadowBlur  = p.size * 5
        ctx.beginPath()
        ctx.arc(pt.x, pt.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = col.line
        ctx.fill()
        ctx.shadowBlur = 0
      })

      // ------ NODES ------
      NODES.forEach(node => {
        const { x, y } = nodePos(node)
        const status   = getStatus(node.id)
        const col      = STATUS[status] || STATUS.unknown
        const t        = timeRef.current
        const isAlert  = status === 'critical' || status === 'degraded'
        const pulse    = isAlert ? 1 + 0.12 * Math.sin(t * (status === 'critical' ? 3.5 : 2.2)) : 1

        // Pulsing ring for alerts
        if (isAlert) {
          const ringR = NODE_R * 1.9 * pulse
          const ringG = ctx.createRadialGradient(x, y, NODE_R, x, y, ringR)
          ringG.addColorStop(0, col.ring)
          ringG.addColorStop(1, 'transparent')
          ctx.beginPath()
          ctx.arc(x, y, ringR, 0, Math.PI * 2)
          ctx.fillStyle = ringG
          ctx.fill()
        }

        // Halo
        const haloR = NODE_R * 2.2
        const haloG = ctx.createRadialGradient(x, y, 0, x, y, haloR)
        const glowLow = col.glow.replace(/[\d.]+\)$/, '0.18)')
        haloG.addColorStop(0, glowLow)
        haloG.addColorStop(1, 'transparent')
        ctx.beginPath()
        ctx.arc(x, y, haloR, 0, Math.PI * 2)
        ctx.fillStyle = haloG
        ctx.fill()

        // Border ring
        ctx.beginPath()
        ctx.arc(x, y, NODE_R + 1.5, 0, Math.PI * 2)
        ctx.strokeStyle = col.line + '66'
        ctx.lineWidth = 1
        ctx.stroke()

        // Fill
        ctx.beginPath()
        ctx.arc(x, y, NODE_R, 0, Math.PI * 2)
        ctx.fillStyle = col.fill
        ctx.fill()

        // Status dot top-right
        const dx = x + NODE_R * 0.66, dy = y - NODE_R * 0.66
        ctx.beginPath()
        ctx.arc(dx, dy, 4, 0, Math.PI * 2)
        ctx.fillStyle = col.line
        if (isAlert) { ctx.shadowColor = col.line; ctx.shadowBlur = 8 }
        ctx.fill()
        ctx.shadowBlur = 0

        // Label below
        ctx.font = '600 11px Inter, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillStyle = col.text
        ctx.fillText(node.short, x, y + NODE_R + 16)

        // Short name inside node
        ctx.font = '700 9px Inter, sans-serif'
        ctx.fillStyle = 'rgba(255,255,255,0.65)'
        ctx.fillText(node.label, x, y + 3.5)
      })

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', onResize)
    }
  }, []) // empty deps — runs once, reads health via healthRef every frame

  const counts = {
    healthy:  NODES.filter(n => (health?.[n.id]?.status || 'unknown') === 'healthy').length,
    degraded: NODES.filter(n => (health?.[n.id]?.status || 'unknown') === 'degraded').length,
    critical: NODES.filter(n => (health?.[n.id]?.status || 'unknown') === 'critical').length,
  }

  return (
    <div style={{
      background: 'rgba(0,0,0,0.3)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 16, backdropFilter: 'blur(20px)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--text-06)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ display: 'flex', gap: 5 }}>
          {['rgba(248,113,113,0.75)', 'rgba(251,191,36,0.75)', 'rgba(52,211,153,0.75)'].map((c, i) => (
            <div key={i} style={{ width: 9, height: 9, borderRadius: '50%', background: c }} />
          ))}
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-50)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          Service Dependency Graph
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
          {[
            { label: 'healthy',  color: '#34d399', count: counts.healthy },
            { label: 'degraded', color: '#fbbf24', count: counts.degraded },
            { label: 'critical', color: '#f87171', count: counts.critical },
          ].map(s => (
            <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'rgba(255,255,255,0.38)' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color }} />
              {s.count} {s.label}
            </div>
          ))}
        </div>
      </div>

      <canvas ref={canvasRef} style={{ width: '100%', height: 340, display: 'block' }} />

      <div style={{
        padding: '10px 18px', borderTop: '1px solid rgba(255,255,255,0.05)',
        fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'flex', gap: 16,
      }}>
        <span>Particles = active request flow</span>
        <span>Arrows = dependency direction</span>
        <span>Node color = live health status</span>
      </div>
    </div>
  )
}
