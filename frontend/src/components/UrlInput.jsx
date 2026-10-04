import { useState } from 'react'

const YOUTUBE_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]{11}/

function isValidYouTubeUrl(url) {
  return YOUTUBE_REGEX.test(url.trim())
}

export default function UrlInput({ onSubmit, onUpload }) {
  const [activeTab, setActiveTab] = useState('url') // 'url' | 'file'
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (activeTab === 'url') {
        const trimmed = url.trim()
        if (!trimmed) { throw new Error('Please enter a YouTube URL') }
        if (!isValidYouTubeUrl(trimmed)) { throw new Error('Please enter a valid YouTube video URL') }
        await onSubmit(trimmed)
      } else {
        if (!file) { throw new Error('Please select a video file to upload') }
        await onUpload(file)
      }
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    if (selected) {
      if (!selected.type.startsWith('video/')) {
        setError('Only video files are supported')
        return
      }
      setFile(selected)
      setError('')
    }
  }

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      setUrl(text)
      setError('')
    } catch { /* clipboard access denied */ }
  }

  const examples = [
    { label: 'Bollywood', url: 'https://www.youtube.com/watch?v=example1' },
    { label: 'Tollywood', url: 'https://www.youtube.com/watch?v=example2' },
    { label: 'Hollywood', url: 'https://www.youtube.com/watch?v=example3' },
  ]

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <div className="card card--glow" style={{ padding: '0' }}>
        {/* Tab Header */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
          <button 
            type="button" 
            onClick={() => setActiveTab('url')}
            className={`tab-btn ${activeTab === 'url' ? 'active' : ''}`}
            style={{ flex: 1, padding: '1rem', background: 'none', border: 'none', 
              color: activeTab === 'url' ? 'var(--primary-light)' : 'var(--text-muted)',
              borderBottom: activeTab === 'url' ? '2px solid var(--primary)' : 'none',
              fontWeight: activeTab === 'url' ? 700 : 500, cursor: 'pointer' }}
          >
            🔗 YouTube URL
          </button>
          <button 
            type="button" 
            onClick={() => setActiveTab('file')}
            className={`tab-btn ${activeTab === 'file' ? 'active' : ''}`}
            style={{ flex: 1, padding: '1rem', background: 'none', border: 'none',
              color: activeTab === 'file' ? 'var(--primary-light)' : 'var(--text-muted)',
              borderBottom: activeTab === 'file' ? '2px solid var(--primary)' : 'none',
              fontWeight: activeTab === 'file' ? 700 : 500, cursor: 'pointer' }}
          >
            📁 Local File
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.75rem' }}>
          {activeTab === 'url' ? (
            <div>
              <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: 600, fontSize: '0.95rem' }}>
                YouTube Trailer URL
              </label>

              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'stretch' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <span style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)',
                    fontSize: '1.1rem', pointerEvents: 'none' }}>▶</span>
                  <input
                    id="youtube-url-input"
                    className={`input ${error ? 'error' : ''}`}
                    style={{ paddingLeft: '2.5rem' }}
                    type="url"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={url}
                    onChange={e => { setUrl(e.target.value); setError('') }}
                    disabled={loading}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <button type="button" className="btn btn-secondary" onClick={handlePaste}
                  disabled={loading} title="Paste from clipboard" style={{ padding: '0.65rem 1rem' }}>
                  📋
                </button>
              </div>
            </div>
          ) : (
            <div>
              <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: 600, fontSize: '0.95rem' }}>
                Upload Local Trailer
              </label>
              <div 
                className={`dropzone ${isDragging ? 'dragging' : ''} ${error ? 'error' : ''}`}
                onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={e => {
                  e.preventDefault()
                  setIsDragging(false)
                  const dropped = e.dataTransfer.files[0]
                  if (dropped && dropped.type.startsWith('video/')) {
                    setFile(dropped)
                    setError('')
                  } else {
                    setError('Please drop a valid video file')
                  }
                }}
                onClick={() => document.getElementById('file-upload').click()}
                style={{ 
                  border: '2px dashed var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '2rem',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: isDragging ? 'rgba(121, 57, 255, 0.05)' : 'rgba(255,255,255,0.01)',
                  transition: 'all 0.2s ease'
                }}
              >
                <input 
                  id="file-upload" 
                  type="file" 
                  hidden 
                  accept="video/*" 
                  onChange={handleFileChange}
                />
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📤</div>
                {file ? (
                  <p style={{ fontWeight: 600, color: 'var(--primary-light)' }}>
                    {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                  </p>
                ) : (
                  <p className="text-muted">
                    Drag & drop video or <span style={{ color: 'var(--primary-light)' }}>browse</span>
                  </p>
                )}
              </div>
            </div>
          )}

          {error && (
            <p style={{ marginTop: '0.5rem', color: 'var(--danger)', fontSize: '0.83rem' }}>
              ⚠ {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary w-full"
            style={{ marginTop: '1.25rem', padding: '0.85rem', fontSize: '1rem', justifyContent: 'center' }}
            disabled={loading || (activeTab === 'url' ? !url.trim() : !file)}>
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Spinner /> {activeTab === 'url' ? 'Starting pipeline...' : 'Uploading file...'}
              </span>
            ) : (
              <span>🚀 Extract Metadata</span>
            )}
          </button>

          <div style={{ marginTop: '1.25rem', padding: '1rem', background: 'rgba(255,255,255,0.02)',
            borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <p className="text-xs text-muted" style={{ marginBottom: '0.5rem', fontWeight: 600 }}>
              SUPPORTED LANGUAGES
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {['Hindi', 'Tamil', 'Telugu', 'Malayalam', 'Kannada', 'Bengali', 'Marathi', 'Punjabi', 'English'].map(lang => (
                <span key={lang} className="badge badge--purple">{lang}</span>
              ))}
            </div>
          </div>
        </form>
      </div>

      <div style={{ marginTop: '1rem', textAlign: 'center' }}>
        <p className="text-xs text-muted">
          Processing takes 2–5 minutes · Video is automatically deleted after extraction
        </p>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <span style={{ display: 'inline-block', width: 16, height: 16,
      border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
      borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
  )
}
