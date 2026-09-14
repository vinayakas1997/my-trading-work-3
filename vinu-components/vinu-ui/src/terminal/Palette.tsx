import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useUI } from '../store'
import type { TerminalData } from './useTerminalData'

// Ctrl+K palette: jump to tickers + pages. Navigation only — no trading POSTs.
export default function Palette({ d, open, onClose }: { d: TerminalData; open: boolean; onClose: () => void }) {
  const { setSym } = useUI()
  const nav = useNavigate()
  const [q, setQ] = useState('')

  useEffect(() => {
    if (open) setQ('')
  }, [open ])
  if (!open) return null

  const tickers = d.tickers.filter((t) => t.toLowerCase().includes(q.toLowerCase())).slice(0, 8)
  const pages = [
    ['live loop', '/live'], ['simulator lab', '/simulator'], ['agent mesh', '/agents'],
    ['portfolio', '/portfolio'], ['screener', '/screener'], ['research', '/research'],
  ].filter(([l]) => l.includes(q.toLowerCase()))
  const go = (fn: () => void) => { fn(); onClose() }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex justify-center pt-24" onClick={onClose}>
      <div className="w-full max-w-lg card p-2 h-fit" onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="jump to ticker, page…"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              if (tickers[0] && !pages.length) go(() => setSym(tickers[0]))
              else if (pages[0]) go(() => nav(pages[0][1]))
            }
          }}
          className="w-full bg-base border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent" />
        <div className="mt-1 max-h-64 overflow-auto">
          {tickers.map((t) => (
            <button key={t} onClick={() => go(() => setSym(t))} className="block w-full text-left px-3 py-1.5 text-sm num hover:bg-accent/15 rounded">◉ {t}</button>
          ))}
          {pages.map(([l, p]) => (
            <button key={p} onClick={() => go(() => nav(p))} className="block w-full text-left px-3 py-1.5 text-sm hover:bg-accent/15 rounded">→ {l}</button>
          ))}
        </div>
      </div>
    </div>
  )
}
