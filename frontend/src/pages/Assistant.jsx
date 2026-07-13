import { useState, useRef, useEffect } from 'react'
import Markdown from '../components/Markdown'

const API = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const STARTERS = [
  'Give me a full system health summary',
  'Why is /api/checkout failing?',
  'Which service is the root cause?',
  'How do I fix the latency spike?',
  'Generate an incident report',
  'What should I monitor proactively?',
]

export default function Assistant({ getIncidentReport, anomalies }) {
  const [msgs, setMsgs]           = useState([{
    role: 'assistant',
    content: `Hi, I'm Sentinel AI.\n\nI have live visibility into all NexusCommerce API endpoints, current anomalies, error rates, and latency trends.\n\nAsk me anything about your system.`,
    ts: new Date().toISOString(),
  }])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [streaming, setStreaming] = useState(false)
  const endRef                    = useRef(null)
  const abortRef                  = useRef(null)
  const msgsRef                   = useRef(msgs)
  msgsRef.current                 = msgs

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, loading, streaming])

  const send = async (text) => {
    if (!text.trim() || loading || streaming) return
    const userMsg = { role: 'user', content: text, ts: new Date().toISOString() }
    setMsgs(p => [...p, userMsg])
    setInput('')

    // Incident report: use blocking endpoint
    if (text.toLowerCase().includes('incident report')) {
      setLoading(true)
      try {
        const r   = await getIncidentReport()
        setMsgs(p => [...p, { role: 'assistant', content: r.report, ts: new Date().toISOString() }])
      } catch {
        setMsgs(p => [...p, { role: 'assistant', content: 'Backend unreachable. Is the server running on :8000?', ts: new Date().toISOString() }])
      } finally { setLoading(false) }
      return
    }

    // All other questions: SSE streaming
    setStreaming(true)
    const history = msgsRef.current.slice(-16).map(m => ({ role: m.role, content: m.content }))
    // Add the user message to history for the request
    history.push({ role: 'user', content: text })

    // Placeholder assistant message we'll stream into
    const placeholder = { role: 'assistant', content: '', ts: new Date().toISOString(), _streaming: true }
    setMsgs(p => [...p, placeholder])

    try {
      const ctrl   = new AbortController()
      abortRef.current = ctrl
      const res    = await fetch(`${API}/api/chat/stream`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, history: history.slice(0, -1) }),
        signal:  ctrl.signal,
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const parsed = JSON.parse(payload)
            if (parsed.token) {
              setMsgs(p => {
                const next = [...p]
                const last = next[next.length - 1]
                if (last?._streaming) {
                  next[next.length - 1] = { ...last, content: last.content + parsed.token }
                }
                return next
              })
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setMsgs(p => {
          const next = [...p]
          const last = next[next.length - 1]
          if (last?._streaming) {
            next[next.length - 1] = { ...last, content: last.content || 'Backend unreachable. Is the server running on :8000?', _streaming: false }
          }
          return next
        })
      }
    } finally {
      // Mark streaming done — remove _streaming flag
      setMsgs(p => {
        const next = [...p]
        const last = next[next.length - 1]
        if (last?._streaming) next[next.length - 1] = { ...last, _streaming: false }
        return next
      })
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{
        padding: '40px 60px 22px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: msgs.length <= 1 ? 22 : 0 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-38)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 10 }}>
              AI Assistant
            </div>
            <h1 style={{
              fontSize: 34, fontWeight: 900, letterSpacing: '-1px',
              background: 'var(--heading-gradient)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>
              Sentinel AI
            </h1>
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '8px 14px', borderRadius: 20,
            background: 'var(--app-card-bg)', border: '1px solid var(--text-10)',
            fontSize: 12, color: 'var(--text-50)', flexShrink: 0,
          }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#a78bfa', animation: 'pulse 2s infinite', boxShadow: '0 0 8px rgba(167,139,250,0.9)' }} />
            Live · {anomalies.length} anomalies
          </div>
        </div>

        {/* Starter chips */}
        {msgs.length <= 1 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {STARTERS.map(s => (
              <button key={s} onClick={() => send(s)} style={{
                padding: '7px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                border: '1px solid var(--text-10)',
                background: 'var(--bg-04)',
                color: 'var(--text-55)', cursor: 'pointer', transition: 'all 0.16s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(139,92,246,0.12)'; e.currentTarget.style.borderColor = 'rgba(167,139,250,0.3)'; e.currentTarget.style.color = '#c4b5fd' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-04)'; e.currentTarget.style.borderColor = 'var(--text-10)'; e.currentTarget.style.color = 'var(--text-55)' }}
              >{s}</button>
            ))}
          </div>
        )}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 60px', display: 'flex', flexDirection: 'column', gap: 22 }}>
        {msgs.map((m, i) => <Bubble key={i} m={m} isLast={i === msgs.length - 1} />)}
        {loading && <Thinking />}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '14px 60px 32px',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 10, maxWidth: 820 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
            placeholder="Ask about your API health..."
            disabled={streaming}
            style={{
              flex: 1,
              background: 'var(--app-card-bg)',
              border: '1px solid rgba(255,255,255,0.11)',
              borderRadius: 12, padding: '14px 18px',
              fontSize: 14, color: 'white', outline: 'none',
              transition: 'border-color 0.18s',
              opacity: streaming ? 0.5 : 1,
            }}
            onFocus={e => e.target.style.borderColor = 'rgba(167,139,250,0.45)'}
            onBlur={e  => e.target.style.borderColor = 'rgba(255,255,255,0.11)'}
          />
          {streaming ? (
            <button
              onClick={stop}
              style={{
                padding: '0 24px', height: 48, borderRadius: 12, border: '1px solid rgba(248,113,113,0.3)',
                background: 'rgba(248,113,113,0.1)',
                color: '#fca5a5',
                fontSize: 13, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
                transition: 'all 0.16s',
              }}
            >Stop</button>
          ) : (
            <button
              onClick={() => send(input)}
              disabled={loading || !input.trim()}
              style={{
                padding: '0 24px', height: 48, borderRadius: 12, border: 'none', flexShrink: 0,
                background: loading || !input.trim()
                  ? 'var(--text-06)'
                  : 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
                color: loading || !input.trim() ? 'rgba(255,255,255,0.25)' : 'white',
                fontSize: 13, fontWeight: 600,
                cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                transition: 'all 0.16s',
                boxShadow: loading || !input.trim() ? 'none' : '0 0 22px rgba(139,92,246,0.32)',
              }}
            >Send</button>
          )}
        </div>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', marginTop: 10 }}>
          Powered by Llama 3.3 70B via Groq · Press Enter to send
        </p>
      </div>
    </div>
  )
}

function Bubble({ m, isLast }) {
  const isUser      = m.role === 'user'
  const isStreaming = m._streaming && isLast

  return (
    <div style={{
      display: 'flex', gap: 12, maxWidth: 820,
      flexDirection: isUser ? 'row-reverse' : 'row',
      animation: 'fadeUp 0.22s ease',
    }}>
      {!isUser && (
        <div style={{
          width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 2, boxShadow: '0 0 14px rgba(139,92,246,0.35)',
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </div>
      )}
      <div style={{ maxWidth: '80%' }}>
        <p style={{ fontSize: 11, color: 'var(--text-30)', marginBottom: 6, textAlign: isUser ? 'right' : 'left' }}>
          {isUser ? 'You' : 'Sentinel'} · {m.ts?.slice(11, 19)}
        </p>
        <div style={{
          background: isUser
            ? 'linear-gradient(135deg, #8b5cf6, #a78bfa)'
            : 'var(--app-card-bg)',
          border: isUser ? 'none' : '1px solid var(--text-10)',
          borderRadius: isUser ? '14px 14px 3px 14px' : '3px 14px 14px 14px',
          padding: '13px 17px',
          boxShadow: isUser ? '0 4px 20px rgba(139,92,246,0.22)' : 'none',
        }}>
          {isUser ? (
            <span style={{ fontSize: 14, color: 'white', lineHeight: 1.7 }}>{m.content}</span>
          ) : (
            <div style={{ position: 'relative' }}>
              {m.content
                ? <Markdown text={m.content} />
                : isStreaming && <div style={{ width: 8, height: 16, background: '#a78bfa', borderRadius: 2, animation: 'blink 1s step-end infinite', display: 'inline-block' }} />
              }
              {isStreaming && m.content && (
                <span style={{
                  display: 'inline-block', width: 2, height: '1em',
                  background: '#a78bfa', marginLeft: 2, verticalAlign: 'text-bottom',
                  animation: 'blink 1s step-end infinite', borderRadius: 1,
                }} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Thinking() {
  return (
    <div style={{ display: 'flex', gap: 12, maxWidth: 820, animation: 'fadeUp 0.22s ease' }}>
      <div style={{
        width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
        background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginTop: 2, boxShadow: '0 0 14px rgba(139,92,246,0.35)',
      }}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      </div>
      <div style={{ marginTop: 22 }}>
        <div style={{
          background: 'var(--app-card-bg)', border: '1px solid var(--text-10)',
          borderRadius: '3px 14px 14px 14px', padding: '14px 18px',
          display: 'flex', gap: 5, alignItems: 'center',
        }}>
          {[0, 0.15, 0.3].map((d, i) => (
            <div key={i} style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'rgba(167,139,250,0.6)',
              animation: `bounce 0.9s ${d}s infinite`,
            }} />
          ))}
        </div>
      </div>
    </div>
  )
}
