import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { EChart } from '../components/charts'

// Portfolio / Screener / Research — one component each, same shell language.
export default function More({ section }: { section: 'portfolio' | 'screener' | 'research' }) {
  const weights = useQuery({ queryKey: ['pf-weights'], queryFn: api.pfWeights, enabled: section === 'portfolio', refetchInterval: 60_000 })
  const pfState = useQuery({ queryKey: ['pf-state'], queryFn: api.pfState, enabled: section === 'portfolio', refetchInterval: 60_000 })
  const rules = useQuery({ queryKey: ['rules'], queryFn: api.rules, enabled: section === 'screener', refetchInterval: 30_000 })
  const rankers = useQuery({ queryKey: ['rankers'], queryFn: api.rankers, enabled: section === 'screener', refetchInterval: 60_000 })
  const artifacts = useQuery({ queryKey: ['artifacts'], queryFn: () => api.artifacts(), enabled: section === 'research', refetchInterval: 30_000 })

  if (section === 'portfolio') {
    const w: any = weights.data
    const names: string[] = w?.weights ? Object.keys(w.weights) : ['AAPL', 'MSFT', 'TSLA']
    const vals: number[] = w?.weights ? Object.values(w.weights).map(Number) : [8.2, 6.1, 3.1]
    return (
      <div className="space-y-4">
        <section className="card p-4">
          <h2 className="font-bold text-sm mb-2">Portfolio · correlation-aware allocation <span className="text-xs font-normal text-faint">{weights.data ? '● live' : '○ mock'}</span></h2>
          <EChart height={240} option={{
            xAxis: { type: 'category', data: names },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } },
            series: [{ type: 'bar', data: vals, itemStyle: { color: '#2F81F7' } }],
          }} />
        </section>
        <section className="card p-4"><h2 className="font-bold text-sm mb-2">State</h2>
          <pre className="text-[11px] p-3 rounded-lg bg-base border border-edge overflow-auto" style={{ color: '#7dd3fc' }}>{JSON.stringify(pfState.data ?? 'unreachable', null, 2).slice(0, 2000)}</pre>
        </section>
      </div>
    )
  }

  if (section === 'screener') {
    const rl: any[] = (rules.data as any)?.rules ?? (Array.isArray(rules.data) ? rules.data : [])
    const rk: any[] = (rankers.data as any)?.rankers ?? (Array.isArray(rankers.data) ? rankers.data : [])
    return (
      <div className="space-y-4">
        <section className="card p-4">
          <h2 className="font-bold text-sm mb-2">Screener · rules (30s) + rankers (24h) <span className="text-xs font-normal text-faint">{rules.data ? '● live' : '○ unreachable'}</span></h2>
          {rl.length ? rl.map((r: any, i: number) => (
            <div key={i} className="rounded-lg bg-base border border-edge p-2 mb-1 text-[13px] flex justify-between">
              <span className="num text-accent">{r.name ?? r.rule_id ?? `rule-${i}`}</span>
              <span className="chip">{r.enabled === false ? 'disabled' : 'active'}</span>
            </div>
          )) : <p className="text-sm text-faint">No rules reported.</p>}
        </section>
        <section className="card p-4"><h2 className="font-bold text-sm mb-2">Rankers</h2>
          {rk.length ? rk.map((r: any, i: number) => <RankerRow key={i} id={r.ranker_id ?? r.id ?? r} />) : <p className="text-sm text-faint">No rankers reported.</p>}
        </section>
      </div>
    )
  }

  const arts: any[] = Array.isArray(artifacts.data) ? artifacts.data : []
  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Research · artifacts <span className="text-xs font-normal text-faint">{artifacts.data ? `● ${arts.length} live` : '○ unreachable'}</span></h2>
        {arts.length ? (
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-faint text-[11px] uppercase"><th>ID</th><th>Type</th><th>Status</th><th>Symbol</th></tr></thead>
            <tbody>{arts.slice(0, 50).map((a: any, i: number) => (
              <tr key={i} className="border-t border-edge"><td className="num">{a.artifact_id ?? a.id}</td><td>{a.type_ ?? a.type}</td><td><span className="chip num">{a.status}</span></td><td className="num text-accent">{a.symbol}</td></tr>
            ))}</tbody>
          </table>
        ) : <p className="text-sm text-faint">No artifacts reported.</p>}
      </section>
    </div>
  )
}

function RankerRow({ id }: { id: string }) {
  const latest = useQuery({ queryKey: ['rank-latest', id], queryFn: () => api.rankLatest(id), enabled: false })
  return (
    <div className="rounded-lg bg-base border border-edge p-2 mb-1 text-[13px]">
      <button onClick={() => latest.refetch()} className="text-accent num">{id} → latest snapshot</button>
      {latest.data && <pre className="mt-1 text-[11px] text-faint overflow-auto max-h-40">{JSON.stringify(latest.data, null, 1).slice(0, 1200)}</pre>}
    </div>
  )
}
