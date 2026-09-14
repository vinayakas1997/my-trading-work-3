# vinu-ui — Vinu system-mirror trading UI

Isolated frontend. Talks to the FastAPI services over HTTP only (Vite dev
proxy). **No backend edits, no shared code, no shared ports.**

## Run

```bash
cd vinu-components/vinu-ui
npm install
npm run dev      # → http://127.0.0.1:5173 (own port, never clashes with 8080–8095)
npm run build    # typecheck + production build
```

Set `VITE_API_KEY` in `.env` if services require bearer auth:
`VITE_API_KEY=...` (sent as `Authorization: Bearer`).

## Safety rules (do not regress)

- Read-only GETs render automatically; every POST is behind an explicit
  user click (simulate, session replay, re-rank) — order/halt/approve POSTs
  stay unwired until Phase 3 with confirm modals.
- Every fetch fails soft → panel shows "unreachable · mock", never blocks
  other panels, no aggressive retries.
- Deleting this folder restores the system exactly.

## Proxy map (mirrors docker-compose.yml)

stock 8081 · analysis 8083 · research 8087 · live 8091 · portfolio 8090 ·
screener 8095 · agent 8086 · news 8080 · quant-core (strategy+simulator) 8084

## Pages

- `/tickers` — L1 board (table/kanban/timeline/raw switch)
- `/tickers/:sym` — L2 detail: flow, 6 angle families, gates, charts
  (live candles + Kronos 5-step cone + cross), ledger
- `/live` — 5-min cycle strip, book, OrderGuard preview
- `/simulator` — config → run card (equity/metrics) → runs
- `/agents` — mesh roster, sessions + event replay, swarm presets
- `/portfolio` `/screener` `/research` — weights, rules/rankers, artifacts
