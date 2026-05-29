import { useEffect, useRef } from 'react'

const PARTICLE_COUNT = 38
const MAX_DIST       = 110
const SPEED          = 0.28

export default function SparkField() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1

    let width  = window.innerWidth
    let height = window.innerHeight
    canvas.width  = width  * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)
    let animId

    const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
      x:  Math.random() * width,
      y:  Math.random() * height,
      vx: (Math.random() - 0.5) * SPEED,
      vy: (Math.random() - 0.5) * SPEED,
      r:  Math.random() * 1.2 + 0.4,
      pulse: Math.random() * Math.PI * 2, // phase offset for twinkle
    }))

    function draw(ts) {
      ctx.clearRect(0, 0, width, height)

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx   = particles[i].x - particles[j].x
          const dy   = particles[i].y - particles[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < MAX_DIST) {
            const alpha = (1 - dist / MAX_DIST) * 0.06
            ctx.beginPath()
            ctx.strokeStyle = `rgba(139,92,246,${alpha})`
            ctx.lineWidth   = 0.6
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw particles with gentle twinkle
      const t = ts * 0.001
      particles.forEach(p => {
        const twinkle = 0.15 + 0.1 * Math.sin(t + p.pulse)
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(167,139,250,${twinkle})`
        ctx.fill()
      })
    }

    function update() {
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < -10)           { p.x = width + 10 }
        else if (p.x > width + 10)  { p.x = -10 }
        if (p.y < -10)           { p.y = height + 10 }
        else if (p.y > height + 10) { p.y = -10 }
      })
    }

    function loop(ts) {
      update()
      draw(ts)
      animId = requestAnimationFrame(loop)
    }
    animId = requestAnimationFrame(loop)

    const resize = () => {
      width  = window.innerWidth
      height = window.innerHeight
      canvas.width  = width  * dpr
      canvas.height = height * dpr
      ctx.scale(dpr, dpr)
    }
    window.addEventListener('resize', resize, { passive: true })

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed', inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.55,
      }}
    />
  )
}
