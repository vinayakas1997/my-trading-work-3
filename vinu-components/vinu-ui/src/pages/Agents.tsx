import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

// Agent mesh: teams/workers as lively nodes, decision feed, sessions + replay, skills atlas.
const TEAMS = [
  { name: 'Summary Agent', desc: 'surveys 28 angles · row_count>0 only', cadence: '30m' },
  { name: 'Planner', desc: 'fit tier + priority · consults HypothesisRegistry', cadence: '30m' },
  { name: 'Researcher / Executor', desc: 'sweep → backtest → author_trade_plan', cadence: 'on demand' },
  { name: 'risk_gatekeeper', desc: 'portfolio-fit · BENCHING→PEND', cadence: '15m' },
  { name: 'capital_allocator', desc: 'whole PEND batch · PEND→ACTIVE', cadence: '15m' },
  { name: 'Monitor', desc: 'invalidation / contingency / bracket / trim', cadence: '5m' },
  { name: 'significance triage', desc: 'statistical gate before Planner', cadence: '15m' },
]

export default function Agents() {
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: api.sessions, refetchInterval: 15_000 })
  const presets = useQuery({ queryKey: ['swarm-presets'], queryFn: api.swarmPresets, refetchInterval: 60_000 })
  const agentStatus = useQuery({ queryKey: ['agent-status'], queryFn: api.agentStatus, refetchInterval: 15_000 })
  const list: any[] = Array.isArray(sessions.data) ? sessions.data : []

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h2 className="font-bold text-sm mb-1">Agent mesh <span className="text-xs font-normal text-faint">{agentStatus.data ? '● agent reachable' : '○ unreachable · static roster'}</span></h2>
        <p className="text-xs text-faint mb-3">Nodes pulse as workers fire — edges light on handoff. Decision feed below shows every verdict with its reason.</p>
        <div className="grid md:grid-cols-4 gap-2">
          {TEAMS.map((t, i) => (
            <div key={t.name} className="rounded-xl bg-base border border-edge p-3 card-lift">
              <div className="flex items-center gap-2">
                <span className="dot flow-pulse" style={{ background: '#2F81F7', animationDelay: `${i * 0.2}s` }} />
                <b className="text-[13px]">{t.name}</b>
              </div>
              <div className="text-[11px] text-muted mt-1">{t.desc}</div>
              <div className="text-[10px] text-faint num mt-1">cadence {t.cadence}</div>
            </div>
          ))}
          <div className="rounded-xl bg-base border border-edge p-3">
            <div className="flex items-center gap-2"><span className="dot" style={{ background: '#A371F7' }} /><b className="text-[13px]">swarm presets</b></div>
            <pre className="text-[10px] text-faint mt-1 overflow-auto max-h-24">{JSON.stringify(presets.data ?? 'unreachable', null, 1).slice(0, 400)}</pre>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-sm mb-2">Sessions <span className="text-xs font-normal text-faint">click → event replay (tool calls in order)</span></h2>
        {list.length ? (
          <div className="space-y-1">{list.slice(0, 20).map((s: any, i: number) => (
            <SessionRow key={s.session_id ?? i} id={s.session_id ?? s.id} title={s.title ?? s.session_id} />
          ))}</div>
        ) : <p className="text-sm text-faint">No sessions reported (or agent unreachable).</p>}
      </section>
    </div>
  )
}

function SessionRow({ id, title }: { id: string; title: string }) {
  const events = useQuery({ queryKey: ['session-events', id], queryFn: () => api.sessionEvents(id), enabled: false })
  return (
    <div className="rounded-lg bg-base border border-edge p-2 text-[13px]">
      <button onClick={() => events.refetch()} className="text-accent num">{title || id}</button>
      {events.data && <pre className="mt-1 text-[11px] text-faint overflow-auto max-h-40">{JSON.stringify(events.data, null, 1).slice(0, 1500)}</pre>}
    </div>
  )
}
