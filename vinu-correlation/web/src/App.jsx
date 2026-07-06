import { useState } from 'react'
import CorrelationDashboard from './components/CorrelationDashboard.jsx'
import { WATCHLIST } from './api.js'

export default function App() {
  const [ticker, setTicker] = useState('AAPL')
  const [searchInput, setSearchInput] = useState('')

  const handleSearch = (e) => {
    e.preventDefault()
    const val = searchInput.trim().toUpperCase()
    if (val) setTicker(val)
    setSearchInput('')
  }

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1 className="sidebar-title">vinu-correlation</h1>
          <p className="sidebar-subtitle">News ↔ Price Bridge</p>
        </div>

        <form onSubmit={handleSearch} style={{ padding: '0 0.75rem 0.75rem' }}>
          <input
            type="text"
            placeholder="Search ticker..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ width: '100%', fontSize: '0.82rem', padding: '0.45rem 0.6rem' }}
          />
        </form>

        <div style={{ padding: '0 0.75rem 0.35rem', fontSize: '0.68rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Watchlist
        </div>

        {WATCHLIST.map(s => (
          <button
            key={s}
            type="button"
            className={`sidebar-link${ticker === s ? ' active' : ''}`}
            onClick={() => setTicker(s)}
          >
            <span>{s}</span>
            {ticker === s && <span style={{ fontSize: '0.6rem', color: 'var(--primary)' }}>●</span>}
          </button>
        ))}
      </nav>

      <main className="main-content">
        <CorrelationDashboard key={ticker} ticker={ticker} />
      </main>
    </div>
  )
}
