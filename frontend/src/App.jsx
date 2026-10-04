import { useState, useCallback } from 'react'
import UrlInput from './components/UrlInput.jsx'
import ProgressTracker from './components/ProgressTracker.jsx'
import MetadataDisplay from './components/MetadataDisplay.jsx'
import BatchProcessor from './components/BatchProcessor.jsx'
import AnalyticsDashboard from './components/AnalyticsDashboard.jsx'

const API = '/api'

// Views: 'home' | 'processing' | 'results' | 'batch' | 'analytics'
export default function App() {
  const [view, setView] = useState('home')
  const [taskId, setTaskId] = useState(null)
  const [taskStatus, setTaskStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])

  const handleSubmit = useCallback(async (url) => {
    try {
      const res = await fetch(`${API}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (!res.ok) throw new Error(`Server error: ${res.statusText}`)
      const data = await res.json()
      setTaskId(data.task_id)
      setTaskStatus({ status: 'pending', progress: 0, current_stage: 'Queued' })
      setResult(null)
      setView('processing')
    } catch (e) {
      alert(`Failed to start extraction: ${e.message}`)
    }
  }, [])

  const handleUpload = useCallback(async (file) => {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${API}/upload`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`Server error: ${res.statusText}`)
      const data = await res.json()
      setTaskId(data.task_id)
      setTaskStatus({ status: 'pending', progress: 0, current_stage: 'Queued' })
      setResult(null)
      setView('processing')
    } catch (e) {
      alert(`Failed to upload file: ${e.message}`)
    }
  }, [])

  const handleComplete = useCallback((resultData) => {
    setResult(resultData)
    setHistory(h => [{ taskId, result: resultData, ts: new Date() }, ...h.slice(0, 9)])
    setView('results')
  }, [taskId])

  const handleReset = useCallback(() => {
    setView('home')
    setTaskId(null)
    setTaskStatus(null)
    setResult(null)
  }, [])

  return (
    <div className="page">
      {/* ── Top Nav ── */}
      <nav style={{ padding: '1rem 1.5rem', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', borderBottom: '1px solid var(--border)',
        backdropFilter: 'blur(20px)', position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(7,9,15,0.85)' }}>
        <button onClick={handleReset} style={{ display: 'flex', alignItems: 'center',
          gap: '0.6rem', background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-primary)' }}>
          <span style={{ fontSize: '1.4rem' }}>🎬</span>
          <span style={{ fontWeight: 800, fontSize: '1.1rem' }}>
            Trailer<span className="gradient-text">IQ</span>
          </span>
        </button>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {['home', 'batch', 'analytics'].map(v => (
            <button key={v} className={`btn btn-ghost ${view === v ? 'active' : ''}`}
              onClick={() => setView(v)}
              style={{ textTransform: 'capitalize',
                color: view === v ? 'var(--primary-light)' : undefined }}>
              {v === 'home' ? '🔍 Extract' : v === 'batch' ? '📦 Batch' : '📊 Analytics'}
            </button>
          ))}
        </div>
      </nav>

      {/* ── Views ── */}
      <main style={{ flex: 1, padding: '2rem 1.5rem' }}>
        <div className="container">
          {view === 'home' && (
            <div className="fade-in">
              <Hero />
              <UrlInput onSubmit={handleSubmit} onUpload={handleUpload} />
              {history.length > 0 && <History history={history} onSelect={(r) => { setResult(r); setView('results') }} />}
            </div>
          )}
          {view === 'processing' && (
            <div className="fade-in">
              <ProgressTracker
                taskId={taskId}
                onComplete={handleComplete}
                onError={(e) => { alert(`Processing failed: ${e}`); setView('home') }}
              />
            </div>
          )}
          {view === 'results' && result && (
            <div className="fade-in">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                <div>
                  <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>
                    {result.basic_identification?.movie_name || result.basic_identification?.trailer_title || 'Extraction Results'}
                  </h2>
                  <p className="text-muted text-sm" style={{ marginTop: '0.25rem' }}>
                    Processed in {result.processing_time_seconds}s
                    {result.errors?.length > 0 && ` · ${result.errors.length} warning(s)`}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button className="btn btn-secondary" onClick={handleReset}>← New</button>
                  <button className="btn btn-primary" onClick={() => {
                    const a = document.createElement('a')
                    a.href = `/api/export/${result.task_id}`
                    a.download = `trailer_${result.task_id}.json`
                    a.click()
                  }}>⬇ Export JSON</button>
                </div>
              </div>
              <MetadataDisplay data={result} />
            </div>
          )}
          {view === 'batch' && (
            <div className="fade-in">
              <BatchProcessor />
            </div>
          )}
          {view === 'analytics' && (
            <div className="fade-in">
              <AnalyticsDashboard />
            </div>
          )}
        </div>
      </main>

      <footer style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)',
        fontSize: '0.8rem', borderTop: '1px solid var(--border)' }}>
        TrailerIQ · AI-powered with Whisper, CLIP, GPT-4o · Built for Indian & global cinema
      </footer>
    </div>
  )
}

function Hero() {
  return (
    <div style={{ textAlign: 'center', padding: '3rem 0 2.5rem', maxWidth: 640, margin: '0 auto' }}>
      <div className="float-anim" style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎬</div>
      <h1 style={{ fontSize: 'clamp(2rem, 5vw, 3rem)', fontWeight: 800, lineHeight: 1.1 }}>
        Extract <span className="gradient-text">AI Metadata</span><br />from any Trailer
      </h1>
      <p style={{ marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.7 }}>
        Paste any YouTube movie trailer URL. Our 6-agent AI pipeline extracts cast, genre,
        plot summary, languages, and 50+ metadata fields — including Hindi, Tamil, Telugu,
        Malayalam, Kannada & more.
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap', marginTop: '1.25rem' }}>
        {['🤖 Whisper STT', '👁 CLIP Vision', '🧠 GPT-4o NLP', '🌏 9 Languages'].map(t => (
          <span key={t} className="badge badge--primary">{t}</span>
        ))}
      </div>
    </div>
  )
}

function History({ history, onSelect }) {
  return (
    <div style={{ marginTop: '2rem' }}>
      <p className="text-sm text-muted" style={{ marginBottom: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Recent Extractions</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {history.map(({ result: r, ts }) => (
          <button key={r.task_id} className="card" onClick={() => onSelect(r)}
            style={{ textAlign: 'left', cursor: 'pointer', padding: '0.85rem 1.25rem',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <div>
              <p style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                {r.basic_identification?.movie_name || 'Unknown movie'}
              </p>
              <p className="text-xs text-muted">{r.youtube_url?.slice(0, 60)}...</p>
            </div>
            <span className="badge badge--success">Done</span>
          </button>
        ))}
      </div>
    </div>
  )
}
