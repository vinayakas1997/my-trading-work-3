import { useQueries, useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { api } from '../lib/api'
import { FALLBACK_TICKERS } from '../lib/mock'

// Shared terminal data: one fetch per source, props flow down.
// Every query fails soft → panels degrade to mock, never block.
export function useTerminalData() {
  const watchlist = useQuery({ queryKey: ['t-watchlist'], queryFn: api.watchlist, refetchInterval: 60_000 })
  const tickers = useMemo(
    () => watchlist.data?.tickers ?? watchlist.data?.symbols ?? FALLBACK_TICKERS,
    [watchlist.data],
  )
  const liveList = !!watchlist.data

  const closes = useQueries({
    queries: tickers.slice(0, 12).map((s) => ({
      queryKey: ['t-close', s],
      queryFn: () => api.candles(s, '1d', 5),
      refetchInterval: 60_000,
    })),
  })
  // Signature changes only when a fetch lands → tape identity stays stable otherwise.
  const closeSig = closes.map((c) => c.dataUpdatedAt).join(',')
  const tape = useMemo(() => tickers.slice(0, 12).map((s, i) => {
    const raw: any = closes[i]?.data
    const rows = raw?.candles ?? raw?.data ?? []
    const last = rows[rows.length - 1]
    const prev = rows[rows.length - 2]
    const px = last ? +last.close : null
    const chg = last && prev && +prev.close ? ((+last.close - +prev.close) / +prev.close) * 100 : null
    return { sym: s, px, chg, live: !!last }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [tickers, closeSig])

  const broker = useQuery({ queryKey: ['t-broker'], queryFn: api.brokerStatus, refetchInterval: 10_000 })
  const account = useQuery({ queryKey: ['t-account'], queryFn: api.brokerAccount, refetchInterval: 15_000 })
  const positions = useQuery({ queryKey: ['t-positions'], queryFn: api.brokerPositions, refetchInterval: 10_000 })
  const risk = useQuery({ queryKey: ['t-risk'], queryFn: api.pfRisk, refetchInterval: 60_000 })
  const emergency = useQuery({ queryKey: ['t-emergency'], queryFn: api.emergencyStatus, refetchInterval: 10_000 })
  const artifacts = useQuery({ queryKey: ['t-artifacts'], queryFn: () => api.artifacts(), refetchInterval: 30_000 })
  const liveStatus = useQuery({ queryKey: ['t-live'], queryFn: api.liveStatus, refetchInterval: 10_000 })
  const rules = useQuery({ queryKey: ['t-rules'], queryFn: api.rules, refetchInterval: 30_000 })

  const halted = (broker.data as any)?.halted === true || (emergency.data as any)?.halted === true
  const anyDown = [watchlist, broker, account, risk, artifacts].some((q) => q.isError)
  const master: 'HALTED' | 'DEGRADED' | 'CLEAR' = halted ? 'HALTED' : anyDown ? 'DEGRADED' : 'CLEAR'

  const posList: any[] = useMemo(() => {
    const p = positions.data as any
    return p?.positions ?? (Array.isArray(p) ? p : [])
  }, [positions.data])

  const artList: any[] = useMemo(() => {
    const a = artifacts.data as any
    return Array.isArray(a) ? a : []
  }, [artifacts.data])

  // Stable object identity → React.memo children below only re-render on real data change.
  return useMemo(() => ({
    tickers, liveList, tape, broker: broker.data, account: account.data,
    positions: posList, risk: risk.data, emergency: emergency.data,
    artifacts: artList, liveStatus: liveStatus.data, rules: rules.data,
    halted, master,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [watchlist.data, broker.data, account.data, positions.data, risk.data, emergency.data, artifacts.data, liveStatus.data, rules.data, tickers, tape, halted, master])
}

export type TerminalData = ReturnType<typeof useTerminalData>
