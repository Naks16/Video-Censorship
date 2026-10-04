import { useEffect, useRef, useState } from 'react'

const STAGES = [
  { id: 'ingestion', label: 'Video Ingestion', desc: 'Downloading trailer & extracting frames', emoji: '⬇️', targetProgress: 15 },
  { id: 'audio',     label: 'Audio Analysis',  desc: 'Whisper STT transcription & language detection', emoji: '🎙️', targetProgress: 35 },
  { id: 'vision',    label: 'Vision Analysis',  desc: 'CLIP scene & object classification', emoji: '👁️', targetProgress: 55 },
  { id: 'nlp',       label: 'NLP Processing',   desc: 'GPT-4o genre, plot, themes extraction', emoji: '🧠', targetProgress: 75 },
  { id: 'metadata',  label: 'Metadata Parsing', desc: 'Cast, crew, trailer type extraction', emoji: '🔍', targetProgress: 88 },
  { id: 'aggregate', label: 'Aggregating',      desc: 'Merging results & scoring', emoji: '✨', targetProgress: 100 },
]

export default function ProgressTracker({ taskId, onComplete, onError }) {
  const [progress, setProgress] = useState(0)
  const [currentStage, setCurrentStage] = useState('Queued')
  const [elapsed, setElapsed] = useState(0)
  const startTime = useRef(Date.now())
  const esRef = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.current) / 1000))
    }, 1000)

    // Server-Sent Events for real-time progress
    const es = new EventSource(`/api/stream/${taskId}`)
    esRef.current = es

    es.onmessage = async (event) => {
      const data = JSON.parse(event.data)
      setProgress(data.progress || 0)
      setCurrentStage(data.current_stage || '')

      if (data.status === 'completed') {
        es.close()
        clearInterval(timer)
        try {
          const res = await fetch(`/api/result/${taskId}`)
          const result = await res.json()
          onComplete(result)
        } catch (e) { onError(e.message) }
      } else if (data.status === 'failed') {
        es.close()
        clearInterval(timer)
        onError(data.error || 'Pipeline failed')
      }
    }

    es.onerror = () => {
      // SSE disconnected — fallback to polling
      es.close()
      const poll = setInterval(async () => {
        try {
          const res = await fetch(`/api/status/${taskId}`)
          const data = await res.json()
          setProgress(data.progress || 0)
          setCurrentStage(data.current_stage || '')
          if (data.status === 'completed') {
            clearInterval(poll)
            clearInterval(timer)
            const r = await fetch(`/api/result/${taskId}`)
            onComplete(await r.json())
          } else if (data.status === 'failed') {
            clearInterval(poll)
            clearInterval(timer)
            onError(data.error)
          }
        } catch { /* ignore */ }
      }, 2000)
    }

    return () => {
      es.close()
      clearInterval(timer)
    }
  }, [taskId, onComplete, onError])

  const activeStageIdx = STAGES.findIndex(s => s.targetProgress > progress) - 1
  const clampedIdx = Math.max(0, Math.min(activeStageIdx, STAGES.length - 1))

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div style={{ fontSize: '3rem', marginBottom: '0.75rem',
          animation: 'pulse-ring 2s ease-in-out infinite' }}>⚙️</div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>AI Pipeline Running</h2>
        <p className="text-muted text-sm" style={{ marginTop: '0.35rem' }}>
          {currentStage} · {fmt(elapsed)} elapsed
        </p>
      </div>

      {/* Progress bar */}
      <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span className="text-sm" style={{ fontWeight: 600 }}>{currentStage}</span>
          <span className="text-sm" style={{ color: 'var(--primary-light)', fontWeight: 700 }}>{progress}%</span>
        </div>
        <div style={{ height: 8, background: 'rgba(255,255,255,0.07)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${progress}%`,
            background: 'linear-gradient(90deg, var(--primary) 0%, var(--accent) 100%)',
            borderRadius: 4,
            transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
            boxShadow: '0 0 12px rgba(99,102,241,0.6)',
          }} />
        </div>
      </div>

      {/* Stage steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {STAGES.map((stage, idx) => {
          const isDone = progress >= stage.targetProgress
          const isActive = !isDone && progress >= (STAGES[idx - 1]?.targetProgress ?? 0)
          const isPending = !isDone && !isActive

          return (
            <div key={stage.id}
              className="card"
              style={{
                padding: '0.9rem 1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                borderColor: isActive ? 'var(--border-active)' : isDone ? 'rgba(16,185,129,0.3)' : 'var(--border)',
                background: isActive
                  ? 'rgba(99,102,241,0.08)'
                  : isDone ? 'rgba(16,185,129,0.06)' : 'var(--bg-card)',
                opacity: isPending ? 0.5 : 1,
                transition: 'all 0.4s ease',
              }}>
              {/* Status icon */}
              <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem',
                background: isDone ? 'rgba(16,185,129,0.2)' : isActive ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)',
                border: `2px solid ${isDone ? 'var(--success)' : isActive ? 'var(--primary)' : 'var(--border)'}`,
                animation: isActive ? 'pulse-ring 1.5s ease infinite' : 'none' }}>
                {isDone ? '✓' : isActive ? <ActiveSpinner /> : stage.emoji}
              </div>

              {/* Text */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontWeight: 600, fontSize: '0.88rem',
                  color: isDone ? 'var(--success)' : isActive ? 'var(--primary-light)' : 'var(--text-secondary)' }}>
                  {stage.label}
                </p>
                <p className="text-xs text-muted" style={{ marginTop: '0.1rem', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stage.desc}</p>
              </div>

              {/* Stage badge */}
              <span className={`badge ${isDone ? 'badge--success' : isActive ? 'badge--primary' : ''}`}
                style={{ flexShrink: 0, fontSize: '0.7rem' }}>
                {isDone ? 'Done' : isActive ? 'Running' : `${stage.targetProgress}%`}
              </span>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-muted" style={{ textAlign: 'center', marginTop: '1.5rem' }}>
        ⏱ Typical processing time: 2–5 minutes depending on trailer length
      </p>
    </div>
  )
}

function ActiveSpinner() {
  return (
    <span style={{ display: 'inline-block', width: 14, height: 14,
      border: '2px solid rgba(99,102,241,0.3)', borderTopColor: 'var(--primary)',
      borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
  )
}
