import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api } from '../lib/api'
import { FALLBACK_TICKERS, ANGLES28 } from '../lib/mock'
import { useUI, type BoardFmt } from '../store'

const STAGES = ['watchlist', 'RunLog', 'ChangeGate', 'Summary', 'Planner', 'sweep', 'CREATED', 'risk', 'PEND', 'alloc', 'ACTIVE', 'monitor']

export default function Tickers() {
  const nav = useNavigate()
  const { boardFmt, setBoardFmt, setSym } = useUI()
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: api.watchlist, refetchInterval: 60_000 })
  const stories = useQuery({
    queryKey: ['stories'],
    queryFn: async () => {
      const list = wl.data?.tickers ?? wl.data?.symbols ?? FALLBACK_TICKERS
      const out: Record<string, any> = {}
      await Promise.all(list.slice(0, 12).map(async (s: string) => { out[s] = await api.story(s) }))
      return out
    },
    enabled: true,
    refetchInterval: 60_000,
  })

  const tickers: string[] = wl.data?.tickers ?? wl.data?.symbols ?? FALLBACK_TICKERS
  const live = !!wl.data
  const open = (s: string) => { setSym(s); nav(`/tickers/${s}`) }
  const fmts: BoardFmt[] = ['table', 'kanban', 'timeline', 'raw']

  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-bold text-sm">L1 · Ticker board <span className="text-xs font-normal text-faint">click a row → live detail · {live ? '● watchlist live' : '○ watchlist unreachable · showing fallback'}</span></h2>
        <div className="flex gap-1.5 text-xs">
          {fmts.map((f) => (
            <button key={f} onClick={() => setBoardFmt(f)} className={`chip ${boardFmt === f ? '!bg-accent !border-accent text-white' : ''}`}>{f}</button>
          ))}
        </div>
      </div>

      {boardFmt === 'table' && (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-faint text-[11px] uppercase tracking-wide">
              <th className="pb-2">Ticker</th><th className="pb-2">RunLog</th><th className="pb-2">Summary</th><th className="pb-2">Artifact</th><th className="pb-2">Monitor</th><th className="pb-2">Flow</th>
            </tr></thead>
            <tbody>
              {tickers.map((s) => {
                const st = stories.data?.[s]
                const hits = st?.angle_hits ?? st?.n_angles ?? null
                return (
                  <tr key={s} onClick={() => open(s)} className="border-t border-edge cursor-pointer hover:bg-raised">
                    <td className="py-2 font-bold text-accent num">{s}</td>
                    <td className="num text-muted">{st ? 'fresh' : '—'}</td>
                    <td className="num">{hits != null ? `${hits}/${ANGLES28.length}` : `—/${ANGLES28.length}`}</td>
                    <td><span className="chip num">{st?.artifact_status ?? '—'}</span></td>
                    <td className="text-muted">{st?.monitor ?? '—'}</td>
                    <td className="whitespace-nowrap">{STAGES.map((g, i) => <span key={g} title={g} className="dot mr-1" style={{ background: i < 5 ? '#3FB950' : '#2A3342' }} />)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {boardFmt === 'kanban' && (
        <div className="flex gap-2 overflow-x-auto">
          {['CREATED', 'BENCHING', 'PEND', 'ACTIVE'].map((c) => (
            <div key={c} className="flex-1 rounded-xl p-2 bg-base border border-edge" style={{ minWidth: 160 }}>
              <h3 className="text-[11px] font-bold text-muted num mb-2">{c}</h3>
              {tickers.filter((s) => (stories.data?.[s]?.artifact_status ?? (s === 'AAPL' ? 'ACTIVE' : 'BENCHING')) === c)
                .map((s) => (
                  <div key={s} onClick={() => open(s)} className="rounded-lg p-2 mb-2 cursor-pointer card card-lift"><b className="num text-accent">{s}</b></div>
                ))}
            </div>
          ))}
        </div>
      )}

      {boardFmt === 'timeline' && (
        <div className="space-y-3">
          {tickers.map((s) => (
            <div key={s} onClick={() => open(s)} className="cursor-pointer">
              <b className="num text-accent">{s}</b>
              <div className="mt-1 flex flex-wrap gap-1">{STAGES.map((g, i) => <span key={g} className="chip" style={i < 5 ? { borderColor: '#2F81F7' } : { opacity: 0.45 }}>{i < 5 ? '●' : '○'} {g}</span>)}</div>
            </div>
          ))}
        </div>
      )}

      {boardFmt === 'raw' && (
        <pre className="text-[11px] p-3 rounded-lg bg-base border border-edge overflow-auto" style={{ color: '#7dd3fc' }}>
          {JSON.stringify({ watchlist: tickers, live, stories: stories.data ?? null }, null, 2)}
        </pre>
      )}
    </section>
  )
}
