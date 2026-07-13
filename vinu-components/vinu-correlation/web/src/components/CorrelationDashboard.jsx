import { useState, useEffect } from 'react'
import { api } from '../api.js'

function corrColor(v) {
  if (v === 0 || v == null) return 'var(--text-dim)'
  const abs = Math.abs(v)
  if (v > 0) return abs > 0.5 ? 'var(--success)' : abs > 0.3 ? '#65a30d' : 'var(--text-muted)'
  return abs > 0.5 ? 'var(--danger)' : abs > 0.3 ? '#ea580c' : 'var(--text-muted)'
}

function deviationColor(level) {
  switch (level) {
    case 'critical': return 'var(--danger)'
    case 'high': return '#ea580c'
    case 'elevated': return 'var(--warning)'
    default: return 'var(--success)'
  }
}

function impactBadge(label) {
  if (!label) return { cls: 'badge-gray', text: 'unknown' }
  if (label === 'high_bearish') return { cls: 'badge-red', text: 'High Bearish' }
  if (label === 'high_bullish') return { cls: 'badge-green', text: 'High Bullish' }
  if (label === 'medium') return { cls: 'badge-yellow', text: 'Medium' }
  return { cls: 'badge-gray', text: 'Low' }
}

function CorrBar({ label, value, ciLower, ciUpper, pValue }) {
  const pct = value == null ? 50 : ((value + 1) / 2) * 100
  const fillColor = corrColor(value)
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
        <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 700, color: fillColor }}>{value != null ? value.toFixed(4) : '—'}</span>
      </div>
      <div style={{ position: 'relative', height: '10px', background: 'rgba(255,255,255,0.04)', borderRadius: '999px', overflow: 'visible' }}>
        <div style={{
          position: 'absolute', left: '0', right: '0', top: '0', bottom: '0',
          background: 'linear-gradient(to right, var(--danger), rgba(255,255,255,0.05), var(--success))',
          borderRadius: '999px', opacity: 0.15,
        }} />
        <div style={{
          position: 'absolute', left: `${pct}%`, top: '-3px', width: '16px', height: '16px',
          borderRadius: '50%', background: fillColor, transform: 'translateX(-50%)',
          boxShadow: `0 0 8px ${fillColor}44`,
          transition: 'left 0.5s ease',
        }} />
        {ciLower != null && ciUpper != null && (
          <div style={{
            position: 'absolute', left: `${((ciLower + 1) / 2) * 100}%`,
            right: `${100 - ((ciUpper + 1) / 2) * 100}%`,
            top: '14px', height: '3px', background: fillColor, opacity: 0.3,
            borderRadius: '999px',
          }} />
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '0.25rem' }}>
        <span>-1.0</span>
        {ciLower != null && <span>95% CI [{ciLower.toFixed(2)}, {ciUpper.toFixed(2)}]</span>}
        <span>+1.0</span>
      </div>
      {pValue != null && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.15rem' }}>
          p = {pValue.toFixed(6)} {pValue < 0.05 && <span style={{ color: 'var(--success)' }}>✓ significant</span>}
        </div>
      )}
    </div>
  )
}

