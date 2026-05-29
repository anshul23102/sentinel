import { useState, useRef, useEffect } from 'react'

const STARTERS = [
  "Why is /checkout failing?",
  "What's the root cause?",
  "Which service to fix first?",
  "Generate incident report",
]

export default function ChatAgent({ sendChat, getIncidentReport }) {
  const [msgs, setMsgs] = useState([{
    role: 'assistant',
    content: "I'm Sentinel AI, your intelligent on-call engineer for NexusCommerce.\n\nI have live context on every API endpoint, error pattern, and anomaly. What's happening in your system?",
    ts: new Date().toISOString(),
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, loading])

  const send = async (text) => {
    if (!text.trim() || loading) return
    setMsgs(p => [...p, { role: 'user', content: text, ts: new Date().toISOString() }])
    setInput('')
    setLoading(true)
    try {
      let res
      if (text.toLowerCase().includes('incident report')) {
        const r = await getIncidentReport(); res = r.report
      } else {
        const h = msgs.slice(-8).map(m => ({ role: m.role, content: m.content }))
        const r = await sendChat(text, h); res = r.response
      }
      setMsgs(p => [...p, { role: 'assistant', content: res, ts: new Date().toISOString() }])
    } catch {
      setMsgs(p => [...p, { role: 'assistant', content: 'Backend unreachable. Make sure the server is running on :8000.', ts: new Date().toISOString() }])
    } finally { setLoading(false) }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'rgba(255,255,255,0.025)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 20, overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(37,99,235,0.06)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 20px rgba(37,99,235,0.4)',
          animation: 'float 3s ease-in-out infinite',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '-0.2px' }}>Sentinel AI</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 1 }}>On-call engineer · live system context</div>
        </div>
        <button onClick={() => send('Generate incident report')} style={{
          padding: '6px 14px', borderRadius: 20, fontSize: 11, fontWeight: 600,
          border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
          color: 'rgba(255,255,255,0.6)', cursor: 'pointer', transition: 'all 0.2s',
        }}>
          📋 Report
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {msgs.map((m, i) => <Bubble key={i} m={m} />)}
        {loading && <ThinkingBubble />}
        <div ref={endRef} />
      </div>

      {/* Quick starts, only before first user msg */}
      {msgs.length === 1 && (
        <div style={{ padding: '0 16px 12px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {STARTERS.map(q => (
            <button key={q} onClick={() => send(q)} style={{
              padding: '5px 12px', borderRadius: 20, fontSize: 12,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.04)',
              color: 'rgba(255,255,255,0.55)', cursor: 'pointer',
              transition: 'all 0.15s',
            }}>{q}</button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(255,255,255,0.02)',
        display: 'flex', gap: 8,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
          placeholder="Ask about your API health…"
          style={{
            flex: 1,
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12, padding: '10px 14px',
            fontSize: 13, color: 'white',
            outline: 'none', transition: 'border 0.2s',
          }}
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()} style={{
          width: 40, height: 40, borderRadius: 12, border: 'none', flexShrink: 0,
          background: loading || !input.trim()
            ? 'rgba(255,255,255,0.06)'
            : 'linear-gradient(135deg, #2563eb, #7c3aed)',
          cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: !loading && input.trim() ? '0 0 16px rgba(37,99,235,0.4)' : 'none',
          transition: 'all 0.2s',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke={loading || !input.trim() ? 'rgba(255,255,255,0.25)' : 'white'} strokeWidth="2.5">
            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  )
}

function Bubble({ m }) {
  const isUser = m.role === 'user'
  return (
    <div style={{ display: 'flex', gap: 8, flexDirection: isUser ? 'row-reverse' : 'row', alignItems: 'flex-end' }}>
      {!isUser && (
        <div style={{
          width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </div>
      )}
      <div style={{
        maxWidth: '86%',
        background: isUser
          ? 'linear-gradient(135deg, #2563eb, #1d4ed8)'
          : 'rgba(255,255,255,0.06)',
        border: isUser ? 'none' : '1px solid rgba(255,255,255,0.08)',
        borderRadius: isUser ? '16px 16px 4px 16px' : '4px 16px 16px 16px',
        padding: '10px 14px',
        fontSize: 13, color: isUser ? 'white' : 'rgba(255,255,255,0.8)',
        lineHeight: 1.6, whiteSpace: 'pre-wrap',
        boxShadow: isUser ? '0 4px 16px rgba(37,99,235,0.3)' : 'none',
      }}>
        {m.content}
        <div style={{ fontSize: 10, opacity: 0.4, marginTop: 4, textAlign: isUser ? 'right' : 'left' }}>
          {m.ts?.slice(11, 19)}
        </div>
      </div>
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
      <div style={{
        width: 26, height: 26, borderRadius: '50%',
        background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      </div>
      <div style={{
        background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '4px 16px 16px 16px', padding: '12px 16px',
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0, 0.18, 0.36].map((d, i) => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,255,255,0.3)',
            animation: `bounce 0.9s ${d}s infinite ease-in-out`,
          }} />
        ))}
      </div>
    </div>
  )
}
