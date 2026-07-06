import { useState, useEffect, useMemo } from 'react'
import { api } from '../api.js'

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

export default function Dashboard({ onViewRequest, showToast }) {
  const [health, setHealth] = useState(null)
  const [features, setFeatures] = useState(null)
  const [presets, setPresets] = useState(null)
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [h, f, p, list] = await Promise.all([
        api('/health'),
        api('/features'),
        api('/presets'),
        api('/requests?limit=200'),
      ])
      setHealth(h)
      setFeatures(f)
      setPresets(p)
      setRequests(list.data || [])
    } catch (e) {
      showToast('Failed to load dashboard: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const counts = useMemo(() => {
    const c = { pending: 0, running: 0, done: 0, failed: 0 }
    requests.forEach(r => { if (c[r.status] !== undefined) c[r.status]++ })
    return c
  }, [requests])

  const successRate = useMemo(() => {
    const total = counts.done + counts.failed
    return total > 0 ? (counts.done / total * 100).toFixed(1) : null
  }, [counts])

  const totalRows = useMemo(() =>
    requests.reduce((sum, r) => sum + (r.row_count || 0), 0),
    [requests]
  )

  const topSymbols = useMemo(() => {
    const freq = {}
    requests.forEach(r => (r.symbols || []).forEach(s => { freq[s] = (freq[s] || 0) + 1 }))
    return Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 5)
  }, [requests])

  const topPresets = useMemo(() => {
    const freq = {}
    requests.forEach(r => { if (r.preset) freq[r.preset] = (freq[r.preset] || 0) + 1 })
    return Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 5)
  }, [requests])

  const mlModels = useMemo(() => {
    const models = new Set()
    requests.forEach(r => { if (r.ml_model) models.add(r.ml_model) })
    return [...models]
  }, [requests])

  const recentFailures = useMemo(() =>
    requests.filter(r => r.status === 'failed')
      .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
      .slice(0, 5),
    [requests]
  )

  const activityTrend = useMemo(() => {
    const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const today = new Date()
    const last7 = []
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      last7.push({ label: dayLabels[d.getDay()], date: d.toISOString().split('T')[0], count: 0 })
    }
    requests.forEach(r => {
      const date = r.created_at?.split('T')[0]
      if (date) {
        const found = last7.find(d => d.date === date)
        if (found) found.count++
      }
    })
    return { days: last7, maxCount: Math.max(...last7.map(d => d.count), 1) }
  }, [requests])

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-dim)' }}>Loading...</div>

  const info = health?.info || {}
  const maxSymbol = Math.max(...topSymbols.map(s => s[1]), 1)
  const maxPreset = Math.max(...topPresets.map(p => p[1]), 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
        {[
          { label: 'Pending', value: counts.pending, color: 'var(--warning)' },
          { label: 'Running', value: counts.running, color: 'var(--info)' },
          { label: 'Done', value: counts.done, color: 'var(--success)' },
          { label: 'Failed', value: counts.failed, color: 'var(--danger)' },
          { label: 'Total', value: requests.length, color: 'var(--text-main)' },
          { label: 'Features', value: features?.count ?? info.catalog_count ?? '-', color: 'var(--primary)' },
          { label: 'Presets', value: presets?.count ?? info.presets_count ?? '-', color: 'var(--primary)' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <span className="stat-value" style={{ color: s.color }}>{s.value}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Secondary Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
        {successRate !== null && (
          <div className="stat-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem' }}>
            <span className="stat-label" style={{ margin: 0 }}>Success Rate</span>
            <span className="stat-value" style={{ color: 'var(--success)', fontSize: '1.25rem' }}>{successRate}%</span>
          </div>
        )}
        <div className="stat-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem' }}>
          <span className="stat-label" style={{ margin: 0 }}>Total Rows Generated</span>
          <span className="stat-value" style={{ color: 'var(--info)', fontSize: '1.25rem' }}>{totalRows.toLocaleString()}</span>
        </div>
      </div>

      {/* System Health */}
      <div className="glass-card">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>System Health</h2>
        {health ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem', fontSize: '0.88rem' }}>
            <div>Data dir: <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{info.data_dir || '-'}</strong></div>
            <div>Stock API: <strong>{info.stock_api_url || '-'}</strong></div>
            <div>DB path: <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{info.db_path || '-'}</strong></div>
            <div>DB size: <strong>{formatSize(info.db_size_bytes)}</strong></div>
            <div>Total requests: <strong>{info.total_request_count ?? '-'}</strong></div>
            <div>
              Status:{' '}
              {info.status_counts
                ? Object.entries(info.status_counts).map(([s, c]) => (
                    <span key={s} className={`status-badge ${s}`} style={{ marginLeft: '0.3rem' }}>{s}: {c}</span>
                  ))
                : <strong>-</strong>}
            </div>
          </div>
        ) : (
          <span style={{ color: 'var(--text-dim)' }}>Offline</span>
        )}
      </div>

      {/* Quick Insights: Top Symbols + Most Used Presets */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1.25rem' }}>
        {/* Top Symbols */}
        <div className="glass-card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>Top Symbols</h2>
          {topSymbols.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', margin: 0 }}>No symbols found.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topSymbols.map(([symbol, count]) => (
                <div key={symbol} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, width: '60px' }}>{symbol}</span>
                  <div style={{ flex: 1, height: '20px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(count / maxSymbol) * 100}%`, background: 'var(--primary)', borderRadius: '4px', opacity: 0.7, minWidth: '4px' }} />
                  </div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600, width: '50px', textAlign: 'right' }}>{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Most Used Presets + ML Models */}
        <div className="glass-card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>Most Used Presets</h2>
          {topPresets.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', margin: 0 }}>No presets found.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topPresets.map(([preset, count]) => (
                <div key={preset} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, width: '100px' }}>{preset}</span>
                  <div style={{ flex: 1, height: '20px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(count / maxPreset) * 100}%`, background: 'var(--success)', borderRadius: '4px', opacity: 0.7, minWidth: '4px' }} />
                  </div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600, width: '50px', textAlign: 'right' }}>{count}</span>
                </div>
              ))}
            </div>
          )}
          {mlModels.length > 0 && (
            <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600, marginRight: '0.5rem' }}>ML Models:</span>
              <div className="chips" style={{ display: 'inline-flex' }}>
                {mlModels.map(m => <span key={m} className="chip">{m}</span>)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Activity Trend */}
      <div className="glass-card">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>Activity (Last 7 Days)</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {activityTrend.days.map(d => (
            <div key={d.date} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-dim)', width: '40px' }}>{d.label}</span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', width: '60px' }}>{d.date?.slice(5)}</span>
              <div style={{ flex: 1, height: '24px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${(d.count / activityTrend.maxCount) * 100}%`,
                  background: d.count > 0 ? 'linear-gradient(90deg, var(--primary), var(--info))' : 'transparent',
                  borderRadius: '4px', minWidth: d.count > 0 ? '4px' : 0,
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, width: '30px', textAlign: 'right' }}>{d.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Failures */}
      {recentFailures.length > 0 && (
        <div className="glass-card" style={{ borderColor: 'rgba(239, 68, 68, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: 'var(--danger)' }}>Recent Failures ({recentFailures.length})</h2>
            <button type="button" className="btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
              onClick={() => onViewRequest(null)}>View All</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {recentFailures.map(r => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0.6rem', background: 'rgba(239,68,68,0.04)', borderRadius: '6px', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.title}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-dim)' }}>{r.symbols?.join(', ')}</span>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{timeAgo(r.updated_at)}</span>
                  {r.error_message && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>
                      — {r.error_message}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.3rem', flexShrink: 0 }}>
                  <button type="button" className="btn-primary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                    onClick={async () => {
                      try { await api(`/requests/${r.id}/run`, { method: 'POST' }); showToast('Retry triggered'); load() }
                      catch (e) { showToast('Retry failed: ' + e.message) }
                    }}>Retry</button>
                  <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                    onClick={() => onViewRequest(r.id)}>View</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Runs Table */}
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
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', minWidth: '600px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-dim)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Title</th>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Symbols</th>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Status</th>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Rows</th>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Created</th>
                  <th style={{ padding: '0.5rem 0.4rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(r => (
                  <tr key={r.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '0.6rem 0.4rem', fontWeight: 600, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</td>
                    <td style={{ padding: '0.6rem 0.4rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{r.symbols?.join(', ')}</td>
                    <td style={{ padding: '0.6rem 0.4rem', textAlign: 'center' }}>
                      <span className={`status-badge ${r.status}`}>{r.status}</span>
                    </td>
                    <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', color: 'var(--text-dim)' }}>{r.row_count ?? '-'}</td>
                    <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{r.created_at?.split('T')[0]}</td>
                    <td style={{ padding: '0.6rem 0.4rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                        onClick={() => onViewRequest(r.id)}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
