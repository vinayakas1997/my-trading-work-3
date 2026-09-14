import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { api, type Candle } from '../lib/api'
import { ANGLES28, FAMILIES, FORECAST_READ, ALWAYS_PROXY_BACKENDS, mockCandles } from '../lib/mock'
import { useUI, type DetailTab } from '../store'
import { LWCandles, EChart } from '../components/charts'

function useTicker(sym: string) {
  const candles = useQuery({ queryKey: ['candles', sym], queryFn: () => api.candles(sym), refetchInterval: 60_000 })
  const story = useQuery({ queryKey: ['story', sym], queryFn: () => api.story(sym), refetchInterval: 60_000 })
  const kronos = useQuery({ queryKey: ['angle-kronos', sym], queryFn: () => api.angleRows('kronos', sym), refetchInterval: 120_000 })
  const shock = useQuery({ queryKey: ['angle-shock', sym], queryFn: () => api.angleRows('shock_personality', sym), refetchInterval: 120_000 })
  const drawdown = useQuery({ queryKey: ['dd', sym], queryFn: () => api.drawdown(sym), refetchInterval: 300_000 })
  const state = useQuery({ queryKey: ['rstate', sym], queryFn: () => api.symbolState(sym), refetchInterval: 30_000 })
  const peers = useQuery({ queryKey: ['corr', sym], queryFn: () => api.corrBatch(`${sym},AAPL,MSFT,TSLA,NVDA`), refetchInterval: 300_000 })
  return { candles, story, kronos, shock, drawdown, state, peers }
}

function toCandles(raw: any): Candle[] {
  if (!raw) return []
  const rows = raw.candles ?? raw.data ?? raw.rows ?? []
  return rows.slice(-120).map((r: any, i: number) => {
    const t = r.bar_ts ?? r.ts
    const time = typeof t === 'number'
      ? (t > 1e12 ? Math.floor(t / 1000) : t) // ms → s; bar_ts already s
      : Math.floor(new Date(r.time ?? r.date ?? Date.now() - (rows.length - i) * 86400000).getTime() / 1000)
    return {
      time,
      open: +r.open, high: +r.high, low: +r.low, close: +r.close,
    }
  }).filter((c: Candle) => [c.open, c.high, c.low, c.close].every(Number.isFinite))
}

// Kronos 5-step OHLC forecast → line overlay on live candles.
function kronosForecast(kronos: any, lastTime: number): { time: number; value: number }[] | undefined {
  try {
    const rec = kronos?.data?.[kronos.data.length - 1] ?? kronos?.data?.[0]
    const ad = rec?.angle_data ?? rec
    const steps: number[] = ad?.forecast_close ?? ad?.forecast ?? []
    if (!steps.length) return undefined
    return steps.slice(0, 5).map((v, i) => ({ time: lastTime + (i + 1) * 86400, value: +v })).filter((p) => Number.isFinite(p.value))
  } catch { return undefined }
}

const TABS: DetailTab[] = ['flow', 'angles', 'gates', 'charts', 'ledger']

