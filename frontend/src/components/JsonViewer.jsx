import { useState } from 'react'

export default function JsonViewer({ data }) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(true)

  const json = JSON.stringify(data, null, 2)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(json)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trailer_${data.task_id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="badge badge--primary">JSON</span>
          <span className="text-xs text-muted">{json.split('\n').length} lines · {(new Blob([json]).size / 1024).toFixed(1)} KB</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setExpanded(e => !e)} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
            {expanded ? '⊟ Collapse' : '⊞ Expand'}
          </button>
          <button className="btn btn-secondary" onClick={handleCopy} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
            {copied ? '✓ Copied' : '📋 Copy'}
          </button>
          <button className="btn btn-primary" onClick={handleDownload} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
            ⬇ Download
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ position: 'relative' }}>
          <pre
            className="font-mono"
            style={{
              background: 'rgba(0,0,0,0.4)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1.25rem',
              overflow: 'auto',
              maxHeight: 520,
              fontSize: '0.78rem',
              lineHeight: 1.65,
              color: 'var(--text-secondary)',
              whiteSpace: 'pre',
            }}
            dangerouslySetInnerHTML={{ __html: syntaxHighlight(json) }}
          />
        </div>
      )}
    </div>
  )
}

function syntaxHighlight(json) {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'color:#67e8f9'   // number (cyan)
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'color:#c4b5fd'   // key (purple)
          } else {
            cls = 'color:#86efac'   // string (green)
          }
        } else if (/true|false/.test(match)) {
          cls = 'color:#fcd34d'     // boolean (yellow)
        } else if (/null/.test(match)) {
          cls = 'color:#f87171'     // null (red)
        }
        return `<span style="${cls}">${match}</span>`
      }
    )
}
