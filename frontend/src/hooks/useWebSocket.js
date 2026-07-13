import { useEffect, useRef, useState, useCallback } from 'react'
import {
  generateLogBatch, generateHealthSnapshot, generateAnomalies,
  generateAiAnalyses, generateTimeseriesPoint, generateInitialTimeseries,
  generateInitialHealthHistory, setMockScenario, getMockScenario,
} from './mockData'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const WS_URL  = BACKEND.replace(/^http/, 'ws') + '/ws'
const API_URL = BACKEND

// How long to wait for a real backend before switching to demo mode (ms)
const DEMO_FALLBACK_MS = 8000

export function useWebSocket() {
  const ws        = useRef(null)
  const logBuffer = useRef([])
  const demoTimer = useRef(null)
  const demoLoop  = useRef(null)
  const isMock    = useRef(false)

  const [connected,       setConnected]       = useState(false)
  const [demoMode,        setDemoMode]        = useState(false)
  const [health,          setHealth]          = useState({})
  const [healthHistory,   setHealthHistory]   = useState([])
  const [anomalies,       setAnomalies]       = useState([])
  const [aiAnalyses,      setAiAnalyses]      = useState({})
  const [timeseries,      setTimeseries]      = useState([])
  const [currentScenario, setCurrentScenario] = useState('normal')
  const [recentLogs,      setRecentLogs]      = useState([])
  const [liveStats,       setLiveStats]       = useState({ avgLatency: 0, errorRate: 0, rps: 0, maxLatency: 0 })

  // ── Demo mode: generate mock state every second ──────────────────────────
  const startDemoMode = useCallback(() => {
    if (isMock.current) return
    isMock.current = true
    setDemoMode(true)
    setConnected(true)  // show as "Live" in sidebar

    // Seed initial state
    setTimeseries(generateInitialTimeseries(60))
    setHealthHistory(generateInitialHealthHistory(40))
    setHealth(generateHealthSnapshot())

    // Tick every second
    demoLoop.current = setInterval(() => {
      const batch   = generateLogBatch(30)
      const buf     = [...batch, ...logBuffer.current].slice(0, 180)
      logBuffer.current = buf

      const avgLatency = Math.round(buf.reduce((s, l) => s + l.latency_ms, 0) / buf.length)
      const maxLatency = Math.round(Math.max(...buf.map(l => l.latency_ms)))
      const errorRate  = +((buf.filter(l => l.status_code >= 400).length / buf.length) * 100).toFixed(1)
      setLiveStats({ avgLatency, errorRate, rps: batch.length, maxLatency })
      setRecentLogs(prev => [...batch, ...prev].slice(0, 200))
      setTimeseries(prev => [...prev, generateTimeseriesPoint()].slice(-120))

      // Health every 5s
      if (Date.now() % 5000 < 1100) {
        const snap = generateHealthSnapshot()
        setHealth(snap)
        setHealthHistory(prev => [...prev.slice(-39), { ts: Date.now(), data: snap }])
      }

      // Anomalies when in a failure scenario
      const anom = generateAnomalies()
      if (anom.length > 0) {
        setAnomalies(anom)
        setAiAnalyses(generateAiAnalyses(anom))
      } else {
        setAnomalies([])
      }
    }, 1000)
  }, [])

  const stopDemoMode = useCallback(() => {
    if (!isMock.current) return
    isMock.current = false
    setDemoMode(false)
    clearInterval(demoLoop.current)
    demoLoop.current = null
    logBuffer.current = []
  }, [])

  // ── Real backend fetch ────────────────────────────────────────────────────
  const fetchTimeseries = useCallback(async () => {
    if (isMock.current) return
    try {
      const r    = await fetch(`${API_URL}/api/timeseries?minutes=5`)
      const data = await r.json()
      if (Array.isArray(data) && data.length > 0) {
        setTimeseries(prev => {
          const map = new Map(prev.map(p => [p.second, p]))
          data.forEach(p => { if (!map.has(p.second)) map.set(p.second, p) })
          return Array.from(map.values()).sort((a, b) => a.second.localeCompare(b.second)).slice(-120)
        })
      }
    } catch {}
  }, [])

  // ── WebSocket connection ──────────────────────────────────────────────────
  useEffect(() => {
    function connect() {
      const socket = new WebSocket(WS_URL)
      ws.current = socket

      socket.onopen = () => {
        // Real backend connected — cancel demo fallback and stop mock if running
        if (demoTimer.current) {
          clearTimeout(demoTimer.current)
          demoTimer.current = null
        }
        stopDemoMode()
        setConnected(true)
        fetchTimeseries()
      }

      socket.onclose = () => {
        setConnected(false)
        if (!isMock.current) {
          // Schedule demo fallback if not already running
          if (!demoTimer.current) {
            demoTimer.current = setTimeout(() => {
              startDemoMode()
              demoTimer.current = null
            }, DEMO_FALLBACK_MS)
          }
          setTimeout(connect, 2000)
        }
      }

      socket.onerror = () => socket.close()

      socket.onmessage = (e) => {
        if (isMock.current) return  // ignore real messages while in demo mode (shouldn't happen)
        let msg
        try { msg = JSON.parse(e.data) } catch { return }

        switch (msg.type) {
          case 'health':
            setHealth(msg.data)
            setHealthHistory(prev => [...prev.slice(-39), { ts: Date.now(), data: msg.data }])
            break

          case 'anomaly':
            setAnomalies(prev => [msg.data, ...prev].slice(0, 50))
            break

          case 'init_anomalies':
            setAnomalies(msg.data)
            break

          case 'ai_analysis':
            if (msg.data?.anomaly_id != null) {
              setAiAnalyses(prev => ({ ...prev, [msg.data.anomaly_id]: msg.data }))
            }
            break

          case 'logs': {
            const batch = msg.data
            if (!batch?.length) break
            logBuffer.current = [...batch, ...logBuffer.current].slice(0, 180)
            const buf = logBuffer.current
            const avgLatency = Math.round(buf.reduce((s, l) => s + l.latency_ms, 0) / buf.length)
            const maxLatency = Math.round(Math.max(...buf.map(l => l.latency_ms)))
            const errorRate  = +((buf.filter(l => l.status_code >= 400).length / buf.length) * 100).toFixed(1)
            setLiveStats({ avgLatency, errorRate, rps: batch.length, maxLatency })
            const avgLat = batch.reduce((s, l) => s + l.latency_ms, 0) / batch.length
            const errors = batch.filter(l => l.status_code >= 400).length
            setTimeseries(prev => [...prev, {
              second:      new Date().toISOString().slice(0, 19),
              avg_latency: Math.round(avgLat),
              req_count:   batch.length,
              errors,
            }].slice(-120))
            setRecentLogs(prev => [...batch, ...prev].slice(0, 200))
            break
          }

          case 'scenario_change':
            if (msg.data?.scenario) {
              setCurrentScenario(msg.data.scenario)
              logBuffer.current = []
            }
            break
        }
      }
    }

    // Start connection attempt immediately, demo fallback fires after DEMO_FALLBACK_MS
    demoTimer.current = setTimeout(() => {
      startDemoMode()
      demoTimer.current = null
    }, DEMO_FALLBACK_MS)
    connect()

    const interval = setInterval(fetchTimeseries, 10000)
    return () => {
      ws.current?.close()
      clearInterval(interval)
      if (demoTimer.current) {
        clearTimeout(demoTimer.current)
        demoTimer.current = null
      }
      clearInterval(demoLoop.current)
    }
  }, [fetchTimeseries, startDemoMode, stopDemoMode])

  // ── Scenario injection ────────────────────────────────────────────────────
  const injectScenario = useCallback(async (scenario, intensity = 1.0) => {
    logBuffer.current = []
    setCurrentScenario(scenario)

    if (isMock.current) {
      setMockScenario(scenario)
      // Immediately reflect scenario in anomalies
      const anom = generateAnomalies()
      setAnomalies(anom)
      if (anom.length > 0) setAiAnalyses(generateAiAnalyses(anom))
      return
    }
    try {
      await fetch(`${API_URL}/api/scenario`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ scenario, intensity }),
      })
    } catch {}
  }, [])

  const sendChat = useCallback(async (message, history) => {
    if (isMock.current) {
      // Minimal mock chat response
      await new Promise(r => setTimeout(r, 800))
      const scenario = getMockScenario()
      const responses = {
        normal:        'All systems are healthy. Latency is nominal at ~80ms, error rate below 1%. No active incidents.',
        db_slowdown:   'Root cause: database connection pool exhausted. Auth service is queuing 28 connections against a pool of 10. Cascade path: Auth (500ms) → Cart (timeouts) → Checkout (503s). Recommend: increase pool size and add circuit breaker.',
        memory_leak:   'Memory leak detected on search service. Heap growing ~12MB/min. GC pauses causing latency spikes. Restart the service immediately and cap the in-memory product cache.',
        rate_limit:    'Rate limit cascade: auth returning 429s from a traffic spike. All login-dependent services are stalled. Block the source subnet in WAF and temporarily raise rate limit for internal services.',
        net_partition: 'Network partition in us-east-1b AZ. Inventory is unreachable causing 65% cart failures. Reroute traffic to us-east-1a replica and enable stale-read fallback.',
      }
      return { response: responses[scenario] || responses.normal }
    }
    const r = await fetch(`${API_URL}/api/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message, history }),
    })
    return r.json()
  }, [])

  const getIncidentReport = useCallback(async () => {
    if (isMock.current) {
      await new Promise(r => setTimeout(r, 600))
      return { report: '## Incident Summary\nActive failure scenario detected across 3 services.\n\n## Root Cause\nSee Incidents page for full cascade chain.\n\n## Resolution\nUse scenario controls to restore normal operation.' }
    }
    const r = await fetch(`${API_URL}/api/incident-report`, { method: 'POST' })
    return r.json()
  }, [])

  return {
    connected, demoMode, health, healthHistory, anomalies, aiAnalyses,
    timeseries, currentScenario, recentLogs, liveStats,
    injectScenario, sendChat, getIncidentReport,
  }
}
