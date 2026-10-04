import { useEffect, useState } from 'react'
import {
  Chart as ChartJS,
  ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, Title
} from 'chart.js'
import { Doughnut, Bar } from 'react-chartjs-2'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title)

const CHART_COLORS = [
  '#6366f1', '#8b5cf6', '#06b6d4', '#10b981',
  '#f59e0b', '#ef4444', '#ec4899', '#14b8a6',
  '#f97316', '#a78bfa', '#34d399', '#fb923c',
]

const CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
    },
    tooltip: {
      backgroundColor: '#0d1220',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      titleColor: '#f1f5f9',
      bodyColor: '#94a3b8',
    }
  },
  scales: {
    x: {
      ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 10 } },
      grid: { color: 'rgba(255,255,255,0.04)' },
    },
    y: {
      ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 10 } },
      grid: { color: 'rgba(255,255,255,0.06)' },
    },
  },
}

export default function AnalyticsDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/analytics')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const refresh = () => {
    setLoading(true)
    fetch('/api/analytics')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  if (loading) return <LoadingState />
  if (error) return <div className="alert alert--error">⚠ {error}</div>
  if (!data || data.total_processed === 0) return <EmptyState />

  // Genre donut chart
  const genreEntries = Object.entries(data.genre_distribution).sort((a, b) => b[1] - a[1])
  const genreChart = {
    labels: genreEntries.map(e => e[0]),
    datasets: [{
      data: genreEntries.map(e => e[1]),
      backgroundColor: CHART_COLORS.slice(0, genreEntries.length),
      borderColor: 'rgba(255,255,255,0.06)',
      borderWidth: 1,
    }]
  }

  // Language bar chart
  const langEntries = Object.entries(data.language_distribution).sort((a, b) => b[1] - a[1])
  const langChart = {
    labels: langEntries.map(e => e[0]),
    datasets: [{
      label: 'Trailers',
      data: langEntries.map(e => e[1]),
      backgroundColor: CHART_COLORS.map(c => c + 'cc'),
      borderColor: CHART_COLORS,
      borderWidth: 1,
      borderRadius: 6,
    }]
  }

  // Confidence bar chart
  const confEntries = Object.entries(data.avg_confidence)
    .sort((a, b) => b[1] - a[1]).slice(0, 8)
  const confChart = {
    labels: confEntries.map(e => e[0].replace(/_/g, ' ')),
    datasets: [{
      label: 'Avg Confidence',
      data: confEntries.map(e => Math.round(e[1] * 100)),
      backgroundColor: confEntries.map(e =>
        e[1] >= 0.85 ? '#10b981cc' :
        e[1] >= 0.65 ? '#f59e0bcc' : '#ef4444cc'
      ),
      borderColor: confEntries.map(e =>
        e[1] >= 0.85 ? '#10b981' : e[1] >= 0.65 ? '#f59e0b' : '#ef4444'
      ),
      borderWidth: 1,
      borderRadius: 4,
    }]
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>📊 Analytics Dashboard</h2>
          <p className="text-muted text-sm">Aggregated stats across all processed trailers</p>
        </div>
        <button className="btn btn-secondary" onClick={refresh}>↻ Refresh</button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'Total Processed', value: data.total_processed, emoji: '🎬' },
          { label: 'Genres Found',    value: Object.keys(data.genre_distribution).length, emoji: '🎭' },
          { label: 'Languages',       value: Object.keys(data.language_distribution).length, emoji: '🌏' },
          { label: 'Avg Confidence',  value: `${Math.round((Object.values(data.avg_confidence).reduce((a, b) => a + b, 0) / Math.max(Object.values(data.avg_confidence).length, 1)) * 100)}%`, emoji: '🎯' },
        ].map(s => (
          <div key={s.label} className="card" style={{ textAlign: 'center', padding: '1.25rem' }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.35rem' }}>{s.emoji}</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--primary-light), var(--accent))',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{s.value}</div>
            <div className="text-xs text-muted" style={{ marginTop: '0.25rem' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid-2" style={{ gap: '1.5rem', marginBottom: '1.5rem' }}>
        {genreEntries.length > 0 && (
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>🎭 Genre Distribution</h3>
            <div style={{ height: 240 }}>
              <Doughnut data={genreChart} options={{ ...CHART_OPTIONS, scales: undefined }} />
            </div>
          </div>
        )}
        {langEntries.length > 0 && (
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>🌏 Language Distribution</h3>
            <div style={{ height: 240 }}>
              <Bar data={langChart} options={CHART_OPTIONS} />
            </div>
          </div>
        )}
      </div>

      {confEntries.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>🎯 Average Confidence by Field</h3>
          <div style={{ height: 200 }}>
            <Bar data={confChart} options={CHART_OPTIONS} />
          </div>
        </div>
      )}

      {/* Safety Overview */}
      {data.moderation_stats && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>🛡️ Safety Severity Overview</h3>
          <div className="grid-2" style={{ alignItems: 'center' }}>
            <div style={{ height: 200 }}>
              <Doughnut 
                data={{
                  labels: ['Low Risk', 'Medium Risk', 'High Risk'],
                  datasets: [{
                    data: [
                      data.moderation_stats.low || 0,
                      data.moderation_stats.medium || 0,
                      data.moderation_stats.high || 0
                    ],
                    backgroundColor: ['#10b981cc', '#f59e0bcc', '#ef4444cc'],
                    borderColor: 'rgba(255,255,255,0.06)',
                    borderWidth: 1,
                  }]
                }} 
                options={{ ...CHART_OPTIONS, scales: undefined }} 
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', borderRadius: '0.5rem', backgroundColor: 'rgba(16,185,129,0.1)' }}>
                 <span style={{ color: '#10b981', fontWeight: 600 }}>Low Risk</span>
                 <span style={{ fontWeight: 700 }}>{data.moderation_stats.low || 0}</span>
               </div>
               <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', borderRadius: '0.5rem', backgroundColor: 'rgba(245,158,11,0.1)' }}>
                 <span style={{ color: '#f59e0b', fontWeight: 600 }}>Medium Risk</span>
                 <span style={{ fontWeight: 700 }}>{data.moderation_stats.medium || 0}</span>
               </div>
               <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', borderRadius: '0.5rem', backgroundColor: 'rgba(239,68,68,0.1)' }}>
                 <span style={{ color: '#ef4444', fontWeight: 600 }}>High Risk</span>
                 <span style={{ fontWeight: 700 }}>{data.moderation_stats.high || 0}</span>
               </div>
            </div>
          </div>
        </div>
      )}


      {/* Trailer type breakdown */}
      {Object.keys(data.trailer_type_breakdown).length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>🎞️ Trailer Type Breakdown</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {Object.entries(data.trailer_type_breakdown).map(([type, count]) => (
              <div key={type} className="badge badge--primary" style={{ fontSize: '0.88rem', padding: '0.4rem 1rem' }}>
                {type}: <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function LoadingState() {
  return (
    <div style={{ textAlign: 'center', padding: '4rem' }}>
      <span style={{ display: 'inline-block', width: 40, height: 40,
        border: '3px solid rgba(99,102,241,0.3)', borderTopColor: 'var(--primary)',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <p className="text-muted" style={{ marginTop: '1rem' }}>Loading analytics...</p>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{ textAlign: 'center', padding: '4rem 2rem' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📊</div>
      <h3 style={{ fontWeight: 700 }}>No data yet</h3>
      <p className="text-muted text-sm" style={{ marginTop: '0.5rem' }}>
        Process some trailers first, then come back here to see analytics.
      </p>
    </div>
  )
}
