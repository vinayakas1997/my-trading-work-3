import { useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import RequestList from './components/RequestList.jsx'
import RequestDetail from './components/RequestDetail.jsx'
import SubmitForm from './components/SubmitForm.jsx'
import Presets from './components/Presets.jsx'
import Catalog from './components/Catalog.jsx'

const TABS = [
  { key: 'dashboard', label: 'Dashboard', icon: '#' },
  { key: 'requests', label: 'Requests', icon: '#' },
  { key: 'submit', label: 'Submit', icon: '#' },
  { key: 'presets', label: 'Presets', icon: '#' },
  { key: 'catalog', label: 'Catalog', icon: '#' },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [selectedId, setSelectedId] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  const navTo = (t) => { setTab(t); setSelectedId(null) }
  const viewRequest = (id) => { setSelectedId(id); setTab('request-detail') }

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '1.5rem 1rem' }}>
      {toast && (
        <div className="animate-fade-in" style={{
          position: 'fixed', bottom: '1.5rem', left: '50%', transform: 'translateX(-50%)',
          background: '#312e81', border: '1px solid #4f46e5', color: '#e0e7ff',
          padding: '0.75rem 1.5rem', borderRadius: '8px', fontSize: '0.9rem',
          boxShadow: 'var(--shadow-xl)', zIndex: 1000, fontWeight: 600
        }}>
          {toast}
        </div>
      )}

      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '2rem' }}>F</span>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, letterSpacing: '-0.025em', background: 'linear-gradient(to right, #fff, #9ca3af)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              vinu-features
            </h1>
            <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-dim)' }}>Feature Run Registry</p>
          </div>
        </div>
      </header>

      <nav style={{ display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.5rem', paddingBottom: '1px' }}>
        {TABS.map(t => (
          <button key={t.key} type="button" onClick={() => navTo(t.key)}
            style={{
              padding: '0.7rem 1.1rem', border: 'none', background: 'none', cursor: 'pointer',
              fontSize: '0.88rem', fontWeight: tab === t.key ? 700 : 500,
              color: tab === t.key ? 'var(--primary)' : 'var(--text-muted)',
              borderBottom: `2px solid ${tab === t.key ? 'var(--primary)' : 'transparent'}`,
              transition: 'all 0.2s ease', outline: 'none',
            }}>
            {t.label}
          </button>
        ))}
      </nav>

      <div className="animate-fade-in">
        {tab === 'dashboard' && <Dashboard onViewRequest={viewRequest} showToast={showToast} />}
        {tab === 'requests' && <RequestList onViewRequest={viewRequest} showToast={showToast} />}
        {tab === 'request-detail' && <RequestDetail id={selectedId} onBack={() => navTo('requests')} showToast={showToast} />}
        {tab === 'submit' && <SubmitForm showToast={showToast} onSubmitted={() => navTo('requests')} />}
        {tab === 'presets' && <Presets onSelectPreset={() => navTo('submit')} showToast={showToast} />}
        {tab === 'catalog' && <Catalog showToast={showToast} />}
      </div>
    </div>
  )
}
