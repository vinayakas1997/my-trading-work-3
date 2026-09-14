import { memo, useEffect, useMemo, useState } from 'react'
import { useUI } from '../store'
import type { TerminalData } from './useTerminalData'

// Thin command strip: search-ticker · master pill · clock · conn · palette hint.
export function MasterPill({ master }: { master: TerminalData['master'] }) {
  const style =
    master === 'HALTED'
      ? { borderColor: '#F85149', color: '#F85149', boxShadow: '0 0 18px rgba(248,81,73,.5)' }
      : master === 'DEGRADED'
        ? { borderColor: '#F0B90B', color: '#F0B90B' }
        : { borderColor: '#3FB950', color: '#3FB950' }
  const dot = master === 'HALTED' ? '#F85149' : master === 'DEGRADED' ? '#F0B90B' : '#3FB950'
  return (
    <span className={`chip num font-bold ${master === 'HALTED' ? 'halt-glow' : ''}`} style={style}>
      <span className="dot" style={{ background: dot }} />{master}
    </span>
  )
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="num text-xs text-muted">{now.toLocaleTimeString('en-GB')}</span>
}

export default function CommandStrip({ d, onPalette }: { d: TerminalData; onPalette: () => void }) {
  const sym = useUI((s) => s.sym)
  const setSym = useUI((s) => s.setSym)
  const [q, setQ] = useState('')
  const match = d.tickers.filter((t) => t.toLowerCase().includes(q.toLowerCase())).slice(0, 6)

  return (
    <div className="flex items-center gap-2 px-3 h-12 border-b border-edge bg-panel sticky top-0 z-20">
      <div className="w-8 h-8 rounded-xl flex items-center justify-center font-extrabold text-white shrink-0" style={{ background: 'linear-gradient(135deg,#2F81F7,#A371F7)' }}>V</div>
      <div className="relative">
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="type ticker ⏎"
          onKeyDown={(e) => { if (e.key === 'Enter' && match[0]) { setSym(match[0]); setQ('') } }}
          className="bg-base border border-edge rounded-lg px-2 py-1.5 text-[13px] num w-36 focus:outline-none focus:border-accent"
        />
        {q && (
          <div className="absolute top-9 left-0 bg-raised border border-edge rounded-lg overflow-hidden z-30 min-w-36">
            {match.map((m) => (
              <button key={m} onClick={() => { setSym(m); setQ('') }} className="block w-full text-left px-2 py-1.5 text-[13px] num hover:bg-accent/20 text-accent">{m}</button>
            ))}
          </div>
        )}
      </div>
      <span className="chip num">▶ {sym}</span>
      <div className="flex-1 min-w-0 overflow-hidden"><Tape tape={d.tape} /></div>
      <MasterPill master={d.master} />
      <span className="chip"><span className="dot" style={{ background: d.broker ? '#3FB950' : '#F0B90B' }} />{d.broker ? 'conn' : 'no-broker'}</span>
      <Clock />
      <button onClick={onPalette} className="chip num" title="command palette">⌘K</button>
    </div>
  )
}

// Scrolling ticker tape — marquee, pauses on hover. Memoized: props stable unless a fetch lands.
export const Tape = memo(function Tape({ tape }: { tape: TerminalData['tape'] }) {
  const items = useMemo(() => [...tape, ...tape], [tape])
  return (
    <div className="overflow-hidden whitespace-nowrap [mask-image:linear-gradient(90deg,transparent,#000_5%,#000_95%,transparent)]">
      <div className="tape-marquee inline-flex gap-5 hover:[animation-play-state:paused]">
        {items.map((t, i) => (
          <span key={i} className="num text-[11px] text-muted">
            <b className="text-ink">{t.sym}</b>{' '}
            {t.px != null ? <span className={t.chg != null && t.chg < 0 ? 'text-down' : 'text-up'}>{t.px.toFixed(2)}{t.chg != null ? ` ${t.chg >= 0 ? '+' : ''}${t.chg.toFixed(2)}%` : ''}</span> : <span className="text-faint">—</span>}
          </span>
        ))}
      </div>
    </div>
  )
})
