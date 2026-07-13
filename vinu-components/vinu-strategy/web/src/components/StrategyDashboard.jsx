import { useState, useEffect } from 'react'
import { api, evaluateStrategy, fetchWeights } from '../api.js'

function formatTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleString()
}

function weightColor(w) {
  if (w > 0.15) return '#4ade80'
  if (w > 0.05) return '#86efac'
  if (w > 0) return '#bbf7d0'
  return '#64748b'
}

export default function StrategyDashboard({ strategy, ticker }) {
  const [section, setSection] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stratInfo, setStratInfo] = useState(null)
  const [evalResult, setEvalResult] = useState(null)
  const [weights, setWeights] = useState([])
  const [evalLoading, setEvalLoading] = useState(false)

  useEffect(() => {
    if (!strategy) return
    setLoading(true)
    setError(null)
    api(`/strategies/${strategy}`)
      .then(setStratInfo)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [strategy])

  useEffect(() => {
    if (!strategy) return
    fetchWeights(strategy, ticker)
      .then(setWeights)
      .catch(() => {})
  }, [strategy, ticker])

  const handleEvaluate = async () => {
    setEvalLoading(true)
    setEvalResult(null)
    try {
      const result = await evaluateStrategy(strategy, [ticker])
      setEvalResult(result)
      setWeights(prev => [...prev, ...result.weights.map(w => ({...w, date: result.timestamp}))])
    } catch (e) {
      setError(e.message)
    } finally {
      setEvalLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading strategy...</div>
  if (error) return <div className="error">{error}</div>

  return (
    <div className="animate-fade-in">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'1.25rem'}}>
        <div>
          <h2 style={{margin:0,fontSize:'1.25rem',fontWeight:600}}>{strategy}</h2>
          <p style={{margin:'0.2rem 0 0',color:'var(--text-dim)',fontSize:'0.82rem'}}>
            {stratInfo?.description || ''}
          </p>
        </div>
        <button className="btn-primary" onClick={handleEvaluate} disabled={evalLoading}>
          {evalLoading ? 'Evaluating...' : 'Evaluate Now'}
        </button>
      </div>

      {evalResult && (
        <div className="glass-card" style={{marginBottom:'1rem',padding:'0.75rem 1rem'}}>
          <div style={{display:'flex',gap:'2rem',fontSize:'0.82rem'}}>
            <div><strong>Run ID:</strong> {evalResult.run_id}</div>
            <div><strong>Time:</strong> {formatTs(evalResult.timestamp)}</div>
            <div><strong>Symbols:</strong> {evalResult.metadata?.symbol_count || 0}</div>
          </div>
        </div>
      )}

      <div style={{display:'flex',gap:'0.5rem',marginBottom:'1rem'}}>
        {['overview','pipeline','weights','runs'].map(s => (
          <button key={s} className={`btn-secondary${section === s ? ' active' : ''}`}
            onClick={() => setSection(s)}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {section === 'overview' && stratInfo && (
        <div className="glass-card">
          <h3 style={{margin:'0 0 0.75rem',fontSize:'0.95rem',fontWeight:600}}>Strategy Config</h3>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-value">{stratInfo.features_required?.length || 0}</div>
              <div className="stat-label">Features</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stratInfo.correlation_required?.length || 0}</div>
              <div className="stat-label">Correlation Signals</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stratInfo.schedule}</div>
              <div className="stat-label">Schedule</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{weights.length}</div>
              <div className="stat-label">Weight Records</div>
            </div>
          </div>
          {stratInfo.features_required?.length > 0 && (
            <div style={{marginTop:'0.75rem'}}>
              <strong style={{fontSize:'0.82rem'}}>Required Features:</strong>
              <div style={{display:'flex',gap:'0.4rem',flexWrap:'wrap',marginTop:'0.4rem'}}>
                {stratInfo.features_required.map(f => (
                  <span key={f} className="badge badge-feature">{f}</span>
                ))}
              </div>
            </div>
          )}
          {stratInfo.correlation_required?.length > 0 && (
            <div style={{marginTop:'0.5rem'}}>
              <strong style={{fontSize:'0.82rem'}}>Required Correlation:</strong>
              <div style={{display:'flex',gap:'0.4rem',flexWrap:'wrap',marginTop:'0.4rem'}}>
                {stratInfo.correlation_required.map(c => (
                  <span key={c} className="badge badge-correlation">{c}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {section === 'pipeline' && stratInfo && (
        <div className="glass-card">
          <h3 style={{margin:'0 0 0.75rem',fontSize:'0.95rem',fontWeight:600}}>S → A → T → R Pipeline</h3>
          <div style={{display:'flex',gap:'0.75rem',flexWrap:'wrap'}}>
            {['selection','allocation','timing','risk'].map(stage => (
              <div key={stage} className="pipeline-card">
                <div className="pipeline-stage-label">{stage.toUpperCase()}</div>
                <div className="pipeline-stage-value">{stratInfo.pipeline?.[stage] || 'none'}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === 'weights' && (
        <div className="glass-card">
          <h3 style={{margin:'0 0 0.75rem',fontSize:'0.95rem',fontWeight:600}}>
            Weights for {ticker}
          </h3>
          {weights.length === 0 ? (
            <p style={{color:'var(--text-dim)'}}>No weight data yet. Click "Evaluate Now".</p>
          ) : (
            <div style={{overflowX:'auto'}}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Symbol</th>
                    <th>Weight</th>
                    <th>Signal</th>
                    <th>Strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {weights.slice(-20).reverse().map((w, i) => (
                    <tr key={i}>
                      <td>{formatTs(w.date).slice(0, 19)}</td>
                      <td style={{fontWeight:600}}>{w.symbol}</td>
                      <td style={{color: weightColor(w.weight), fontWeight:600}}>
                        {(w.weight * 100).toFixed(1)}%
                      </td>
                      <td>{w.signal_value?.toFixed(4) || '—'}</td>
                      <td style={{fontSize:'0.78rem'}}>{w.strategy_name || strategy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {section === 'runs' && (
        <div className="glass-card">
          <h3 style={{margin:'0 0 0.75rem',fontSize:'0.95rem',fontWeight:600}}>Run History</h3>
          <RunHistory strategy={strategy} />
        </div>
      )}
    </div>
  )
}

function RunHistory({ strategy }) {
  const [runs, setRuns] = useState([])
  useEffect(() => {
    api(`/runs?strategy=${strategy}`).then(setRuns).catch(() => {})
  }, [strategy])

  if (!runs.length) return <p style={{color:'var(--text-dim)'}}>No runs yet.</p>

  return (
    <div style={{overflowX:'auto'}}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Symbol</th>
            <th>Timestamp</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r, i) => (
            <tr key={i}>
              <td style={{fontSize:'0.78rem',fontFamily:'var(--font-mono)'}}>{r.run_id}</td>
              <td>{r.symbol || '—'}</td>
              <td>{formatTs(r.timestamp)}</td>
              <td><span className={`badge badge-${r.status}`}>{r.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
