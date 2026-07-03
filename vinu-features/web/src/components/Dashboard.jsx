import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function Dashboard({ onViewRequest, showToast }) {
  const [health, setHealth] = useState(null)
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [h, list] = await Promise.all([
        api('/health'),
        api('/requests?limit=10'),
      ])
      setHealth(h)
      setRequests(list.data || [])
    } catch (e) {
      showToast('Failed to load dashboard: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const counts = { pending: 0, running: 0, done: 0, failed: 0, deleted: 0 }
  requests.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++ })

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-dim)' }}>Loading...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
        {[
          { label: 'Pending', value: counts.pending, color: 'var(--warning)' },
          { label: 'Running', value: counts.running, color: 'var(--info)' },
          { label: 'Done', value: counts.done, color: 'var(--success)' },
          { label: 'Failed', value: counts.failed, color: 'var(--danger)' },
          { label: 'Total', value: requests.length, color: 'var(--text-main)' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <span className="stat-value" style={{ color: s.color }}>{s.value}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </div>

      <div className="glass-card">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>System Health</h2>
        {health ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.88rem' }}>
            <div>Data dir: <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{health.info?.data_dir || '-'}</strong></div>
            <div>Stock API: <strong>{health.info?.stock_api_url || '-'}</strong></div>
            <div>DB size: <strong>{health.info?.db_size_bytes ? (health.info.db_size_bytes / 1024).toFixed(0) + ' KB' : '-'}</strong></div>
            <div>Request count: <strong>{health.info?.request_count ?? '-'}</strong></div>
          </div>
        ) : (
          <span style={{ color: 'var(--text-dim)' }}>Offline</span>
        )}
      </div>

      <div className="glass-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Recent Runs</h2>
          <button type="button" className="btn-secondary" onClick={() => onViewRequest(null)} style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}>
            View All
          </button>
        </div>
        {requests.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', margin: 0 }}>No requests yet.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-dim)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Title</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Symbols</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Status</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Rows</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '0.6rem 0.4rem', fontWeight: 600 }}>{r.title}</td>
                  <td style={{ padding: '0.6rem 0.4rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{r.symbols?.join(', ')}</td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'center' }}>
                    <span className={`status-badge ${r.status}`}>{r.status}</span>
                  </td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', color: 'var(--text-dim)' }}>{r.row_count ?? '-'}</td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right' }}>
                    <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() => onViewRequest(r.id)}>View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