function LagChart({ lagResults, bestLag }) {
  const entries = Object.entries(lagResults || {})
  if (entries.length === 0) return <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem', fontStyle: 'italic' }}>No lag data</p>
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01)
  return (
    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', height: '100px', padding: '0.5rem 0' }}>
      {entries.map(([lag, corr]) => {
        const barH = (Math.abs(corr) / maxAbs) * 80
        const isBest = bestLag != null && parseInt(lag) === bestLag
        return (
          <div key={lag} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.3rem' }}>
            <span style={{ fontSize: '0.67rem', fontWeight: 700, color: corrColor(corr) }}>{corr.toFixed(2)}</span>
            <div style={{
              width: '100%', maxWidth: '40px', height: `${Math.max(barH, 4)}px`,
              background: corrColor(corr), borderRadius: '4px 4px 0 0',
              opacity: isBest ? 1 : 0.5, transition: 'height 0.3s ease',
            }} />
            <span style={{ fontSize: '0.65rem', color: isBest ? 'var(--primary)' : 'var(--text-dim)', fontWeight: isBest ? 700 : 500 }}>
              {lag}{isBest && ' ✓'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function AttributionBar({ newsPct, marketPct, unexplainedPct }) {
  return (
    <div style={{ display: 'flex', height: '24px', borderRadius: '6px', overflow: 'hidden', margin: '0.5rem 0', fontSize: '0.68rem', fontWeight: 600 }}>
      {newsPct > 0 && (
        <div style={{ flex: newsPct, background: 'var(--warning)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#000' }}>
          {(newsPct * 100).toFixed(0)}% news
        </div>
      )}
      {marketPct > 0 && (
        <div style={{ flex: marketPct, background: 'var(--info)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
          {(marketPct * 100).toFixed(0)}% market
        </div>
      )}
      {unexplainedPct > 0 && (
        <div style={{ flex: unexplainedPct, background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>
          {(unexplainedPct * 100).toFixed(0)}% other
        </div>
      )}
    </div>
  )
}

function formatTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function CorrelationDashboard({ ticker }) {
  const [correlation, setCorrelation] = useState(null)
  const [impact, setImpact] = useState(null)
  const [drawdown, setDrawdown] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [section, setSection] = useState('correlation')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      api(`/correlation/${ticker}`).catch(() => null),
      api(`/impact/${ticker}`).catch(() => null),
      api(`/drawdown/${ticker}`).catch(() => null),
      api(`/baseline/${ticker}`).catch(() => null),
    ]).then(([c, i, d, b]) => {
      if (cancelled) return
      setCorrelation(c)
      setImpact(i)
      setDrawdown(d)
      setBaseline(b)
    }).catch(e => {
      if (!cancelled) setError(e.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => { cancelled = true }
  }, [ticker])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem' }}>
        <div className="animate-spin" style={{ width: '24px', height: '24px', border: '2px solid var(--border-color)', borderTopColor: 'var(--primary)', borderRadius: '50%', marginRight: '0.75rem' }} />
        <span style={{ color: 'var(--text-dim)' }}>Loading {ticker}...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', borderColor: 'rgba(239,68,68,0.2)' }}>
        <span style={{ color: 'var(--danger)', fontSize: '1.1rem', fontWeight: 700 }}>Failed to load {ticker}</span>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem', marginTop: '0.5rem' }}>{error}</p>
      </div>
    )
  }

  const sessions = baseline?.sessions || {}
  const events = impact?.events || []
  const eventSummary = {
    bearish: impact?.high_impact_bearish_events || 0,
    bullish: impact?.high_impact_bullish_events || 0,
    total: impact?.event_count || 0,
    avgDrop: impact?.avg_price_drop_30m || 0,
  }
  const drawdowns = drawdown?.drawdowns || []

  const isGranger = correlation?.granger_causes_prices
  const grangerBadge = isGranger == null ? { cls: 'badge-gray', text: '—' }
    : isGranger ? { cls: 'badge-green', text: 'Causal' }
    : { cls: 'badge-gray', text: 'Not causal' }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, letterSpacing: '-0.025em', fontFamily: 'var(--font-mono)' }}>{ticker}</h1>
        {correlation?.sample_size != null && (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>sample: {correlation.sample_size} hours</span>
        )}
      </div>

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
        <div className="stat-card">
          <span className="stat-value" style={{ color: corrColor(correlation?.news_return_corr) }}>
            {correlation?.news_return_corr != null ? correlation.news_return_corr.toFixed(3) : '—'}
          </span>
          <span className="stat-label">News ↔ Return</span>
        </div>
        <div className="stat-card">
          <span className={`badge ${grangerBadge.cls}`} style={{ fontSize: '0.85rem', display: 'inline-flex' }}>{grangerBadge.text}</span>
          <span className="stat-label" style={{ marginTop: '0.5rem' }}>
            Granger {isGranger ? `(lag ${correlation?.best_lag_minutes}m, p=${correlation?.granger_p_value?.toFixed(4)})` : ''}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-value" style={{ fontSize: '1.4rem' }}>
            {eventSummary.bearish > 0 && <span style={{ color: 'var(--danger)' }}>{eventSummary.bearish}↓ </span>}
            {eventSummary.bullish > 0 && <span style={{ color: 'var(--success)' }}>{eventSummary.bullish}↑</span>}
            {eventSummary.bearish === 0 && eventSummary.bullish === 0 && <span style={{ color: 'var(--text-dim)' }}>0</span>}
          </span>
          <span className="stat-label">High-Impact Events</span>
        </div>
        <div className="stat-card">
          <span className="stat-value" style={{ color: drawdowns.length > 0 ? 'var(--danger)' : 'var(--text-dim)' }}>
            {drawdowns.length}
          </span>
          <span className="stat-label">Drawdowns</span>
        </div>
      </div>

      {/* Section Nav */}
      <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1px' }}>
        {[
          { key: 'correlation', label: 'Correlation Proof' },
          { key: 'events', label: `Events (${events.length})` },
          { key: 'drawdowns', label: `Drawdowns (${drawdowns.length})` },
          { key: 'baseline', label: 'News Baseline' },
        ].map(s => (
          <button key={s.key} type="button" onClick={() => setSection(s.key)}
            className={`btn-secondary${section === s.key ? ' active' : ''}`}
            style={{ padding: '0.5rem 0.9rem', fontSize: '0.82rem', borderBottom: section === s.key ? '2px solid var(--primary)' : '2px solid transparent', borderRadius: '8px 8px 0 0' }}>
            {s.label}
          </button>
        ))}
      </div>

      {/* Correlation Proof Section */}
      {section === 'correlation' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-card">
            <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 1rem 0' }}>Pearson Correlation</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
              <div>
                <CorrBar
                  label="News Article Count vs Price Return"
                  value={correlation?.news_return_corr}
                  ciLower={correlation?.corr_ci_lower}
                  ciUpper={correlation?.corr_ci_upper}
                  pValue={correlation?.corr_p_value}
                />
                <CorrBar
                  label="Avg Sentiment vs Price Return"
                  value={correlation?.sentiment_return_corr}
                />
                <CorrBar
                  label="News Volume vs |Price Return|"
                  value={correlation?.news_volume_corr}
                />
              </div>
              <div>
                <div className="glass-card" style={{ border: 'none', background: 'rgba(255,255,255,0.02)', padding: '1rem' }}>
                  <h3 style={{ fontSize: '0.85rem', fontWeight: 600, margin: '0 0 0.75rem 0', color: 'var(--text-muted)' }}>Granger Causality</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className={`badge ${grangerBadge.cls}`} style={{ fontSize: '0.85rem' }}>{grangerBadge.text}</span>
                    {isGranger != null && (
                      <span style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                        {isGranger
                          ? `News volume Granger-causes price returns (p=${correlation.granger_p_value.toFixed(4)}, best lag=${correlation.best_lag_minutes}m)`
                          : `News volume does NOT Granger-cause price returns (p=${correlation.granger_p_value.toFixed(4)})`
                        }
                      </span>
                    )}
                  </div>
                </div>

                <div className="glass-card" style={{ border: 'none', background: 'rgba(255,255,255,0.02)', padding: '1rem', marginTop: '1rem' }}>
                  <h3 style={{ fontSize: '0.85rem', fontWeight: 600, margin: '0 0 0.75rem 0', color: 'var(--text-muted)' }}>Lag Analysis</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: '0 0 0.5rem 0' }}>
                    Best lag: <strong style={{ color: 'var(--primary)' }}>{correlation?.best_lag_minutes ?? '—'} min</strong> (corr: {correlation?.best_lag_correlation?.toFixed(4) ?? '—'})
                  </p>
                  <LagChart lagResults={correlation?.lag_results} bestLag={correlation?.best_lag_minutes} />
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card">
            <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>Interpretation</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '0.75rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              <div>
                <strong style={{ color: 'var(--text-main)' }}>News Intensity</strong>
                <br />{correlation?.news_return_corr != null
                  ? Math.abs(correlation.news_return_corr) < 0.1 ? 'Negligible linear relationship between news volume and price returns.'
                  : Math.abs(correlation.news_return_corr) < 0.3 ? 'Weak relationship — news volume has a mild association with price direction.'
                  : Math.abs(correlation.news_return_corr) < 0.5 ? 'Moderate relationship — news volume and price returns move together.'
                  : 'Strong relationship — news volume is a meaningful indicator of return direction.'
                  : 'Insufficient data for interpretation.'}
              </div>
              <div>
                <strong style={{ color: 'var(--text-main)' }}>Sentiment</strong>
                <br />{correlation?.sentiment_return_corr != null
                  ? Math.abs(correlation.sentiment_return_corr) < 0.1 ? 'Sentiment scores show no linear correlation with returns.'
                  : correlation.sentiment_return_corr > 0 ? 'Positive sentiment tends to align with positive returns.'
                  : 'Negative sentiment tends to align with negative returns.'
                  : 'Insufficient data.'}
              </div>
              <div>
                <strong style={{ color: 'var(--text-main)' }}>Causality</strong>
                <br />{isGranger == null ? 'Insufficient data for Granger test.'
                  : isGranger ? `News volume has statistical predictive power over price returns at a ${correlation.best_lag_minutes}-minute lag (p<0.05).`
                  : 'News volume does not statistically predict price returns at any tested lag.'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Events Section */}
      {section === 'events' && (
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Impact Events</h2>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.78rem' }}>
              <span style={{ color: 'var(--danger)' }}>● {eventSummary.bearish} bearish</span>
              <span style={{ color: 'var(--success)' }}>● {eventSummary.bullish} bullish</span>
              <span style={{ color: 'var(--text-dim)' }}>| avg drop: {eventSummary.avgDrop}%</span>
            </div>
          </div>

          {events.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No impact events found for {ticker}.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', minWidth: '800px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-dim)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Time</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Headline</th>
                    <th style={{ padding: '0.4rem', textAlign: 'center' }}>Sentiment</th>
                    <th style={{ padding: '0.4rem', textAlign: 'center' }}>Impact</th>
                    <th style={{ padding: '0.4rem', textAlign: 'right' }}>Δ5m</th>
                    <th style={{ padding: '0.4rem', textAlign: 'right' }}>Δ15m</th>
                    <th style={{ padding: '0.4rem', textAlign: 'right' }}>Δ30m</th>
                    <th style={{ padding: '0.4rem', textAlign: 'right' }}>Δ1h</th>
                    <th style={{ padding: '0.4rem', textAlign: 'right' }}>AR 30m</th>
                    <th style={{ padding: '0.4rem', textAlign: 'center' }}>Sig.</th>
                  </tr>
                </thead>
                <tbody>
                  {events.slice(0, 50).map((e, i) => {
                    const ib = impactBadge(e.impact_label)
                    return (
                      <tr key={e.article_id || i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <td style={{ padding: '0.4rem', whiteSpace: 'nowrap', color: 'var(--text-dim)', fontSize: '0.75rem' }}>{formatTs(e.ts)}</td>
                        <td style={{ padding: '0.4rem', fontWeight: 600, maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {e.headline || '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'center', fontSize: '0.75rem', color: e.sentiment === 'BULLISH' ? 'var(--success)' : e.sentiment === 'BEARISH' ? 'var(--danger)' : 'var(--text-dim)' }}>
                          {e.sentiment || '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                          <span className={`badge ${ib.cls}`}>{ib.text}</span>
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'right', color: (e.price_change_5m || 0) < 0 ? 'var(--danger)' : 'var(--success)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {e.price_change_5m != null ? `${e.price_change_5m > 0 ? '+' : ''}${e.price_change_5m.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'right', color: (e.price_change_15m || 0) < 0 ? 'var(--danger)' : 'var(--success)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {e.price_change_15m != null ? `${e.price_change_15m > 0 ? '+' : ''}${e.price_change_15m.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'right', color: (e.price_change_30m || 0) < 0 ? 'var(--danger)' : 'var(--success)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {e.price_change_30m != null ? `${e.price_change_30m > 0 ? '+' : ''}${e.price_change_30m.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'right', color: (e.price_change_1h || 0) < 0 ? 'var(--danger)' : 'var(--success)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {e.price_change_1h != null ? `${e.price_change_1h > 0 ? '+' : ''}${e.price_change_1h.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'right', color: (e.abnormal_return_30m || 0) < 0 ? 'var(--danger)' : 'var(--success)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {e.abnormal_return_30m != null ? `${e.abnormal_return_30m > 0 ? '+' : ''}${(e.abnormal_return_30m * 100).toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                          {e.ar_significant ? (
                            <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>✓</span>
                          ) : e.ar_p_value != null && e.ar_p_value < 0.1 ? (
                            <span className="badge badge-yellow" style={{ fontSize: '0.65rem' }}>~</span>
                          ) : (
                            <span className="badge badge-gray" style={{ fontSize: '0.65rem' }}>—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Drawdowns Section */}
      {section === 'drawdowns' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {drawdowns.length === 0 ? (
            <div className="glass-card">
              <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', margin: 0 }}>No significant drawdowns detected for {ticker}.</p>
            </div>
          ) : (
            drawdowns.map((dd, i) => {
              const attr = dd.attribution || {}
              return (
                <div key={i} className="glass-card" style={{ borderColor: 'rgba(239,68,68,0.15)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                    <div>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}>
                        Drawdown #{i + 1}
                      </h3>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {formatTs(dd.peak_ts)} → {formatTs(dd.trough_ts)}
                      </div>
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--danger)' }}>
                      {dd.drop_pct?.toFixed(1)}%
                    </div>
                  </div>

                  {attr.news_driven_pct != null && (
                    <>
                      <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.78rem', color: 'var(--text-dim)', marginBottom: '0.25rem' }}>
                        <span>News-driven: <strong style={{ color: 'var(--warning)' }}>{(attr.news_driven_pct * 100).toFixed(0)}%</strong></span>
                        <span>Market beta: <strong style={{ color: 'var(--info)' }}>{(attr.market_beta_pct * 100).toFixed(0)}%</strong></span>
                        <span>Unexplained: <strong>{(attr.unexplained_pct * 100).toFixed(0)}%</strong></span>
                      </div>
                      <AttributionBar
                        newsPct={attr.news_driven_pct}
                        marketPct={attr.market_beta_pct}
                        unexplainedPct={attr.unexplained_pct}
                      />
                    </>
                  )}

                  {(attr.contributing_events || []).length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Contributing Events</div>
                      {attr.contributing_events.slice(0, 5).map((ev, j) => (
                        <div key={j} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', padding: '0.2rem 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.headline || '—'}</span>
                          <span style={{ color: 'var(--text-dim)', marginLeft: '0.5rem', whiteSpace: 'nowrap' }}>
                            {(ev.attribution_pct * 100).toFixed(1)}% | {ev.impact_label || '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Baseline Section */}
      {section === 'baseline' && (
        <div className="glass-card">
          <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>News Volume Baseline</h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', margin: '0 0 1rem 0' }}>
            Average daily articles: <strong style={{ color: 'var(--text-main)' }}>{baseline?.mean_daily_articles ?? '—'}</strong>
          </p>

          {Object.keys(sessions).length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No baseline data for {ticker}.</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
              {Object.entries(sessions).map(([sessionName, data]) => {
                const devColor = deviationColor(data.deviation_level)
                return (
                  <div key={sessionName} className="glass-card" style={{ border: 'none', background: 'rgba(255,255,255,0.02)', textAlign: 'center', padding: '1rem' }}>
                    <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
                      {sessionName.replace('_', ' ')}
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 800, color: devColor }}>
                      {data.z_score?.toFixed(1)}
                    </div>
                    <span className={`badge`} style={{ background: `${devColor}22`, color: devColor, borderColor: `${devColor}44`, fontSize: '0.72rem', marginTop: '0.25rem' }}>
                      {data.deviation_level || 'normal'}
                    </span>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '0.75rem', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                      <span>μ <strong>{data.mean?.toFixed(1) || '—'}</strong></span>
                      <span>σ <strong>{data.stddev?.toFixed(1) || '—'}</strong></span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
