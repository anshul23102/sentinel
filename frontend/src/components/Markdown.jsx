// Renders the markdown patterns returned by Llama 3.3 70B:
// ## / ### headings, * / - / 1. lists, **bold**, `code`, ``` blocks, blank lines
export default function Markdown({ text, style = {} }) {
  if (!text) return null

  // Split into code blocks first so we don't parse inside them
  const segments = splitCodeBlocks(text)

  return (
    <div style={{ lineHeight: 1.78, ...style }}>
      {segments.map((seg, si) => {
        if (seg.type === 'code') {
          return (
            <pre key={si} style={{
              background: 'rgba(0,0,0,0.4)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '10px 14px',
              fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
              color: '#e2e8f0', overflowX: 'auto', margin: '8px 0',
              lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {seg.lang && (
                <div style={{ fontSize: 9, color: '#a78bfa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {seg.lang}
                </div>
              )}
              {seg.content}
            </pre>
          )
        }

        // Regular text — parse line by line
        const lines = seg.content.split('\n')
        return lines.map((line, i) => {
          const trimmed = line.trim()
          if (!trimmed) return <div key={`${si}-${i}`} style={{ height: 8 }} />

          // ## heading
          if (trimmed.startsWith('## ')) {
            return (
              <div key={`${si}-${i}`} style={{ fontSize: 12, fontWeight: 700, color: '#c4b5fd', textTransform: 'uppercase', letterSpacing: '0.6px', marginTop: 16, marginBottom: 6 }}>
                {parseInline(trimmed.slice(3))}
              </div>
            )
          }

          // ### heading
          if (trimmed.startsWith('### ')) {
            return (
              <div key={`${si}-${i}`} style={{ fontSize: 12, fontWeight: 700, color: '#a78bfa', marginTop: 12, marginBottom: 4 }}>
                {parseInline(trimmed.slice(4))}
              </div>
            )
          }

          // Numbered list (1. 2. 3.)
          const numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)/)
          if (numberedMatch) {
            return (
              <div key={`${si}-${i}`} style={{ display: 'flex', gap: 9, marginBottom: 5, alignItems: 'flex-start' }}>
                <span style={{
                  color: '#a78bfa', flexShrink: 0, fontSize: 11, fontWeight: 700,
                  minWidth: 18, marginTop: 1,
                }}>{numberedMatch[1]}.</span>
                <span style={{ color: 'rgba(255,255,255,0.72)', fontSize: 13 }}>
                  {parseInline(numberedMatch[2])}
                </span>
              </div>
            )
          }

          // Bullet point (* or -)
          if (/^[*\-] /.test(trimmed)) {
            return (
              <div key={`${si}-${i}`} style={{ display: 'flex', gap: 9, marginBottom: 5, alignItems: 'flex-start' }}>
                <span style={{ color: '#a78bfa', flexShrink: 0, marginTop: 1, fontSize: 12 }}>›</span>
                <span style={{ color: 'rgba(255,255,255,0.72)', fontSize: 13 }}>
                  {parseInline(trimmed.slice(2))}
                </span>
              </div>
            )
          }

          // Plain line
          return (
            <div key={`${si}-${i}`} style={{ color: 'rgba(255,255,255,0.68)', fontSize: 13, marginBottom: 3 }}>
              {parseInline(trimmed)}
            </div>
          )
        })
      })}
    </div>
  )
}

// Split text into alternating prose / fenced-code segments
function splitCodeBlocks(text) {
  const segments = []
  const regex    = /```(\w*)\n?([\s\S]*?)```/g
  let last = 0, match
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      segments.push({ type: 'prose', content: text.slice(last, match.index) })
    }
    segments.push({ type: 'code', lang: match[1] || '', content: match[2].trim() })
    last = match.index + match[0].length
  }
  if (last < text.length) segments.push({ type: 'prose', content: text.slice(last) })
  return segments.length ? segments : [{ type: 'prose', content: text }]
}

// Render **bold** and `inline code` within a line
function parseInline(text) {
  const parts = []
  // Combined regex: **bold** or `code`
  const regex  = /\*\*(.+?)\*\*|`([^`]+)`/g
  let last = 0, key = 0, match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(<span key={key++}>{text.slice(last, match.index)}</span>)
    }
    if (match[1] !== undefined) {
      // **bold**
      parts.push(
        <strong key={key++} style={{ color: 'rgba(255,255,255,0.92)', fontWeight: 700 }}>
          {match[1]}
        </strong>
      )
    } else {
      // `inline code`
      parts.push(
        <code key={key++} style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11, color: '#67e8f9',
          background: 'rgba(6,182,212,0.1)',
          border: '1px solid rgba(6,182,212,0.18)',
          borderRadius: 4, padding: '1px 5px',
        }}>
          {match[2]}
        </code>
      )
    }
    last = match.index + match[0].length
  }

  if (last < text.length) parts.push(<span key={key++}>{text.slice(last)}</span>)
  return parts.length ? parts : text
}
