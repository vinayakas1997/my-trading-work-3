# UI design — system-mirror trading UI

Purpose: UI that **reflects the real vinu pipeline**, not a generic terminal.
What is flowing, per-ticker status, per-market status, switchable formats,
drillable to full granularity (L0 → L3).

## Contents

- `demo.html` — Phase 0 static click-demo (no build, open in browser).
  Mock data for 2 tickers (AAPL, TSLA) across all layers.
- `00-system-mirror-ui-plan.md` — full layer/endpoint/format spec.

## Layers

- L0 Fleet: kill-switch, broker health, drawdown monitor, worker heartbeats
- L1 Ticker board: watchlist × stage × artifact status (table / kanban / timeline / raw)
- L2 Ticker detail: artifact timeline, 28-angle grid, sweep evidence, ledger
- L3 Trace: OrderGuard 7-check chain + TeamRunStore + order id

## Sources of truth

- `project-understanding/01-new-full-explanation-v2.md` — pipeline diagram
- `project-understanding/03-granularity-understanding/` — per-service cadences/pipelines
- `other-repos-world/repos` — reference UIs (Vibe-Trading, dsa-web, FreqUI, FinceptTerminal)
