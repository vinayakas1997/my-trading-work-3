import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { EChart } from '../components/charts'

// Live loop: cycle steps, book, emergency state. POST triggers are
// user-initiated buttons only (never auto-fired).
export default function Live() {
  const status = useQuery({ queryKey: ['live-status'], queryFn: api.liveStatus, refetchInterval: 5_000 })
  const positions = useQuery({ queryKey: ['broker-positions'], queryFn: api.brokerPositions, refetchInterval: 5_000 })
  const account = useQuery({ queryKey: ['broker-account'], queryFn: api.brokerAccount, refetchInterval: 10_000 })
  const emergency = useQuery({ queryKey: ['emergency2'], queryFn: api.emergencyStatus, refetchInterval: 10_000 })

  const steps = ['fetch plans', 'prices', 'equity', 'broker-health', 'halt mirror', 'shock sort', 'enter / evaluate', 'reconcile', 'correlation trim', 'OOD']
  const pos: any[] = (positions.data as any)?.positions ?? (positions.data as any) ?? []

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Live · 5-minute cycle <span className="text-xs font-normal text-faint">{status.data ? '● orchestrator reachable' : '○ unreachable · mock'}</span></h2>
        <div className="flex flex-wrap items-center gap-1">
          {steps.map((s, i) => (
            <span key={s} className="flex items-center gap-1">
              <span className="chip flow-pulse" style={{ animationDelay: `${i * 0.15}s` }}>● {s}</span>
              {i < steps.length - 1 && <span className="text-faint">→</span>}
            </span>
          ))}
        </div>
        <div className="mt-3 grid md:grid-cols-3 gap-2 text-[13px]">
          <div className="rounded-xl bg-base border border-edge p-3">Equity <div className="num text-lg">{(account.data as any)?.equity ?? (account.data as any)?.portfolio_value ?? '—'}</div></div>
          <div className="rounded-xl bg-base border border-edge p-3">Emergency <div className="num text-lg">{JSON.stringify((emergency.data as any)?.halted ?? '—')}</div></div>
          <div className="rounded-xl bg-base border border-edge p-3">Open positions <div className="num text-lg">{Array.isArray(pos) ? pos.length : '—'}</div></div>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Book · distance to invalidation</h2>
        {Array.isArray(pos) && pos.length > 0 ? (
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-faint text-[11px] uppercase"><th>Symbol</th><th>Qty</th><th>Entry</th><th>Invalidation</th></tr></thead>
            <tbody>{pos.map((p: any, i: number) => (
              <tr key={i} className="border-t border-edge"><td className="num text-accent">{p.symbol ?? p.sym}</td><td className="num">{p.qty}</td><td className="num">{p.entry ?? p.avg_price}</td><td className="num">{p.invalidation ?? '—'}</td></tr>
            ))}</tbody>
          </table>
        ) : <p className="text-sm text-faint">No open positions reported (or broker unreachable).</p>}
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">OrderGuard preview <span className="text-xs font-normal text-faint">same 7 checks the Live page ticket runs before submit</span></h2>
        <EChart height={180} option={{
          xAxis: { type: 'category', data: ['halt', 'throttle', 'override', 'mandate', 'caps', 'budget', 'submit'] },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } },
          series: [{ type: 'bar', data: [1, 1, 1, 1, 1, 1, 1], itemStyle: { color: '#3FB950' } }],
        }} />
        <p className="text-xs text-faint mt-1">Order placement stays behind an explicit confirm modal (Phase 3).</p>
      </section>
    </div>
  )
}
