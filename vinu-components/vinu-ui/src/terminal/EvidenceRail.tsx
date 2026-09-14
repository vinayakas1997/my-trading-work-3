import { useQueries } from '@tanstack/react-query'
import { memo, useState } from 'react'
import { useUI } from '../store'
import { api } from '../lib/api'
import type { TerminalData } from './useTerminalData'

// Right rail: fleet mini + verdict feed + voter bar + risk box. 5 lines max each.
function Block({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="card p-2">
      <button onClick={() => setOpen(!open)} className="text-[10px] tracking-widest text-faint font-semibold w-full text-left">{open ? '▾' : '▸'} {title}</button>
      {open && <div className="mt-1 space-y-1">{children}</div>}
    </div>
  )
}

function dirOf(rows: any): '↑' | '↓' | '→' | '—' {
  try {
    const rec = rows?.data?.slice(-1)[0]
    const ad = rec?.angle_data ?? rec ?? {}
    const s = JSON.stringify(ad).toLowerCase()
    const dir = (ad.direction ?? ad.trend ?? ad.signal ?? '').toString().toLowerCase()
    if (/up|bull|long|buy/.test(dir)) return '↑'
    if (/down|bear|short|sell/.test(dir)) return '↓'
    const c = ad.forecast_close ?? ad.forecast ?? []
    if (c.length >= 2) return +c[c.length - 1] >= +c[0] ? '↑' : '↓'
    if (/flat|neutral|sideways/.test(dir + s)) return '→'
    return '—'
  } catch { return '—' }
}

export default memo(function EvidenceRail({ d }: { d: TerminalData }) {
  const { sym } = useUI()
  const voters = useQueries({
    queries: ['arima', 'lstm', 'dlinear'].map((a) => ({
      queryKey: ['ev-voter', a, sym], queryFn: () => api.angleRows(a, sym), refetchInterval: 120_000,
    })),
  })
  const verdicts = [...d.artifacts]
    .sort((a: any, b: any) => +new Date(b.updated_at ?? 0) - +new Date(a.updated_at ?? 0))
    .slice(0, 5)
  const agree = voters.filter((v) => dirOf(v.data) === '↑').length
  const disagree = voters.filter((v) => dirOf(v.data) === '↓').length

  return (
    <div className="space-y-2 h-full overflow-auto">
      <Block title="FLEET">
        <div className="text-[11px] num text-muted">equity {(d.account as any)?.equity ?? '—'} · dd {(d.risk as any)?.drawdown_pct ?? '—'}</div>
        <div className="text-[11px] num text-muted">live {(d.liveStatus as any)?.status ?? '—'} · OOD dormant</div>
      </Block>
      <Block title="VERDICTS · latest">
        {verdicts.length ? verdicts.map((a: any, i: number) => (
          <div key={i} className="text-[11px]"><span className="chip num" style={{ fontSize: 10 }}>{a.status}</span> <span className="num text-accent">{a.symbol ?? a.name ?? a.artifact_id}</span></div>
        )) : <div className="text-[11px] text-faint">no verdicts yet</div>}
      </Block>
      <Block title={`VOTERS · ${sym} (${agree}↑ ${disagree}↓)`}>
        <div className="h-1.5 rounded bg-base overflow-hidden flex">
          <div style={{ width: `${(agree / 3) * 100}%`, background: '#26A69A' }} />
          <div style={{ width: `${(disagree / 3) * 100}%`, background: '#EF5350' }} />
        </div>
        {['arima', 'lstm', 'dlinear'].map((a, i) => (
          <div key={a} className="text-[11px] num text-muted flex justify-between"><span>{a}</span><span>{dirOf(voters[i].data)} {(voters[i].data as any)?.row_count ?? '—'}r</span></div>
        ))}
      </Block>
      <Block title="RISK">
        <div className="text-[11px] num text-muted">budget {(d.risk as any)?.risk_budget_used_pct ?? '—'} · halt-pol entries_only</div>
        <div className="text-[11px] num text-muted">corr trim armed · CVaR gate live</div>
      </Block>
    </div>
  )
})
