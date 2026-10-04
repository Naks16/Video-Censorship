import { useState } from 'react'
import ConfidenceBar from './ConfidenceBar.jsx'
import JsonViewer from './JsonViewer.jsx'

const TABS = [
  { id: 'basic',        label: 'Basic',        emoji: '🎯' },
  { id: 'credits',      label: 'Credits',      emoji: '🎬' },
  { id: 'content',      label: 'Content',      emoji: '📝' },
  { id: 'trailer',      label: 'Trailer',      emoji: '🎞️' },
  { id: 'technical',    label: 'Technical',    emoji: '⚙️' },
  { id: 'discovery',    label: 'Discovery',    emoji: '🔎' },
  { id: 'audience',     label: 'Audience',     emoji: '👥' },
  { id: 'distribution', label: 'Distribution', emoji: '📢' },
  { id: 'engagement',   label: 'Engagement',   emoji: '📊' },
  { id: 'safety',       label: 'Safety',       emoji: '🛡️' },
  { id: 'json',         label: 'Raw JSON',     emoji: '{ }' },
]


export default function MetadataDisplay({ data }) {
  const [activeTab, setActiveTab] = useState('basic')
  const cs = data.confidence_scores || {}

  return (
    <div>
      {/* Score card */}
      {data.trailer_score && <ScoreCard score={data.trailer_score} />}

      {/* Errors */}
      {data.errors?.length > 0 && (
        <div className="alert alert--warning" style={{ marginBottom: '1rem' }}>
          <span>⚠</span>
          <div>
            <strong>Warnings ({data.errors.length})</strong>
            <ul style={{ marginTop: '0.3rem', paddingLeft: '1rem' }}>
              {data.errors.map((e, i) => <li key={i} style={{ fontSize: '0.83rem' }}>{e}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="tabs" style={{ marginBottom: '1rem' }}>
        {TABS.map(t => (
          <button key={t.id} className={`tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}>
            <span>{t.emoji}</span> {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="card fade-in" key={activeTab}>
        {activeTab === 'basic'        && <BasicTab d={data.basic_identification} cs={cs} />}
        {activeTab === 'credits'      && <CreditsTab d={data.creative_credits} cs={cs} />}
        {activeTab === 'content'      && <ContentTab d={data.content_descriptors} cs={cs} />}
        {activeTab === 'trailer'      && <TrailerTab d={data.trailer_specific} cs={cs} />}
        {activeTab === 'technical'    && <TechnicalTab d={data.technical_metadata} />}
        {activeTab === 'discovery'    && <DiscoveryTab d={data.search_discovery} />}
        {activeTab === 'audience'     && <AudienceTab d={data.audience_classification} cs={cs} />}
        {activeTab === 'distribution' && <DistributionTab d={data.distribution_marketing} />}
        {activeTab === 'engagement'   && <EngagementTab d={data.engagement_metadata} />}
        {activeTab === 'safety'       && <ModerationTab d={data.moderation} />}
        {activeTab === 'json'         && <JsonViewer data={data} />}

      </div>
    </div>
  )
}

// ── Tab panels ────────────────────────────────────────────────

function Field({ label, value, confidence, chip }) {
  const isEmpty = value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
  return (
    <div className="field-row">
      <span className="field-label">{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        {isEmpty
          ? <span className="field-value empty">Not detected</span>
          : Array.isArray(value)
            ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {value.map((v, i) => <span key={i} className={`badge badge--${chip || 'primary'}`}>{v}</span>)}
              </div>
            : <span className="field-value">{String(value)}</span>
        }
        {confidence !== undefined && confidence > 0 && (
          <ConfidenceBar value={confidence} small />
        )}
      </div>
    </div>
  )
}

function BasicTab({ d, cs }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Movie Name"       value={d.movie_name}       confidence={cs.movie_name} />
      <Field label="Trailer Title"    value={d.trailer_title} />
      <Field label="Release Year"     value={d.release_year}     confidence={cs.release_year} />
      <Field label="Languages"        value={d.languages}        confidence={cs.language} chip="cyan" />
      <Field label="Country of Origin" value={d.country_of_origin} />
    </div>
  )
}

function CreditsTab({ d, cs }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Director"          value={d.director}          confidence={cs.director} />
      <Field label="Main Cast"         value={d.main_cast}         confidence={cs.main_cast} chip="purple" />
      <Field label="Producers"         value={d.producers}         chip="purple" />
      <Field label="Production Company" value={d.production_company} />
      <Field label="Screenwriter"      value={d.screenwriter} />
      <Field label="Music Composer"    value={d.music_composer} />
    </div>
  )
}

function ContentTab({ d, cs }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Genres"       value={d.genres}       confidence={cs.genres} chip="primary" />
      <Field label="Subgenre"     value={d.subgenre} />
      <Field label="Themes"       value={d.themes}       confidence={cs.themes} chip="cyan" />
      <Field label="Tone"         value={d.tone}         confidence={cs.tone} />
      <div className="field-row">
        <span className="field-label">Plot Summary</span>
        {d.plot_summary
          ? <p style={{ lineHeight: 1.7, color: 'var(--text-primary)', fontSize: '0.95rem' }}>{d.plot_summary}</p>
          : <span className="field-value empty">Not detected</span>}
        {cs.plot_summary > 0 && <ConfidenceBar value={cs.plot_summary} small />}
      </div>
    </div>
  )
}

function TrailerTab({ d, cs }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Trailer Type"    value={d.trailer_type}    confidence={cs.trailer_type} />
      <Field label="Trailer Number"  value={d.trailer_number} />
      <Field label="Duration"        value={d.duration ? `${Math.floor(d.duration / 60)}m ${Math.round(d.duration % 60)}s` : null} />
      <Field label="Release Date"    value={d.trailer_release_date} />
      <Field label="Version"         value={d.version} />
    </div>
  )
}

function TechnicalTab({ d }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Resolution"   value={d.resolution} />
      <Field label="Aspect Ratio" value={d.aspect_ratio} />
      <Field label="Frame Rate"   value={d.frame_rate ? `${d.frame_rate} fps` : null} />
      <Field label="Audio Format" value={d.audio_format} />
      <Field label="File Format"  value={d.file_format} />
    </div>
  )
}

function DiscoveryTab({ d }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Keywords"      value={d.keywords}      chip="primary" />
      <Field label="Hashtags"      value={d.hashtags}      chip="cyan" />
      <Field label="Franchise"     value={d.franchise_name} />
      <Field label="Related Movies" value={d.related_movies} chip="purple" />
    </div>
  )
}

function AudienceTab({ d, cs }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Age Rating"       value={d.age_rating}        confidence={cs.age_rating} />
      <Field label="Content Warnings" value={d.content_warnings}  chip="warning" />
      <Field label="Target Audience"  value={d.target_audience} />
    </div>
  )
}

function DistributionTab({ d }) {
  if (!d) return <Empty />
  return (
    <div>
      <Field label="Studio"        value={d.studio} />
      <Field label="Distributor"   value={d.distributor} />
      <Field label="Social Handles" value={d.social_handles}  chip="cyan" />
      <Field label="Campaign Tags"  value={d.campaign_tags}   chip="primary" />
      <div className="field-row">
        <span className="field-label">Official Links</span>
        {d.official_links?.length
          ? <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {d.official_links.map((l, i) => (
                <a key={i} href={l} target="_blank" rel="noreferrer"
                  style={{ color: 'var(--accent)', fontSize: '0.85rem', wordBreak: 'break-all' }}>{l}</a>
              ))}
            </div>
          : <span className="field-value empty">Not detected</span>}
      </div>
    </div>
  )
}

function ModerationTab({ d }) {
  if (!d) return <Empty />
  
  const severityColor = 
    d.severity === 'high' ? '#ef4444' : 
    d.severity === 'medium' ? '#f59e0b' : '#10b981'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>🛡️ Content Safety Analysis</h3>
          <p className="text-sm text-muted">AI-driven visual and audio moderation assessment</p>
        </div>
        <div style={{ 
          padding: '0.4rem 1rem', 
          borderRadius: '2rem', 
          backgroundColor: `${severityColor}20`, 
          border: `1px solid ${severityColor}`,
          color: severityColor,
          fontWeight: 700,
          fontSize: '0.85rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          Severity: {d.severity}
        </div>
      </div>

      <div className="grid-2" style={{ gap: '1.5rem', marginBottom: '2rem' }}>
        {/* Visual Safety */}
        <div className="card" style={{ backgroundColor: 'rgba(255,255,255,0.02)', padding: '1.25rem' }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-secondary)' }}>👁 Visual Moderation</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
             <ScoreGauge label="Nudity" value={d.nudity_score} />
             <ScoreGauge label="Violence" value={d.violence_score} />
             <FlagItem label="Sexually Explicit" active={d.sexually_explicit_content} />
          </div>
        </div>

        {/* Audio Safety */}
        <div className="card" style={{ backgroundColor: 'rgba(255,255,255,0.02)', padding: '1.25rem' }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-secondary)' }}>🔊 Audio Moderation</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
             <FlagItem label="Abusive Language" active={d.audio_abusive_language} />
             <FlagItem label="Sexual Content" active={d.audio_sexual_content} />
             <FlagItem label="Threats / Hate Speech" active={d.audio_threats} />
          </div>
        </div>
      </div>

      {/* Summary Card */}
      <div className="card" style={{ borderLeft: `4px solid ${severityColor}`, padding: '1.25rem' }}>
        <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>📝 Safety Summary</h4>
        <p style={{ lineHeight: 1.7, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
          {d.summary}
        </p>
      </div>
    </div>
  )
}

function ScoreGauge({ label, value }) {
  const percentage = Math.round(value * 100)
  const color = value > 0.6 ? '#ef4444' : value > 0.3 ? '#f59e0b' : '#10b981'
  
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: '0.8rem', color: color, fontWeight: 700 }}>{percentage}%</span>
      </div>
      <div style={{ height: 6, backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 3 }}>
        <div style={{ 
          height: '100%', 
          width: `${percentage}%`, 
          backgroundColor: color, 
          borderRadius: 3,
          boxShadow: `0 0 8px ${color}40`,
          transition: 'width 1s ease'
        }} />
      </div>
    </div>
  )
}

function FlagItem({ label, active }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
      <span style={{ fontSize: '0.85rem' }}>{label}</span>
      <span style={{ 
        fontSize: '0.75rem', 
        padding: '0.2rem 0.6rem', 
        borderRadius: '1rem',
        backgroundColor: active ? '#ef444420' : '#10b98120',
        color: active ? '#ef4444' : '#10b981',
        border: `1px solid ${active ? '#ef444440' : '#10b98140'}`,
        fontWeight: 600
      }}>
        {active ? '🚩 Flagged' : '✓ Safe'}
      </span>
    </div>
  )
}

function EngagementTab({ d }) {

  if (!d) return <Empty />
  return (
    <div>
      {d.thumbnail_url && (
        <div style={{ marginBottom: '1rem' }}>
          <img src={d.thumbnail_url} alt="Thumbnail" style={{ width: '100%', maxWidth: 480,
            borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }} />
        </div>
      )}
      <Field label="Upload Date" value={d.upload_date} />
      <Field label="Views"  value={d.views ? d.views.toLocaleString() : null} />
      <Field label="Likes"  value={d.likes ? d.likes.toLocaleString() : null} />
      <div className="field-row">
        <span className="field-label">Description</span>
        {d.description
          ? <p style={{ maxHeight: 200, overflow: 'auto', fontSize: '0.83rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{d.description}</p>
          : <span className="field-value empty">Not available</span>}
      </div>
    </div>
  )
}

function ScoreCard({ score }) {
  const bars = [
    { label: 'Excitement',  value: score.excitement_score,  color: '#f59e0b' },
    { label: 'Clarity',     value: score.clarity_score,     color: '#06b6d4' },
    { label: 'Emotional',   value: score.emotional_impact,  color: '#ec4899' },
    { label: 'Production',  value: score.production_quality, color: '#10b981' },
  ]
  return (
    <div className="card" style={{ marginBottom: '1rem', padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div>
          <p style={{ fontWeight: 700, fontSize: '0.9rem' }}>🏆 Engagement Score</p>
          <p className="text-xs text-muted">{score.score_explanation}</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '2rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--primary-light), var(--accent))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            {score.overall_score.toFixed(0)}
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>/100</span>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '0.5rem' }}>
        {bars.map(b => (
          <div key={b.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{b.label}</span>
              <span style={{ fontSize: '0.72rem', color: b.color, fontWeight: 700 }}>{b.value.toFixed(0)}</span>
            </div>
            <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${b.value}%`, background: b.color,
                borderRadius: 2, transition: 'width 0.8s ease', boxShadow: `0 0 6px ${b.color}60` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Empty() {
  return <p className="text-muted" style={{ padding: '1rem 0', fontSize: '0.9rem' }}>No data available for this section.</p>
}
