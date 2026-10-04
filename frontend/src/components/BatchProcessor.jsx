import { useState } from 'react'

const YOUTUBE_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]{11}/

export default function BatchProcessor() {
  const [urls, setUrls] = useState('')
  const [tasks, setTasks] = useState([])   // [{ url, taskId, status, progress, result }]
  const [loading, setLoading] = useState(false)

  const parsedUrls = urls.split('\n').map(l => l.trim()).filter(l => l && YOUTUBE_REGEX.test(l))
  const invalidLines = urls.split('\n').map(l => l.trim()).filter(l => l && !YOUTUBE_REGEX.test(l))

  const handleSubmit = async () => {
    if (parsedUrls.length === 0) return
    if (parsedUrls.length > 10) { alert('Maximum 10 URLs per batch'); return }

    setLoading(true)
    try {
      const res = await fetch('/api/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls: parsedUrls }),
      })
      const data = await res.json()
      const initialTasks = data.task_ids.map((taskId, i) => ({
        url: parsedUrls[i],
        taskId,
        status: 'pending',
        progress: 0,
        result: null,
      }))
      setTasks(initialTasks)
      setLoading(false)

      // Poll all tasks
      initialTasks.forEach(t => pollTask(t.taskId))
    } catch (e) {
      alert(`Batch submit failed: ${e.message}`)
      setLoading(false)
    }
  }

  const pollTask = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${taskId}`)
        const data = await res.json()
        setTasks(prev => prev.map(t => t.taskId === taskId
          ? { ...t, status: data.status, progress: data.progress, currentStage: data.current_stage }
          : t
        ))
        if (data.status === 'completed') {
          clearInterval(interval)
          const r = await fetch(`/api/result/${taskId}`)
          const result = await r.json()
          setTasks(prev => prev.map(t => t.taskId === taskId ? { ...t, result } : t))
        } else if (data.status === 'failed') {
          clearInterval(interval)
        }
      } catch { clearInterval(interval) }
    }, 3000)
  }

  const handleExport = (task) => {
    const a = document.createElement('a')
    a.href = `/api/export/${task.taskId}`
    a.download = `trailer_${task.taskId}.json`
    a.click()
  }

  const completedCount = tasks.filter(t => t.status === 'completed').length
  const failedCount = tasks.filter(t => t.status === 'failed').length

  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.35rem' }}>
          📦 Batch Processing
        </h2>
        <p className="text-muted text-sm">
          Submit up to 10 YouTube trailer URLs at once. Each URL is processed independently.
        </p>
      </div>

      {tasks.length === 0 ? (
        <div className="card" style={{ padding: '1.75rem' }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.75rem' }}>
            YouTube URLs (one per line)
          </label>
          <textarea
            className="input"
            style={{ minHeight: 200, resize: 'vertical', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.83rem' }}
            placeholder={`https://www.youtube.com/watch?v=abc123\nhttps://www.youtube.com/watch?v=def456\nhttps://youtu.be/ghi789`}
            value={urls}
            onChange={e => setUrls(e.target.value)}
          />

          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span className="badge badge--success">{parsedUrls.length} valid</span>
            {invalidLines.length > 0 && <span className="badge badge--danger">{invalidLines.length} invalid</span>}
          </div>

          {invalidLines.length > 0 && (
            <div className="alert alert--warning" style={{ marginTop: '0.75rem' }}>
              <span>⚠</span>
              <div>
                <strong>Invalid lines (will be skipped):</strong>
                <ul style={{ marginTop: '0.25rem', paddingLeft: '1rem', fontSize: '0.82rem' }}>
                  {invalidLines.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              </div>
            </div>
          )}

          <button className="btn btn-primary w-full" style={{ marginTop: '1.25rem', justifyContent: 'center', padding: '0.85rem' }}
            onClick={handleSubmit} disabled={loading || parsedUrls.length === 0}>
            {loading ? 'Submitting...' : `🚀 Process ${parsedUrls.length} Trailer${parsedUrls.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      ) : (
        <div>
          {/* Summary */}
          <div className="card" style={{ padding: '1rem 1.5rem', marginBottom: '1.5rem',
            display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: '1rem', flex: 1, flexWrap: 'wrap' }}>
              <span className="badge badge--primary">{tasks.length} Total</span>
              <span className="badge badge--success">{completedCount} Done</span>
              {failedCount > 0 && <span className="badge badge--danger">{failedCount} Failed</span>}
              <span className="badge badge--warning">{tasks.length - completedCount - failedCount} Running</span>
            </div>
            <button className="btn btn-secondary" onClick={() => { setTasks([]); setUrls('') }}>
              ↩ New Batch
            </button>
          </div>

          {/* Task cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {tasks.map(task => (
              <div key={task.taskId} className="card" style={{
                borderColor: task.status === 'completed' ? 'rgba(16,185,129,0.3)' : task.status === 'failed' ? 'rgba(239,68,68,0.3)' : 'var(--border)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono, monospace',
                      color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {task.url}
                    </p>
                    {task.result?.basic_identification?.movie_name && (
                      <p style={{ fontWeight: 600, marginTop: '0.25rem' }}>
                        {task.result.basic_identification.movie_name}
                      </p>
                    )}
                    {task.currentStage && task.status === 'processing' && (
                      <p className="text-xs text-muted" style={{ marginTop: '0.2rem' }}>{task.currentStage}</p>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {task.status === 'processing' && (
                      <span style={{ fontSize: '0.8rem', color: 'var(--primary-light)' }}>{task.progress}%</span>
                    )}
                    <span className={`badge badge--${task.status === 'completed' ? 'success' : task.status === 'failed' ? 'danger' : task.status === 'processing' ? 'primary' : 'warning'}`}>
                      {task.status}
                    </span>
                    {task.status === 'completed' && (
                      <button className="btn btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
                        onClick={() => handleExport(task)}>⬇ Export</button>
                    )}
                  </div>
                </div>

                {task.status === 'processing' && (
                  <div style={{ marginTop: '0.75rem', height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2 }}>
                    <div style={{ height: '100%', width: `${task.progress}%`, background: 'linear-gradient(90deg, var(--primary), var(--accent))',
                      borderRadius: 2, transition: 'width 0.5s ease' }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
