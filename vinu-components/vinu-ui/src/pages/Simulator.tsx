import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { EChart } from '../components/charts'

// Simulator lab: config → user-fired run → run card (equity/weights/trades/metrics) + compare.
export default function Simulator() {
  const [strategy, setStrategy] = useState('momentum')
  const [capital, setCapital] = useState(100000)
  const [costBps, setCostBps] = useState(5)
  const [runId, setRunId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const runs = useQuery({ queryKey: ['sim-runs'], queryFn: api.simRuns, refetchInterval: 30_000 })
  const equity = useQuery({ queryKey: ['sim-equity', runId], queryFn: () => api.simEquity(runId!), enabled: !!runId })
  const metrics = useQuery({ queryKey: ['sim-metrics', runId], queryFn: () => api.simMetrics(runId!), enabled: !!runId })

  const run = async () => {
    setRunning(true)
    const res: any = await api.simulate({ strategy, capital, cost_bps: costBps })
    setRunning(false)
    if (res?.run_id) setRunId(res.run_id)
  }

  const eq: any[] = (equity.data as any)?.equity ?? (equity.data as any) ?? []

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h2 className="font-bold text-sm mb-3">Simulator lab <span className="text-xs font-normal text-faint">{runs.data ? '● engine reachable' : '○ unreachable · config only'}</span></h2>
        <div className="grid md:grid-cols-4 gap-3 items-end">
          <label className="text-xs text-muted">Strategy
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="mt-1 w-full bg-base border border-edge rounded-lg p-2 text-ink">
              <option value="momentum">momentum</option>
              <option value="mean_reversion">mean_reversion</option>
              <option value="trend">trend</option>
            </select>
          </label>
          <label className="text-xs text-muted">Capital <span className="num">{capital.toLocaleString()}</span>
            <input type="range" min={10000} max={1000000} step={10000} value={capital} onChange={(e) => setCapital(+e.target.value)} className="w-full" />
          </label>
          <label className="text-xs text-muted">Costs <span className="num">{costBps} bps</span>
            <input type="range" min={0} max={50} value={costBps} onChange={(e) => setCostBps(+e.target.value)} className="w-full" />
          </label>
          <button onClick={run} disabled={running} className="chip justify-center !py-2 !bg-accent !border-accent text-white disabled:opacity-50">
            {running ? 'running…' : '▶ run simulation'}
          </button>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Run card {runId && <span className="num text-accent">{runId}</span>}</h2>
        {eq.length > 0 ? (
          <EChart height={260} option={{
            xAxis: { type: 'category', data: eq.map((_: any, i: number) => i) },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } },
            series: [{ type: 'line', showSymbol: false, data: eq.map((p: any) => p.equity ?? p.value ?? p), lineStyle: { color: '#2F81F7', width: 2 }, areaStyle: { color: 'rgba(47,129,247,.15)' } }],
          }} />
        ) : <p className="text-sm text-faint">No run selected. Firing a run calls <span className="num">POST /simulator/simulate</span> (compute only, no orders).</p>}
        {metrics.data && <pre className="mt-2 text-[11px] p-3 rounded-lg bg-base border border-edge overflow-auto" style={{ color: '#7dd3fc' }}>{JSON.stringify(metrics.data, null, 2)}</pre>}
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Runs <span className="text-xs font-normal text-faint">select → compare promotion candidate</span></h2>
        <pre className="text-[11px] p-3 rounded-lg bg-base border border-edge overflow-auto" style={{ color: '#7dd3fc' }}>{JSON.stringify(runs.data ?? 'unreachable', null, 2).slice(0, 2000)}</pre>
      </section>
    </div>
  )
}
