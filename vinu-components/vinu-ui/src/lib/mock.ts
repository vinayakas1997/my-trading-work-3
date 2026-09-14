// Mock shapes used only when a service is unreachable.
// Same field names as the real endpoints so panels render identically.

export const FALLBACK_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']

export const ANGLES28 = [
  'arima', 'backtesting_44_metrics', 'chronos', 'dlinear', 'drawdown_deep_dive',
  'exponential_smoothing', 'garch', 'itransformer', 'kalman_filters', 'kronos',
  'lag_llama', 'lpatchtst', 'lstm', 'moirai', 'moment', 'news_price_causality',
  'patchtst', 'peer_relative_strength', 'pnl_attribution', 'regime_analysis',
  'shock_clustering', 'shock_personality', 'tft', 'timer_timerxl', 'timesfm',
  'tips_regime_aware_transformer', 'trend_lifecycle', 'trend_session_structure',
]

export const FORECAST_READ = new Set(['shock_clustering', 'shock_personality'])

// Angle families — each answers a different trader question, each gets its own view.
export const FAMILIES: { id: string; title: string; question: string; angles: string[] }[] = [
  {
    id: 'ensemble', title: 'Ensemble fan · where next, how sure?',
    question: 'Probabilistic 5-step cones overlaid — overlap = consensus, splay = stand down',
    angles: ['timesfm', 'chronos', 'lag_llama', 'moirai', 'moment', 'timer_timerxl', 'tft', 'kronos'],
  },
  {
    id: 'voters', title: 'Direction voters · which way, one step?',
    question: 'One-step arrows + confidence; Kalman draws the smoothed-truth line',
    angles: ['arima', 'dlinear', 'lstm', 'patchtst', 'lpatchtst', 'itransformer', 'exponential_smoothing', 'tips_regime_aware_transformer', 'kalman_filters'],
  },
  {
    id: 'risk', title: 'Risk · how big may I go?',
    question: 'GARCH vol gauge → position size; drawdown + 44-metric table feed the promotion bar',
    angles: ['garch', 'drawdown_deep_dive', 'backtesting_44_metrics'],
  },
  {
    id: 'structure', title: 'Market structure · what game is this?',
    question: 'Regime ribbon on price, lifecycle stage, session profile, shock cluster + personality',
    angles: ['regime_analysis', 'trend_lifecycle', 'trend_session_structure', 'shock_clustering', 'shock_personality'],
  },
  {
    id: 'relative', title: 'Relative + cause · vs whom, and why?',
    question: 'Peer correlation / excess-return cross chart; news events pinned on price',
    angles: ['peer_relative_strength', 'news_price_causality'],
  },
  {
    id: 'attribution', title: 'Attribution · what actually worked?',
    question: 'PnL split (signal / timing / sizing) with confidence intervals',
    angles: ['pnl_attribution'],
  },
]

export const ALWAYS_PROXY_BACKENDS = new Set(['lag_llama', 'moirai', 'moment'])

export function mockCandles(n = 90, start = 228) {
  let p = start
  const out: { time: number; open: number; high: number; low: number; close: number }[] = []
  const t0 = Math.floor(Date.now() / 1000) - n * 86400
  for (let i = 0; i < n; i++) {
    const o = p
    const c = o + (Math.random() - 0.45) * 3
    out.push({ time: t0 + i * 86400, open: o, high: Math.max(o, c) + Math.random(), low: Math.min(o, c) - Math.random(), close: c })
    p = c
  }
  return out
}
