import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api, type Candle } from '../lib/api'
import { mockCandles } from '../lib/mock'
import { useUI } from '../store'
import { LWCandles } from '../components/charts'

const TFS = [
  { id: '1D', interval: '1d', days: 5 },
  { id: '1M', interval: '1d', days: 30 },
  { id: '3M', interval: '1d', days: 90 },
  { id: '6M', interval: '1d', days: 180 },
  { id: '1Y', interval: '1d', days: 365 },
  { id: 'ALL', interval: '1d', days: 730 },
]

function toCandles(raw: any): Candle[] {
  if (!raw) return []
  const rows = raw.candles ?? raw.data ?? []
  return rows.slice(-400).map((r: any) => {
    const t = r.bar_ts ?? r.ts
    const time = typeof t === 'number' ? (t > 1e12 ? Math.floor(t / 1000) : t) : Math.floor(new Date(r.time ?? r.date ?? Date.now()).getTime() / 1000)
    return { time, open: +r.open, high: +r.high, low: +r.low, close: +r.close }
  }).filter((c: Candle) => [c.open, c.high, c.low, c.close].every(Number.isFinite))
}

// Hero: live candles + Kronos 5-step cone + TF tabs + one-line action.
export default function HeroChart({ onAges }: { onAges: (a: Record<string, string>) => void }) {
  const { sym, setDetailTab } = useUI()
  const nav = useNavigate()
  const [tf, setTf] = useState(TFS[3])
  const [confirmFlat, setConfirmFlat] = useState(false)

  const candles = useQuery({ queryKey: ['h-candles', sym, tf.id], queryFn: () => api.candles(sym, tf.interval, tf.days), refetchInterval: 60_000 })
  const kronos = useQuery({ queryKey: ['h-kronos', sym], queryFn: () => api.angleRows('kronos', sym), refetchInterval: 120_000 })
  const positions = useQuery({ queryKey: ['h-positions'], queryFn: api.brokerPositions, refetchInterval: 10_000 })
  const artifacts = useQuery({ queryKey: ['h-artifacts'], queryFn: () => api.artifacts(), refetchInterval: 30_000 })

  const data = toCandles(candles.data)
  const shown = data.length ? data : mockCandles()
  const live = data.length > 0
  const last = shown[shown.length - 1]

  const fc = (() => {
    try {
      const rec: any = (kronos.data as any)?.data?.slice(-1)[0]
      const steps: number[] = rec?.angle_data?.forecast_close ?? rec?.angle_data?.forecast ?? []
      if (!steps.length || !last) return undefined
      return steps.slice(0, 5).map((v, i) => ({ time: last.time + (i + 1) * 86400, value: +v })).filter((p) => Number.isFinite(p.value))
    } catch { return undefined }
  })()
  const backend = (() => {
    try {
      const rec: any = (kronos.data as any)?.data?.slice(-1)[0]
      return rec?.angle_data?.model_backend ?? null
    } catch { return null }
  })()

  const pos = ((positions.data as any)?.positions ?? []).find((p: any) => (p.symbol ?? p.sym) === sym)
  const art = ((artifacts.data as any) ?? []).find((a: any) => a.symbol === sym || (Array.isArray(a.universe) && a.universe.includes(sym)))
  const pnl = pos?.unrealized_pl ?? pos?.unrealized_pnl
  const distInv = pos && last && pos.invalidation ? (((last.close - +pos.invalidation) / last.close) * 100).toFixed(1) : null

  // Ages flow up on a timer only — NEVER setState during render (render loop).
  useEffect(() => {
    const push = () => {
      if (!candles.dataUpdatedAt) return
      const m = Math.max(0, Math.round((Date.now() - candles.dataUpdatedAt) / 60000))
      onAges({ candles: m === 0 ? 'just now' : `${m}m old` })
    }
    push()
    const t = setInterval(push, 30_000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles.dataUpdatedAt])

  const flatten = async () => {
    if (!confirmFlat) { setConfirmFlat(true); return }
    setConfirmFlat(false)
    await fetch('/api/live/trade-plan/emergency-flatten', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  }

  return (
    <div className="card p-3">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <b className="num text-lg text-accent">{sym}</b>
        <span className="num text-lg">{last ? last.close.toFixed(2) : '—'}</span>
        <span className="text-[11px] text-faint">{live ? '● live' : '○ mock shape'} · kronos {backend ?? (kronos.data ? 'rows' : '—')}</span>
        <div className="ml-auto flex gap-1 text-[11px]">
          {TFS.map((t) => (
            <button key={t.id} onClick={() => setTf(t)} className={`chip num ${tf.id === t.id ? '!bg-accent !border-accent text-white' : ''}`}>{t.id}</button>
          ))}
        </div>
      </div>
      <LWCandles data={shown} forecast={fc} />
      {/* Action line — the decision in one sentence + the two buttons that matter */}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px] rounded-lg bg-base border border-edge px-3 py-2">
        <span className="dot" style={{ background: pos ? '#26A69A' : '#5B6474' }} />
        <span>
          {pos ? <><b className="num">{sym} {pos.side ?? 'LONG'} {pos.qty}</b> · <span className={`num ${pnl < 0 ? 'text-down' : 'text-up'}`}>{pnl != null ? `${pnl >= 0 ? '+' : ''}${(+pnl).toFixed(2)}` : 'open'}</span>{distInv != null && <span className="text-muted"> · invalidation {distInv}% away</span>}</>
            : <span className="text-muted">{art ? `${art.status} · ${art.name ?? art.artifact_id}` : 'flat · no plan'} — arm via Research, trace anything below</span>}
        </span>
        <span className="ml-auto flex gap-1.5">
          <button onClick={flatten} className="chip num" style={confirmFlat ? { borderColor: '#F85149', color: '#F85149' } : {}}>{confirmFlat ? 'confirm flatten?' : 'flatten'}</button>
          <button onClick={() => { setDetailTab('ledger'); nav(`/classic/tickers/${sym}`) }} className="chip num">trace ⤢</button>
        </span>
      </div>
    </div>
  )
}
