import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function RequestDetail({ id, onBack, showToast }) {
  const [req, setReq] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await api(`/requests/${id}`)
      setReq(data)
    } catch (e) {
      showToast('Failed to load request: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleRun = async () => {
    try {
      const data = await api(`/requests/${id}/run`, { method: 'POST' })
      setReq(data)
      showToast('Run completed')
    } catch (e) {
      showToast('Run failed: ' + e.message)
    }
  }

  const handleDelete = async () => {
    try {
      await api(`/requests/${id}`, { method: 'DELETE' })
      showToast('Request deleted')
      onBack()
    } catch (e) {
      showToast('Delete failed: ' + e.message)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-dim)' }}>Loading...</div>
  if (!req) return <p style={{ color: 'var(--text-dim)' }}>Request not found.</p>

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>{req.title}</h2>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>#{req.id} · {req.slug}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" className="btn-secondary" onClick={onBack}>Back</button>
          <button type="button" className="btn-primary" onClick={handleRun}
            disabled={req.status === 'running' || req.status === 'deleted'}>Run</button>
          <button type="button" className="btn-danger" onClick={handleDelete}>Delete</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Status</span>
          <div style={{ marginTop: '0.25rem' }}><span className={`status-badge ${req.status}`}>{req.status}</span></div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Symbols</span>
          <div style={{ marginTop: '0.25rem', fontFamily: 'var(--font-mono)', fontSize: '0.88rem' }}>{req.symbols?.join(', ')}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Range</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>
            {req.from_ts ? new Date(req.from_ts * 1000).toLocaleDateString() : '-'} → {req.to_ts ? new Date(req.to_ts * 1000).toLocaleDateString() : '-'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Interval</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.interval}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Preset</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.preset || 'Custom'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Row Count</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.row_count ?? '-'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>ML Model</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.ml_model || '-'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>ML Label</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.ml_label || '-'}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Created</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.created_at}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Updated</span>
          <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>{req.updated_at}</div>
        </div>
      </div>

      {req.features && req.features.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Features</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.35rem' }}>
            {req.features.map((f, i) => (
              <span key={i} className="chip">{typeof f === 'string' ? f : f.kind}</span>
            ))}
          </div>
        </div>
      )}

      {req.conditions && (
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Conditions</span>
          <pre style={{ background: 'rgba(255,255,255,0.02)', padding: '0.5rem', borderRadius: '6px', fontSize: '0.82rem', margin: '0.25rem 0 0', overflow: 'auto' }}>{req.conditions}</pre>
        </div>
      )}

      {req.error_message && (
        <div style={{ background: 'var(--danger-bg)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '8px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--danger)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Error</span>
          <pre style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', color: '#fca5a5', whiteSpace: 'pre-wrap' }}>{req.error_message}</pre>
        </div>
      )}

      {req.file_path && (
        <div>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Output</span>
          <div style={{ marginTop: '0.25rem', fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--text-muted)' }}>{req.file_path}</div>
        </div>
      )}
    </div>
  )
}
