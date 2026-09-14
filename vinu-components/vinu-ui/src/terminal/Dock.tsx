import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api } from '../lib/api'
import { ANGLES28, FORECAST_READ, ALWAYS_PROXY_BACKENDS } from '../lib/mock'
import { useUI } from '../store'
import { EChart } from '../components/charts'

const TABS = ['voters', 'angles', 'gates', 'cross', 'ledger'] as const

// Bottom dock: proof on demand, tabs not scroll.
export default function Dock() {
  const { sym } = useUI()
  const nav = useNavigate()
  const [tab, setTab] = useState<(typeof TABS)[number]>('voters')
  const story = useQuery({ queryKey: ['dock-story', sym], queryFn: () => api.story(sym), refetchInterval: 60_000 })
  const angles = useQuery({ queryKey: ['dock-angles'], queryFn: api.angles, refetchInterval: 300_000 })
  // Built once per symbol — never inline, or ECharts disposes/re-inits every render.
  const crossOption = useMemo(() => ({
    xAxis: { type: 'category', data: Array.from({ length: 20 }, (_, i) => `t-${20 - i}`) },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } },
    series: [sym, 'MSFT', 'TSLA'].map((n, i) => ({ name: n, type: 'line', showSymbol: false, data: Array.from({ length: 20 }, () => +(0.2 + Math.random() * 0.6).toFixed(2)), lineStyle: { color: ['#2F81F7', '#A371F7', '#26A69A'][i] } })),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  }) as any, [sym])

  return (
    <div className="card px-3 pt-2 pb-1">
      <div className="flex items-center gap-1.5 text-[11px] mb-1">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`chip num ${tab === t ? '!bg-accent !border-accent text-white' : ''}`}>{t}</button>
        ))}
        <button onClick={() => nav(`/classic/tickers/${sym}`)} className="chip num ml-auto">full detail ⤢</button>
      </div>
      <div className="h-36 overflow-auto text-[12px]">
        {tab === 'voters' && <div className="text-muted">Direction consensus for <b className="num text-accent">{sym}</b> — see right-rail voter bar; full cards in detail view.</div>}
        {tab === 'angles' && (
          <div className="grid grid-cols-4 md:grid-cols-7 gap-1">
            {(angles.data?.angles?.map((a: any) => a.name ?? a) ?? ANGLES28).map((a: string) => (
              <div key={a} className="text-center font-mono text-[10px] p-1 rounded-md bg-base border border-edge truncate" title={a}>
                {a}{FORECAST_READ.has(a) ? ' ★' : ''}{ALWAYS_PROXY_BACKENDS.has(a) ? ' ◐' : ''}
              </div>
            ))}
          </div>
        )}
        {tab === 'gates' && <div className="text-muted">Entry: halt → outage → conflict → stale → freshness → CVaR → blackout → liquidity → borrow → cooldown → turbulence. Exit: contingency → invalidation → rebalance-advisory → ratchet (bookkeeping) → bracket 25/50/75 → hold.</div>}
        {tab === 'cross' && <EChart height={130} option={crossOption} />}
        {tab === 'ledger' && <pre className="text-[11px] text-faint overflow-auto">{JSON.stringify(story.data ?? 'story unreachable', null, 1).slice(0, 1200)}</pre>}
      </div>
    </div>
  )
}
