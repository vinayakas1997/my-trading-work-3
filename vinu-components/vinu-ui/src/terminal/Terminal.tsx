import { useEffect, useRef, useState } from 'react'
import { useTerminalData } from './useTerminalData'
import CommandStrip from './CommandStrip'
import KpiRibbon from './KpiRibbon'
import StatusBar from './StatusBar'
import QueueRail from './QueueRail'
import HeroChart from './HeroChart'
import EvidenceRail from './EvidenceRail'
import Dock from './Dock'
import Palette from './Palette'

// Dense operator terminal: command strip → KPIs → 3-col drag grid → dock → status.
export default function Terminal() {
  const d = useTerminalData()
  const [palOpen, setPalOpen] = useState(false)
  const [ages, setAges] = useState<Record<string, string>>({})
  const [cols, setCols] = useState<number[]>(() => {
    try {
      const s = localStorage.getItem('vinu-terminal-cols')
      if (s) return JSON.parse(s)
    } catch { /* fresh */ }
    return [230, 1, 300]
  })
  const drag = useRef<number | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalOpen((v) => !v) }
      if (e.key === 'Escape') setPalOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (drag.current == null) return
      const grid = document.getElementById('t-grid')
      if (!grid) return
      const r = grid.getBoundingClientRect()
      const x = e.clientX - r.left
      setCols((c) => {
        const next = [...c]
        if (drag.current === 0) next[0] = Math.min(420, Math.max(160, x))
        else next[2] = Math.min(520, Math.max(200, r.width - x))
        return next
      })
    }
    const up = () => {
      if (drag.current != null) {
        drag.current = null
        setCols((c) => { try { localStorage.setItem('vinu-terminal-cols', JSON.stringify(c)) } catch { /* ignore */ } return c })
      }
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [])

  return (
    <div className="min-h-screen bg-base text-ink font-sans flex flex-col">
      <CommandStrip d={d} onPalette={() => setPalOpen(true)} />
      <div className="px-3 pt-2 max-w-[1700px] w-full mx-auto"><KpiRibbon d={d} /></div>
      <div className="flex-1 px-3 py-2 max-w-[1700px] w-full mx-auto min-h-0">
        <div id="t-grid" className="grid gap-2" style={{ gridTemplateColumns: `${cols[0]}px minmax(0,1fr) ${cols[2]}px` }}>
          <QueueRail d={d} />
          <div className="space-y-2 min-w-0">
            <HeroChart onAges={(a) => setAges((p) => ({ ...p, ...a }))} />
            <Dock />
          </div>
          <EvidenceRail d={d} />
          {/* drag handles */}
          <div onMouseDown={() => { drag.current = 0 }} className="hidden" />
          <div onMouseDown={() => { drag.current = 1 }} className="hidden" />
        </div>
        <div className="flex gap-4 mt-1 text-[10px] text-faint">
          <span onMouseDown={() => { drag.current = 0 }} className="cursor-col-resize select-none hover:text-accent">⇔ drag left rail</span>
          <span onMouseDown={() => { drag.current = 1 }} className="cursor-col-resize select-none hover:text-accent">⇔ drag right rail</span>
        </div>
      </div>
      <StatusBar d={d} ages={{ ...ages, angles: '—' }} />
      <Palette d={d} open={palOpen} onClose={() => setPalOpen(false)} />
    </div>
  )
}
