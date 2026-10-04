export default function ConfidenceBar({ value, small = false }) {
  const pct = Math.round((value || 0) * 100)

  const color =
    pct >= 85 ? '#10b981' :
    pct >= 65 ? '#f59e0b' :
    pct >= 45 ? '#f97316' :
    '#ef4444'

  if (small) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}>
        <div style={{ width: 48, height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
          <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2,
            boxShadow: `0 0 4px ${color}80`, transition: 'width 0.6s ease' }} />
        </div>
        <span style={{ fontSize: '0.68rem', color, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
          {pct}%
        </span>
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Confidence</span>
        <span style={{ fontSize: '0.75rem', color, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3,
          boxShadow: `0 0 6px ${color}60`, transition: 'width 0.8s ease' }} />
      </div>
    </div>
  )
}
