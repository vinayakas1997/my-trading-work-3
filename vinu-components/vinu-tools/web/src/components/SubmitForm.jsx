import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function SubmitForm({ showToast, onSubmitted }) {
  const [presets, setPresets] = useState([])
  const [form, setForm] = useState({
    title: '', symbols: '', days: 365, interval: '1d',
    preset: '', features: '', conditions: '', ml_model: '', ml_label: '',
    run_immediately: false,
  })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api('/presets').then(d => setPresets(d.data || [])).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || !form.symbols.trim()) {
      showToast('Title and symbols are required')
      return
    }
    setSubmitting(true)
    try {
      const body = {
        title: form.title.trim(),
        symbols: form.symbols.split(/[,\s]+/).map(s => s.trim().toUpperCase()).filter(Boolean),
        days: parseInt(form.days, 10) || 365,
        interval: form.interval,
        run_immediately: form.run_immediately,
      }
      if (form.preset) {
        body.preset = form.preset
      } else if (form.features.trim()) {
        body.features = form.features.split(',').map(f => f.trim()).filter(Boolean)
      } else {
        showToast('Select a preset or specify features')
        setSubmitting(false)
        return
      }
      if (form.conditions.trim()) body.conditions = form.conditions.trim()
      if (form.ml_model.trim()) body.ml_model = form.ml_model.trim()
      if (form.ml_label.trim()) body.ml_label = form.ml_label.trim()

      await api('/requests', { method: 'POST', body: JSON.stringify(body) })
      showToast('Request submitted successfully')
      onSubmitted()
    } catch (e) {
      showToast('Submit failed: ' + e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass-card">
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 1.25rem 0' }}>Submit Feature Request</h2>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Title *</label>
            <input type="text" required placeholder="e.g. swing_aapl" value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))} style={{ width: '100%' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Symbols *</label>
            <input type="text" required placeholder="AAPL, NVDA, TSLA" value={form.symbols}
              onChange={e => setForm(f => ({ ...f, symbols: e.target.value }))} style={{ width: '100%' }} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Days</label>
            <input type="number" min="1" max="3650" value={form.days}
              onChange={e => setForm(f => ({ ...f, days: e.target.value }))} style={{ width: '100%' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Interval</label>
            <select value={form.interval} onChange={e => setForm(f => ({ ...f, interval: e.target.value }))} style={{ width: '100%' }}>
              <option value="1d">1d</option>
              <option value="1h">1h</option>
              <option value="30m">30m</option>
              <option value="15m">15m</option>
              <option value="5m">5m</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Run immediately</label>
            <div style={{ display: 'flex', alignItems: 'center', height: '38px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.88rem' }}>
                <input type="checkbox" checked={form.run_immediately}
                  onChange={e => setForm(f => ({ ...f, run_immediately: e.target.checked }))} />
                Yes
              </label>
            </div>
          </div>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Preset (optional)</label>
          <select value={form.preset} onChange={e => setForm(f => ({ ...f, preset: e.target.value, features: '' }))} style={{ width: '100%' }}>
            <option value="">-- No preset (use custom features) --</option>
            {presets.map(p => (
              <option key={p.name} value={p.name}>{p.name} — {p.description}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
            Custom Features (comma-separated, ignored if preset selected)
          </label>
          <input type="text" placeholder="rsi, macd, bollinger, sma:period=50" value={form.features}
            disabled={!!form.preset}
            onChange={e => setForm(f => ({ ...f, features: e.target.value }))} style={{ width: '100%' }} />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Conditions (optional)</label>
          <textarea placeholder="price > 100 AND volume > 1000000" value={form.conditions}
            onChange={e => setForm(f => ({ ...f, conditions: e.target.value }))} style={{ width: '100%' }} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>ML Model (optional)</label>
            <input type="text" placeholder="lasso" value={form.ml_model}
              onChange={e => setForm(f => ({ ...f, ml_model: e.target.value }))} style={{ width: '100%' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>ML Label (optional)</label>
            <input type="text" placeholder="returns_5d" value={form.ml_label}
              onChange={e => setForm(f => ({ ...f, ml_label: e.target.value }))} style={{ width: '100%' }} />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)' }}>
          <button type="button" className="btn-secondary" onClick={() => setForm({
            title: '', symbols: '', days: 365, interval: '1d',
            preset: '', features: '', conditions: '', ml_model: '', ml_label: '',
            run_immediately: false,
          })}>Reset</button>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Request'}
          </button>
        </div>
      </form>
    </div>
  )
}