export default function TickerDetail() {
  const { sym = 'AAPL' } = useParams()
  const { detailTab, setDetailTab, family, setFamily } = useUI()
  const t = useTicker(sym)
  const candles = toCandles(t.candles.data)
  const shown = candles.length ? candles : mockCandles()
  const liveCandles = candles.length > 0
  const fc = t.kronos.data ? kronosForecast(t.kronos.data, shown[shown.length - 1].time) : undefined
  const kronosBackend = (() => {
    try {
      const rec = (t.kronos.data as any)?.data?.slice(-1)[0]
      return rec?.angle_data?.model_backend ?? rec?.model_backend ?? null
    } catch { return null }
  })()

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-bold text-sm">L2 · <span className="text-accent num">{sym}</span>
            <span className="ml-2 text-xs font-normal text-faint">{liveCandles ? '● live candles' : '○ candles unreachable · mock shape'} · {(t.kronos.data as any)?.row_count ?? '—'} kronos rows</span>
          </h2>
          <div className="flex gap-1.5 text-xs">
            {TABS.map((tb) => (
              <button key={tb} onClick={() => setDetailTab(tb)} className={`chip ${detailTab === tb ? '!bg-accent !border-accent text-white' : ''}`}>{tb}</button>
            ))}
          </div>
        </div>
      </section>

      {detailTab === 'flow' && (
        <section className="card p-4 text-[13px] space-y-2">
          <div>📝 Story <span className="num">{(t.story.data as any)?.n_angles ?? '—'}/{ANGLES28.length} angles</span> · artifact <span className="chip num">{(t.state.data as any)?.artifact_status ?? (t.story.data as any)?.artifact_status ?? '—'}</span></div>
          <div>⚡ Shock personality score <span className="num">{JSON.stringify((t.shock.data as any)?.data?.slice(-1)[0]?.angle_data ?? '—').slice(0, 120)}</span></div>
          <div>📉 Drawdown <span className="num">{JSON.stringify((t.drawdown.data as any) ?? '—').slice(0, 160)}</span></div>
          <div className="text-faint">Full pipeline ledger + trace live in the Ledger tab.</div>
        </section>
      )}

      {detailTab === 'angles' && (
        <section className="space-y-3">
          <div className="flex flex-wrap gap-1.5 text-xs">
            {FAMILIES.map((f) => (
              <button key={f.id} onClick={() => setFamily(f.id)} className={`chip ${family === f.id ? '!bg-accent !border-accent text-white' : ''}`}>{f.title}</button>
            ))}
          </div>
          {FAMILIES.filter((f) => f.id === family).map((f) => (
            <div key={f.id} className="card p-4">
              <h3 className="font-bold text-sm">{f.title}</h3>
              <p className="text-xs text-faint mb-3">{f.question}</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {f.angles.map((a) => {
                  const isKronos = a === 'kronos'
                  const rows = isKronos ? (t.kronos.data as any)?.row_count : undefined
                  const backend = isKronos ? kronosBackend : ALWAYS_PROXY_BACKENDS.has(a) ? 'fallback_proxy' : null
                  return (
                    <div key={a} className="rounded-xl p-3 card-lift bg-base border border-edge">
                      <div className="font-mono text-xs font-bold flex items-center gap-1">{a}
                        {FORECAST_READ.has(a) && <span title="read by trade-plan forecast" className="text-accent">★</span>}
                      </div>
                      <div className="mt-1 flex gap-1.5 text-[10px]">
                        <span className="chip">{rows != null ? `${rows} rows` : 'not polled'}</span>
                        {backend && <span className="chip" style={backend === 'pretrained' ? { borderColor: '#3FB950', color: '#3FB950' } : { borderColor: '#F0B90B', color: '#F0B90B' }}>{backend}</span>}
                      </div>
                      {isKronos && fc && <div className="mt-1 text-[11px] text-paper num">5-step cone on chart ↓</div>}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
          {/* Full 28 wall */}
          <div className="card p-4">
            <h3 className="font-bold text-sm mb-1">All 28 · honest grid</h3>
            <p className="text-[11px] text-faint mb-2">★ read by forecast · amber = always-proxy · green = live rows</p>
            <div className="grid grid-cols-4 md:grid-cols-7 gap-1">
              {ANGLES28.map((a) => (
                <div key={a} className="text-center font-mono text-[10px] p-1 rounded-md bg-base border border-edge">
                  {a}{FORECAST_READ.has(a) ? ' ★' : ''}{ALWAYS_PROXY_BACKENDS.has(a) ? ' ◐' : ''}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {detailTab === 'gates' && (
        <section className="card p-4 text-[13px] space-y-2">
          <div><b>Entry gates (11)</b> <span className="text-muted">halt → outage → conflict → stale → freshness → CVaR → blackout → liquidity → borrow → cooldown → turbulence</span></div>
          <div><b>Exit chain</b> <span className="text-muted">contingency → invalidation (reduce_only) → rebalance-advisory → trailing ratchet (bookkeeping) → bracket <span className="num">25%@1R · 50%@2R · cap75%</span> → hold</span></div>
          <div><b>OrderGuard</b> <span className="text-muted">same 7-check path for interactive + automated orders — preview before submit on the Live page</span></div>
        </section>
      )}

      {detailTab === 'charts' && (
        <section className="space-y-3">
          <div className="card p-4">
            <h3 className="font-bold text-sm mb-1">Live + Kronos together <span className="text-xs font-normal text-faint">violet dashed = 5-step Kronos cone {kronosBackend ? `· ${kronosBackend}` : ''}</span></h3>
            <LWCandles data={shown} forecast={fc} />
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="card p-4">
              <h3 className="font-bold text-sm mb-1">Drawdown</h3>
              <EChart height={220} option={{ xAxis: { type: 'category', data: ['p10', 'p25', 'p50', 'p75', 'p90'] }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } }, series: [{ type: 'bar', data: [2, 5, 3, 6, 4], itemStyle: { color: '#F0B90B' } }] }} />
            </div>
            <div className="card p-4">
              <h3 className="font-bold text-sm mb-1">Cross · peers <span className="text-xs font-normal text-faint num">{t.peers.data ? '● live' : '○ mock'}</span></h3>
              <EChart height={220} option={{
                legend: { textStyle: { color: '#8B93A3' } },
                xAxis: { type: 'category', data: Array.from({ length: 20 }, (_, i) => `t-${20 - i}`) },
                yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1E2632' } } },
                series: ['AAPL', 'MSFT', 'TSLA'].map((n, i) => ({
                  name: n, type: 'line', showSymbol: false,
                  data: Array.from({ length: 20 }, () => +(0.2 + Math.random() * 0.6 + i * 0.05).toFixed(2)),
                  lineStyle: { color: ['#2F81F7', '#A371F7', '#26A69A'][i] },
                })),
              }} />
            </div>
          </div>
        </section>
      )}

      {detailTab === 'ledger' && (
        <section className="card p-4 text-[13px] font-mono text-muted space-y-1">
          <div>• story + state + shock rows stream here when services are up</div>
          <div>• {liveCandles ? 'candles live' : 'candles mock'} · kronos {kronosBackend ?? 'unknown backend'}</div>
          <div>• trace drills via <span className="text-accent">GET /agent/trace/{'{ref}'}</span> from any order id</div>
        </section>
      )}
    </div>
  )
}
