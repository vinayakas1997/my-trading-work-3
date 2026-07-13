import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function Catalog({ showToast }) {
  const [indicators, setIndicators] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    api('/features')
      .then(d => setIndicators(d.data || []))
      .catch(e => showToast('Failed to load catalog: ' + e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = indicators.filter(i =>
    i.kind?.toLowerCase().includes(search.toLowerCase()) ||
    i.description?.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-dim)' }}>Loading...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Feature Catalog ({indicators.length})</h2>
        <input type="text" placeholder="Search indicators..." value={search}
          onChange={e => { setSearch(e.target.value); setSelected(null) }}
          style={{ width: '260px', fontSize: '0.85rem', padding: '0.4rem 0.6rem' }} />
      </div>

      {selected ? (
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{selected.kind}</h3>
              <p style={{ margin: '0.15rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>{selected.description}</p>
            </div>
            <button type="button" className="btn-secondary" style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
              onClick={() => setSelected(null)}>Back</button>
          </div>

          {selected.params && Object.keys(selected.params).length > 0 && (
            <div style={{ marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Parameters</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.35rem' }}>
                {Object.entries(selected.params).map(([name, spec]) => (
                  <span key={name} className="chip" style={{ fontSize: '0.78rem' }}>
                    {name}: {spec.default ?? '?'} ({spec.type || 'auto'})
                  </span>
                ))}
              </div>
            </div>
          )}

          {selected.output_columns && selected.output_columns.length > 0 && (
            <div style={{ marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Output Columns</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.35rem' }}>
                {selected.output_columns.map((col, i) => (
                  <span key={i} className="chip" style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>{col}</span>
                ))}
              </div>
            </div>
          )}

          {selected.examples && selected.examples.length > 0 && (
            <div>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Examples</span>
              <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {selected.examples.map((ex, i) => <li key={i}>{ex}</li>)}
              </ul>
            </div>
          )}

          {selected.help_text && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
              <pre style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}>{selected.help_text}</pre>
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '0.75rem' }}>
          {filtered.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', gridColumn: '1 / -1' }}>No indicators match your search.</p>
          ) : (
            filtered.map(ind => (
              <div key={ind.kind} className="glass-card" style={{ padding: '1rem', cursor: 'pointer' }}
                onClick={() => setSelected(ind)}>
                <h4 style={{ margin: '0 0 0.25rem 0', fontSize: '0.88rem', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{ind.kind}</h4>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.78rem', color: 'var(--text-muted)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {ind.description || '-'}
                </p>
                {ind.output_columns && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem' }}>
                    {ind.output_columns.slice(0, 3).map((c, i) => (
                      <span key={i} style={{ fontSize: '0.65rem', padding: '0.1rem 0.3rem', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{c}</span>
                    ))}
                    {ind.output_columns.length > 3 && <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>+{ind.output_columns.length - 3}</span>}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
