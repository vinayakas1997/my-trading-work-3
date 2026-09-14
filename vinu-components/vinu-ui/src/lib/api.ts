// Typed HTTP client for the FastAPI services (via Vite dev proxy).
// Read-only GETs first. Every call fails soft (null) so one dead service
// never blocks the rest of the UI — panels fall back to mock shapes.

const API_KEY = (import.meta as any).env?.VITE_API_KEY as string | undefined

async function get<T>(path: string, timeoutMs = 8000): Promise<T | null> {
  try {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), timeoutMs)
    const res = await fetch(path, {
      signal: ctrl.signal,
      headers: API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {},
    })
    clearTimeout(t)
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

async function post<T>(path: string, body?: unknown): Promise<T | null> {
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export interface Candle { time: number; open: number; high: number; low: number; close: number; volume?: number }

export const api = {
  // stock-price :8081
  watchlist: () => get<{ tickers?: string[]; symbols?: string[] }>(`/api/stock/watchlist/tickers`),
  candles: (sym: string, interval = '1d', days = 90) =>
    get<any>(`/api/stock/candles/${sym}?interval=${interval}&days=${days}`),
  quote: (sym: string) => get<any>(`/api/stock/quote/${sym}`),
  // initial-analysis :8083
  angles: () => get<{ angles: string[] }>(`/api/analysis/angles`),
  angleRows: (name: string, sym: string) => get<{ row_count: number; data: any[] }>(`/api/analysis/angle/${name}/${sym}`),
  story: (sym: string) => get<any>(`/api/analysis/story/${sym}`),
  factsheet: (sym: string, method: string) => get<any>(`/api/analysis/v1/factsheet/${sym}/${method}`),
  corrBatch: (syms: string) => get<any>(`/api/analysis/correlation/batch?symbols=${encodeURIComponent(syms)}`),
  drawdown: (sym: string) => get<any>(`/api/analysis/drawdown/${sym}`),
  runAngles: (sym: string, names?: string[]) =>
    post<any>(`/api/analysis/run/${sym}?background=true${names?.length ? `&angle_names=${names.join(',')}` : ''}`),
  runJob: (id: string) => get<any>(`/api/analysis/run/jobs/${id}`),
  // research :8087
  artifacts: (status?: string) => get<any[]>(`/api/research/artifacts${status ? `?status=${status}` : ''}`),
  tradePlan: (id: string) => get<any>(`/api/research/trade-plan/${id}`),
  hypotheses: () => get<any>(`/api/research/introspect/hypotheses`.replace('/introspect/hypotheses', '/hypotheses')),
  symbolState: (sym: string) => get<any>(`/api/research/symbols/${sym}/state`),
  // live :8091
  liveHealth: () => get<any>(`/api/live/health`),
  liveStatus: () => get<any>(`/api/live/status`),
  emergencyStatus: () => get<any>(`/api/live/trade-plan/emergency-status`),
  // portfolio :8090
  pfState: () => get<any>(`/api/portfolio/state`),
  pfWeights: () => get<any>(`/api/portfolio/weights`),
  pfRisk: () => get<any>(`/api/portfolio/risk/status`),
  // screener :8095
  rules: () => get<any>(`/api/screener/rules`),
  rankers: () => get<any>(`/api/screener/rankers`),
  rankLatest: (id: string) => get<any>(`/api/screener/rankers/${id}/latest`),
  rankChurn: (id: string) => get<any>(`/api/screener/rankers/${id}/churn`),
  // agent :8086
  brokerStatus: () => get<any>(`/api/agent/broker/status`),
  brokerAccount: () => get<any>(`/api/agent/broker/account`),
  brokerPositions: () => get<any>(`/api/agent/broker/positions`),
  sessions: () => get<any[]>(`/api/agent/sessions`),
  sessionEvents: (id: string) => get<any>(`/api/agent/sessions/${id}/events`),
  swarmPresets: () => get<any>(`/api/agent/swarm/presets`),
  trace: (ref: string) => get<any>(`/api/agent/trace/${ref}`),
  agentStatus: () => get<any>(`/api/agent/status`),
  // quant-core :8084 (strategy + simulator)
  simRuns: () => get<any>(`/api/quant/simulator/runs`),
  simResult: (id: string) => get<any>(`/api/quant/simulator/results/${id}`),
  simMetrics: (id: string) => get<any>(`/api/quant/simulator/metrics/${id}`),
  simEquity: (id: string) => get<any>(`/api/quant/simulator/equity/${id}`),
  simTrades: (id: string) => get<any>(`/api/quant/simulator/trades/${id}`),
  simulate: (body: unknown) => post<any>(`/api/quant/simulator/simulate`, body),
}
