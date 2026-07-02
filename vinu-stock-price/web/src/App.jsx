import React, { useState, useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('settings')
  const [health, setHealth] = useState(null)
  const [healthStatus, setHealthStatus] = useState('loading…')
  const [healthClass, setHealthClass] = useState('health')
  const [pollInterval, setPollInterval] = useState(60)
  const [defaultProvider, setDefaultProvider] = useState('polygon')
  const [dataRoot, setDataRoot] = useState('—')
  const [watchlist, setWatchlist] = useState([])
  const [addTickersInput, setAddTickersInput] = useState('')
  const [actionStatus, setActionStatus] = useState('')
  const [catalog, setCatalog] = useState([])
  const [priceSymbol, setPriceSymbol] = useState('')
  const [priceInterval, setPriceInterval] = useState('5m')
  const [priceDays, setPriceDays] = useState('7')
  const [priceProvider, setPriceProvider] = useState('')
  const [priceSummary, setPriceSummary] = useState('')
  const [priceView, setPriceView] = useState('all')
  const [candles, setCandles] = useState([])
  const [symbolOptions, setSymbolOptions] = useState([])
  const [toast, setToast] = useState('')

  const chartContainerRef = useRef(null)
  const sparklineRef = useRef(null)

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(''), 4000)
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const j = await res.json()
        detail = j.detail || JSON.stringify(j)
      } catch (_) {}
      throw new Error(detail)
    }
    if (res.status === 204) return null
    return res.json()
  }

  function fmtTs(ts) {
    if (!ts) return '—'
    return new Date(ts * 1000).toLocaleString()
  }

  function getRowClass(entry) {
    if (!entry.last_bar_ts) return 'row-empty'
    const age = Date.now() / 1000 - entry.last_bar_ts
    return age < 172800 ? 'row-fresh' : 'row-stale'
  }

  const loadHealth = async () => {
    try {
      const data = await api('/health')
      setHealth(data)
      setHealthStatus(`${data.symbol_count} symbols · ${data.watchlist_size} watchlist`)
      setHealthClass('health ok')
    } catch (_) {
      setHealthStatus('offline')
      setHealthClass('health err')
    }
  }

  const loadSettings = async () => {
    try {
      const data = await api('/settings')
      setPollInterval(data.poll_interval_sec)
      setDefaultProvider(data.default_provider || 'polygon')
      setDataRoot(data.data_root || '—')
    } catch (e) {
      showToast(e.message)
    }
  }

  const loadWatchlist = async () => {
    try {
      const data = await api('/watchlist/tickers')
      setWatchlist(data.tickers || [])
    } catch (e) {
      showToast(e.message)
    }
  }

  const loadCatalog = async () => {
    try {
      const data = await api('/catalog')
      setCatalog(data.data || [])
    } catch (e) {
      showToast(e.message)
    }
  }

  // Initial load
  useEffect(() => {
    loadHealth()
    loadSettings()
    loadWatchlist()
    loadCatalog()
  }, [])

  // Refresh catalogs/watchlist options
  useEffect(() => {
    const catalogSymbols = catalog.map((r) => r.symbol)
    const symbols = [...new Set([...watchlist, ...catalogSymbols])].sort()
    setSymbolOptions(symbols)
    if (symbols.length && !priceSymbol) {
      setPriceSymbol(symbols[0])
    }
  }, [watchlist, catalog])

  // Save Settings
  const handlePollIntervalChange = async (e) => {
    const v = parseInt(e.target.value, 10)
    setPollInterval(v)
    if (v < 10) {
      showToast('Poll interval must be at least 10')
      return
    }
    try {
      await api('/settings', {
        method: 'PATCH',
        body: JSON.stringify({ poll_interval_sec: v }),
      })
    } catch (e) {
      showToast(e.message)
    }
  }

  const handleDefaultProviderChange = async (e) => {
    const v = e.target.value
    setDefaultProvider(v)
    try {
      await api('/settings', {
        method: 'PATCH',
        body: JSON.stringify({ default_provider: v }),
      })
    } catch (e) {
      showToast(e.message)
    }
  }

  // Watchlist Actions
  const handleAddTickers = async () => {
    const raw = addTickersInput.trim()
    if (!raw) return
    const tickers = raw
      .split(/[,\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean)
    try {
      await api('/watchlist/tickers', {
        method: 'POST',
        body: JSON.stringify({ tickers }),
      })
      setAddTickersInput('')
      await loadWatchlist()
      await loadHealth()
    } catch (e) {
      showToast(e.message)
    }
  }

  const handleRemoveTicker = async (ticker) => {
    try {
      await api(`/watchlist/tickers/${encodeURIComponent(ticker)}`, {
        method: 'DELETE',
      })
      await loadWatchlist()
      await loadHealth()
    } catch (e) {
      showToast(e.message)
    }
  }

  // Ingest & Backfill Actions
  const handleIngest = async () => {
    setActionStatus('Ingesting…')
    try {
      const data = await api('/ingest/trigger', { method: 'POST' })
      const s = data.summary
      setActionStatus(`Added ${s.bars_added} bars · polled ${s.symbols_polled} symbols`)
      await loadHealth()
      await loadCatalog()
    } catch (e) {
      setActionStatus('')
      showToast(e.message)
    }
  }

  const handleBackfill = async () => {
    setActionStatus('Backfilling…')
    try {
      const data = await api('/backfill/trigger', { method: 'POST' })
      const s = data.summary
      setActionStatus(`Years OK: ${s.years_ok} · failed: ${s.years_failed} · rows: ${s.total_rows}`)
      await loadHealth()
      await loadCatalog()
    } catch (e) {
      setActionStatus('')
      showToast(e.message)
    }
  }

  // Load candles for chart and table
  const handleLoadCandles = async () => {
    if (!priceSymbol) {
      showToast('Select a symbol')
      return
    }
    try {
      let url = `/candles/${encodeURIComponent(
        priceSymbol
      )}?interval=${priceInterval}&days=${priceDays}&limit=5000`
      if (priceProvider) {
        url += `&provider=${encodeURIComponent(priceProvider)}`
      }
      const data = await api(url)
      const rows = data.data || []
      setCandles(rows)
      if (!data.count) {
        setPriceSummary('0 bars — no data in range. Run backfill or increase days.')
      } else {
        const first = rows[0]
        const last = rows[rows.length - 1]
        setPriceSummary(`${data.count} bars · ${fmtTs(first.bar_ts)} → ${fmtTs(last.bar_ts)}`)
      }
    } catch (e) {
      showToast(e.message)
    }
  }

  const handleCatalogSymbolClick = (symbol) => {
    setPriceSymbol(symbol)
    setActiveTab('prices')
  }

  // Sparkline rendering
  useEffect(() => {
    if (!sparklineRef.current || !candles.length) return
    if (priceView !== 'all' && priceView !== 'table') return

    const canvas = sparklineRef.current
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, w, h)

    const closes = candles.map((r) => Number(r.close))
    const min = Math.min(...closes)
    const max = Math.max(...closes)
    const pad = 8
    ctx.strokeStyle = '#2563eb'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    candles.forEach((r, i) => {
      const x = pad + (i / Math.max(1, candles.length - 1)) * (w - pad * 2)
      const y = h - pad - ((Number(r.close) - min) / Math.max(1e-9, max - min)) * (h - pad * 2)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
  }, [candles, priceView])

  // TradingView Chart rendering
  useEffect(() => {
    if (!chartContainerRef.current || !candles.length) return
    if (priceView !== 'all' && priceView !== 'chart') return

    const container = chartContainerRef.current
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: { background: { color: '#fff' }, textColor: '#333' },
      grid: { vertLines: { color: '#eee' }, horzLines: { color: '#eee' } },
    })
    const candleSeries = chart.addCandlestickSeries()

    // Chronological order is required for lightweight-charts
    const chartData = [...candles]
      .sort((a, b) => a.bar_ts - b.bar_ts)
      .map((r) => ({
        time: r.bar_ts,
        open: Number(r.open),
        high: Number(r.high),
        low: Number(r.low),
        close: Number(r.close),
      }))

    candleSeries.setData(chartData)
    chart.timeScale().fitContent()

    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [candles, priceView])

  // Auto load candles when symbol options are populated
  useEffect(() => {
    if (priceSymbol && activeTab === 'prices') {
      handleLoadCandles()
    }
  }, [priceSymbol, activeTab])

  return (
    <div className="wrap">
      <header>
        <h1>vinu-stock-price</h1>
        <span className={healthClass}>{healthStatus}</span>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button
          type="button"
          className={activeTab === 'coverage' ? 'active' : ''}
          onClick={() => {
            setActiveTab('coverage')
            loadCatalog()
          }}
        >
          Coverage
        </button>
        <button
          type="button"
          className={activeTab === 'prices' ? 'active' : ''}
          onClick={() => setActiveTab('prices')}
        >
          Prices
        </button>
      </nav>

      {/* Settings Panel */}
      {activeTab === 'settings' && (
        <section className="panel active">
          <div className="card">
            <label htmlFor="poll-interval">Poll interval (seconds, min 10)</label>
            <input
              type="number"
              id="poll-interval"
              min="10"
              value={pollInterval}
              onChange={handlePollIntervalChange}
            />
            <p className="status-msg">Applies after the current ingest sleep cycle ends.</p>

            <label htmlFor="default-provider">Default provider</label>
            <select
              id="default-provider"
              value={defaultProvider}
              onChange={handleDefaultProviderChange}
            >
              <option value="polygon">polygon</option>
              <option value="alpaca">alpaca</option>
              <option value="yahoo">yahoo</option>
            </select>

            <label>Data root</label>
            <div className="readonly">{dataRoot}</div>

            <label>Provider keys</label>
            <div className="badges">
              {health &&
                (health.providers || []).map((p) => {
                  const cls = p.configured ? 'ok' : 'warn'
                  const label = p.configured ? 'configured' : 'not configured'
                  return (
                    <span key={p.id} className={`badge ${cls}`}>
                      {p.id} · {label} · p{p.priority}
                    </span>
                  )
                })}
            </div>
          </div>

          <div className="card">
            <label>Watchlist</label>
            <div className="row">
              <input
                type="text"
                placeholder="AAPL, NVDA"
                value={addTickersInput}
                onChange={(e) => setAddTickersInput(e.target.value)}
              />
              <button type="button" className="btn" onClick={handleAddTickers}>
                Add
              </button>
            </div>
            <ul className="ticker-list">
              {watchlist.length === 0 ? (
                <li className="empty">No tickers yet.</li>
              ) : (
                watchlist.map((t) => (
                  <li key={t}>
                    <span>{t}</span>
                    <button
                      type="button"
                      className="btn danger"
                      onClick={() => handleRemoveTicker(t)}
                    >
                      remove
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div className="card">
            <button type="button" className="btn" onClick={handleIngest}>
              Ingest now
            </button>
            <button
              type="button"
              className="btn secondary"
              style={{ marginLeft: '0.5rem' }}
              onClick={handleBackfill}
            >
              Backfill watchlist
            </button>
            {actionStatus && <p className="status-msg">{actionStatus}</p>}
          </div>
        </section>
      )}

      {/* Coverage Panel */}
      {activeTab === 'coverage' && (
        <section className="panel active">
          <div className="card">
            <div className="row">
              <button type="button" className="btn secondary" onClick={loadCatalog}>
                Refresh
              </button>
            </div>
            {catalog.length === 0 ? (
              <p className="empty">
                No symbols in catalog — add watchlist tickers and run backfill.
              </p>
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Provider</th>
                    <th>First</th>
                    <th>Last</th>
                    <th>Archive</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.map((r) => (
                    <tr key={r.symbol} className={getRowClass(r)}>
                      <td>
                        <span
                          className="symbol-link"
                          onClick={() => handleCatalogSymbolClick(r.symbol)}
                        >
                          {r.symbol}
                        </span>
                      </td>
                      <td>{r.provider || ''}</td>
                      <td>{fmtTs(r.first_bar_ts)}</td>
                      <td>{fmtTs(r.last_bar_ts)}</td>
                      <td>{r.archive_through || '—'}</td>
                      <td>{r.backfill_status || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* Prices Panel */}
      {activeTab === 'prices' && (
        <section className="panel active">
          <div className="card">
            <div className="row">
              <div>
                <label htmlFor="price-symbol">Symbol</label>
                <select
                  id="price-symbol"
                  value={priceSymbol}
                  onChange={(e) => setPriceSymbol(e.target.value)}
                >
                  {symbolOptions.length === 0 ? (
                    <option value="">—</option>
                  ) : (
                    symbolOptions.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div>
                <label htmlFor="price-interval">Interval</label>
                <select
                  id="price-interval"
                  value={priceInterval}
                  onChange={(e) => setPriceInterval(e.target.value)}
                >
                  <option value="1m">1m</option>
                  <option value="5m">5m</option>
                  <option value="15m">15m</option>
                  <option value="30m">30m</option>
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                  <option value="1d">1d</option>
                </select>
              </div>
              <div>
                <label htmlFor="price-days">Days</label>
                <select
                  id="price-days"
                  value={priceDays}
                  onChange={(e) => setPriceDays(e.target.value)}
                >
                  <option value="1">1</option>
                  <option value="7">7</option>
                  <option value="30">30</option>
                </select>
              </div>
              <div>
                <label htmlFor="price-provider">Provider</label>
                <select
                  id="price-provider"
                  value={priceProvider}
                  onChange={(e) => setPriceProvider(e.target.value)}
                >
                  <option value="">all</option>
                  <option value="polygon">polygon</option>
                  <option value="alpaca">alpaca</option>
                  <option value="yahoo">yahoo</option>
                </select>
              </div>
            </div>
            <button type="button" className="btn" onClick={handleLoadCandles}>
              Load
            </button>
            {priceSummary && <p className="status-msg">{priceSummary}</p>}

            <div className="view-toggle" style={{ marginTop: '1rem' }}>
              <button
                type="button"
                className={`btn secondary ${priceView === 'all' ? 'active' : ''}`}
                onClick={() => setPriceView('all')}
              >
                All
              </button>
              <button
                type={`button`}
                className={`btn secondary ${priceView === 'table' ? 'active' : ''}`}
                onClick={() => setPriceView('table')}
              >
                Table
              </button>
              <button
                type="button"
                className={`btn secondary ${priceView === 'chart' ? 'active' : ''}`}
                onClick={() => setPriceView('chart')}
              >
                Chart
              </button>
            </div>

            {/* Sparkline Canvas */}
            {(priceView === 'all' || priceView === 'table') && (
              <canvas id="sparkline" ref={sparklineRef}></canvas>
            )}

            {/* Candlestick Table */}
            {(priceView === 'all' || priceView === 'table') && (
              <div className="table-wrap">
                {candles.length === 0 ? (
                  <p className="empty">No bars in range. Run backfill or increase days.</p>
                ) : (
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>O</th>
                        <th>H</th>
                        <th>L</th>
                        <th>C</th>
                        <th>Vol</th>
                        <th>Provider</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Show newest first in table */}
                      {[...candles]
                        .sort((a, b) => b.bar_ts - a.bar_ts)
                        .map((r) => (
                          <tr key={r.bar_ts}>
                            <td>{fmtTs(r.bar_ts)}</td>
                            <td>{Number(r.open).toFixed(2)}</td>
                            <td>{Number(r.high).toFixed(2)}</td>
                            <td>{Number(r.low).toFixed(2)}</td>
                            <td>{Number(r.close).toFixed(2)}</td>
                            <td>{Number(r.volume)}</td>
                            <td>{r.provider || ''}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* TradingView Candlestick Chart */}
            {(priceView === 'all' || priceView === 'chart') && (
              <div id="chart" ref={chartContainerRef}></div>
            )}
          </div>
        </section>
      )}

      {toast && <div className="toast show">{toast}</div>}
    </div>
  )
}

export default App
