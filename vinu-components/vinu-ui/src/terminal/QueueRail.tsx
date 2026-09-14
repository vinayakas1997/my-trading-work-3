import { memo, useMemo } from 'react'
import { useUI } from '../store'
import type { TerminalData } from './useTerminalData'

// Attention queue, urgency-sorted: blocked → armed → shadow → quiet.
export default memo(function QueueRail({ d }: { d: TerminalData }) {
  const { sym, setSym } = useUI()
  const rows = useMemo(() => {
    const artBySym = new Map<string, any>()
    for (const a of d.artifacts) {
      const s = a.symbol ?? (Array.isArray(a.universe) ? a.universe[0] : null)
      if (s && !artBySym.has(s)) artBySym.set(s, a)
    }
    const posSyms = new Set(d.positions.map((p: any) => p.symbol ?? p.sym))
    return d.tickers.map((t) => {
      const art = artBySym.get(t)
      const st = art?.status ?? '—'
      let score = 90
      let why = 'quiet'
      if (d.halted) { score = 0; why = 'halted · entries blocked' }
      else if (posSyms.has(t)) { score = 10; why = `${art?.status ?? 'LIVE'} · open` }
      else if (st === 'PEND') { score = 20; why = 'PEND · awaiting funding' }
      else if (st === 'ACTIVE') { score = 30; why = 'ACTIVE · armed' }
      else if (st === 'BENCHING' || st === 'MONITORING') { score = 40; why = 'shadow · promotion watch' }
      else if (st === 'CREATED') { score = 50; why = 'CREATED · needs approve' }
      const tape = d.tape.find((x) => x.sym === t)
      return { sym: t, score, why, st, chg: tape?.chg ?? null }
    }).sort((a, b) => a.score - b.score)
  }, [d])

  return (
    <div className="card p-2 h-full overflow-auto">
      <div className="text-[10px] tracking-widest text-faint font-semibold px-1 pb-1">QUEUE · urgency</div>
      {rows.map((r) => (
        <button key={r.sym} onClick={() => setSym(r.sym)}
          className={`w-full text-left rounded-lg px-2 py-1.5 mb-0.5 transition-colors ${sym === r.sym ? 'bg-accent/20 border border-accent' : 'border border-transparent hover:bg-raised'}`}>
          <div className="flex items-center justify-between">
            <b className="num text-[13px] text-accent">{r.sym}</b>
            {r.chg != null && <span className={`num text-[11px] ${r.chg < 0 ? 'text-down' : 'text-up'}`}>{r.chg >= 0 ? '+' : ''}{r.chg.toFixed(2)}%</span>}
          </div>
          <div className="text-[10px] text-muted truncate">{r.why}</div>
        </button>
      ))}
    </div>
  )
})
