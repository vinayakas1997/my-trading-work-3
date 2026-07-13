export async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = j.detail || JSON.stringify(j)
    } catch (_) {}
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']

export function evaluateStrategy(name, symbols) {
  let url = `/strategies/${name}/evaluate`
  if (symbols && symbols.length) {
    url += '?' + symbols.map(s => `symbols=${s}`).join('&')
  }
  return api(url, { method: 'POST' })
}

export function fetchStrategies() {
  return api('/strategies')
}

export function fetchWeights(strategy, symbol) {
  let url = `/weights?strategy=${strategy}`
  if (symbol) url += `&symbol=${symbol}`
  return api(url)
}
