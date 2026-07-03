import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function RequestList({ onViewRequest, showToast }) {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterTitle, setFilterTitle] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      let url = '/requests?limit=200'
      if (filterStatus) url += `&status=${encodeURIComponent(filterStatus)}`
      if (filterTitle) url += `&title=${encodeURIComponent(filterTitle)}`
      const data = await api(url)
      setRequests(data.data || [])
    } catch (e) {
      showToast('Failed to load requests: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filterStatus, filterTitle])

  const handleDelete = async (id) => {
    try {
      await api(`/requests/${id}`, { method: 'DELETE' })
      showToast('Request deleted')
      load()
    } catch (e) {
      showToast('Delete failed: ' + e.message)
    }
  }

  const handleRun = async (id) => {
    try {
      await api(`/requests/${id}/run`, { method: 'POST' })
      showToast('Run triggered')
      load()
    } catch (e) {
      showToast('Run failed: ' + e.message)
    }
  }

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Feature Requests</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="text" placeholder="Filter by title..." value={filterTitle}
            onChange={e => setFilterTitle(e.target.value)}
            style={{ width: '180px', fontSize: '0.82rem', padding: '0.4rem 0.6rem' }} />
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            style={{ fontSize: '0.82rem', padding: '0.4rem 0.6rem' }}>
            <option value="">All status</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="done">Done</option>
            <option value="failed">Failed</option>
            <option value="deleted">Deleted</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-dim)' }}>Loading...</div>
      ) : requests.length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No requests found.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', minWidth: '650px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-dim)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>ID</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Title</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Symbols</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Preset</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Status</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Rows</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Created</th>
                <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '0.6rem 0.4rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-dim)' }}>{r.id}</td>
                  <td style={{ padding: '0.6rem 0.4rem', fontWeight: 600, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</td>
                  <td style={{ padding: '0.6rem 0.4rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{r.symbols?.join(', ')}</td>
                  <td style={{ padding: '0.6rem 0.4rem', color: 'var(--text-dim)', fontSize: '0.8rem' }}>{r.preset || '-'}</td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'center' }}>
                    <span className={`status-badge ${r.status}`}>{r.status}</span>
                  </td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', color: 'var(--text-dim)' }}>{r.row_count ?? '-'}</td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{r.created_at?.split('T')[0]}</td>
                  <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem', marginRight: '0.25rem' }}
                      onClick={() => onViewRequest(r.id)}>View</button>
                    {r.status !== 'done' && (
                      <button type="button" className="btn-primary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem', marginRight: '0.25rem' }}
                        onClick={() => handleRun(r.id)} disabled={r.status === 'running' || r.status === 'deleted'}>Run</button>
                    )}
                    <button type="button" className="btn-danger" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                      onClick={() => handleDelete(r.id)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
