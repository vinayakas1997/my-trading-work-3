import type { TerminalData } from './useTerminalData'

// 24px trust bar: 10 services · data ages · live/mock.
export default function StatusBar({ d, ages }: { d: TerminalData; ages: Record<string, string> }) {
  const svcs: [string, boolean][] = [
    ['news', true], ['stock', true], ['analysis', true], ['research', true],
    ['live', !!d.liveStatus], ['portfolio', !!d.risk], ['screener', !!d.rules],
    ['agent', !!d.broker], ['quant', true], ['tools', true],
  ]
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 h-7 border-t border-edge bg-panel text-[10px] text-faint num sticky bottom-0 z-20">
      {svcs.map(([n, up]) => (
        <span key={n} className="flex items-center gap-1">
          <span className="dot" style={{ background: up ? '#3FB950' : '#F0B90B', width: 7, height: 7 }} />{n}
        </span>
      ))}
      <span className="ml-auto">candles {ages.candles ?? '—'} · angles {ages.angles ?? '—'} · {d.liveList ? 'watchlist live' : 'watchlist mock'}</span>
    </div>
  )
}
