import { memo } from 'react'
import type { TerminalData } from './useTerminalData'

// 4 KPI cards — the only numbers that can force action.
export default memo(function KpiRibbon({ d }: { d: TerminalData }) {
  const acct: any = d.account
  const equity = acct?.equity ?? acct?.portfolio_value ?? null
  const dd: any = (d.risk as any)?.drawdown_pct ?? ((d.risk as any)?.aggregate as any)?.max_drawdown ?? null
  const openPnl = d.positions.reduce((s: number, p: any) => s + ((+p.unrealized_pl || +p.unrealized_pnl) ?? 0), 0)
  const hasPnl = d.positions.some((p: any) => p.unrealized_pl != null || p.unrealized_pnl != null)
  const active = d.artifacts.filter((a: any) => a.status === 'ACTIVE').length
  const bench = d.artifacts.filter((a: any) => a.status === 'BENCHING' || a.status === 'MONITORING').length
  const budget = (d.risk as any)?.risk_budget_used_pct ?? (d.risk as any)?.aggregate?.budget_used ?? null

  const cards = [
    { label: 'EQUITY', value: equity != null ? `$${Number(equity).toLocaleString()}` : '—', sub: dd != null ? `dd ${dd}%` : 'drawdown —', tone: '#E6E9EF' },
    { label: 'OPEN PNL', value: hasPnl ? `${openPnl >= 0 ? '+' : ''}${openPnl.toFixed(2)}` : `${d.positions.length} pos`, sub: hasPnl ? `${d.positions.length} open` : 'unrealized n/a', tone: hasPnl ? (openPnl >= 0 ? '#26A69A' : '#EF5350') : '#8B93A3' },
    { label: 'ARTIFACTS', value: `${active} live`, sub: `${bench} shadow · ${d.artifacts.length} total`, tone: '#A371F7' },
    { label: 'RISK BUDGET', value: budget != null ? `${budget}%` : '—', sub: (d.risk as any)?.aggregate?.status ?? 'risk-status', tone: '#F0B90B' },
  ]
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
      {cards.map((c) => (
        <div key={c.label} className="card card-lift px-3 py-2">
          <div className="text-[10px] tracking-widest text-faint font-semibold">{c.label}</div>
          <div className="num text-xl font-bold" style={{ color: c.tone }}>{c.value}</div>
          <div className="num text-[11px] text-muted">{c.sub}</div>
        </div>
      ))}
    </div>
  )
})
