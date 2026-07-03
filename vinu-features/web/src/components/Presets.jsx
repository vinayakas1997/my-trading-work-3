import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function Presets({ onSelectPreset, showToast }) {
  const [presets, setPresets] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api('/presets')
      .then(d => setPresets(d.data || []))
      .catch(e => showToast('Failed to load presets: ' + e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-dim)' }}>Loading...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Preset Blueprints</h2>
      {presets.length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No presets available.</p>
      ) : (
        presets.map(p => (
          <div key={p.name} className="glass-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1rem', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{p.name}</h3>
                {p.description && <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>{p.description}</p>}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                  {(p.features || []).map((f, i) => (
                    <span key={i} className="chip" style={{ fontSize: '0.72rem' }}>{f}</span>
                  ))}
                </div>
              </div>
              <button type="button" className="btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.82rem', whiteSpace: 'nowrap' }}
                onClick={onSelectPreset}>Use</button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
