# System-mirror UI plan (L0 → L3) — LOCKED 2026-09-14

## Locked stack (good + easy, no style compromise)
- React 19 + TypeScript 5 + Vite 7, Node ≥22. `react-router` v7, `zustand` v5, `@tanstack/react-query`.
- Styling: **Tailwind CSS v4** + **shadcn/ui** (Radix + cva + tailwind-merge), `lucide-react`,
  `next-themes` (dark-first), `sonner` toasts, `motion` animations,
  `@fontsource/inter` + `@fontsource/jetbrains-mono`.
- Charts: `lightweight-charts` v5 (candles + entries/exits + EMA/BB/VWAP) +
  `echarts` v6 (equity, drawdown, correlation heatmap, sweep compare, attribution).
- 3D (lazy-loaded, never data owners): `three` + `@react-three/fiber` + `@react-three/drei` +
  `@react-three/postprocessing`. Scenes: correlation 3D network, allocation blocks,
  regime/angle-embedding scatter, market flows. WebGL-off → ECharts 2D fallback, same numbers.
- Agent chat: `react-markdown` + `remark-gfm` + `katex`, `highlight.js` for code/ledger blocks.
- Live: SSE + reconnect banner (Vibe `ConnectionBanner` pattern), WS later. Tests: vitest + Playwright.
- Dropped: StyleX (higher ceiling, slower start — revisit only if shadcn boxes us in),
  Recharts (SVG-bound), Plotly (heavy), Qt/Electron desktop.

## Design system — premium dark trading theme (dark-first)
- Fonts: Inter (UI) + JetBrains Mono (numbers/tickers/ledger). Tabular numerals everywhere.
- Color tokens:
  - `bg-base #0A0E14`, `bg-panel #11161F`, `bg-raised #161D29`, `border #1E2632`
  - `text-primary #E6E9EF`, `text-muted #8B93A3`, `text-faint #5B6474`
  - `accent #2F81F7` (links, ACTIVE, selection), `paper #A371F7` (shadow/benching violet)
  - `up #26A69A` (trading green), `down #EF5350` (trading red)
  - `warn #F0B90B` (degraded/drawdown amber), `halt #F85149` (kill-switch red, glow banner)
  - `ok #3FB950` (healthy/heartbeat green)
- Market-state theming: halt banner glows red + blocks entries; degraded amber chips;
  shadow/paper flows violet; live money flows green/red by PnL sign.
- Rules: never red/green by hue alone for status vs PnL — status uses dot+label;
  numbers always JetBrains Mono with sign (+/−) and unit; halt state dominates top strip.

## L0 — Fleet / market strip (always visible)
| Signal | Source | UI element |
|---|---|---|
| Kill switch | `GET /agent/broker/status` + `/tmp/vinu-trading-halt` | full-width glow banner when halted; scope + `entries_only` policy chip |
| Broker health | `_check_broker_health`, 180s grace | dot: healthy / degraded (blip inside grace ≠ pause) |
| Drawdown monitor (5m) | `PortfolioDrawdownMonitor.check` | -10% halve / -15% flat / -20% halt + abs-loss bar |
| OOD / turbulence / CVaR gate | `_check_ood`, entry gates | chips: alert / halt / flatten |
| Correlation | DCC + shrinkage matrix | heatmap + trim badge on larger leg (+ 3D network scene) |
| Workers | planner 30m, risk 15m, allocator 15m, significance 15m, live 5m, feedback 5m, shadow 1h, analysis 1h, screener 30s, ranker 24h | heartbeat dots + age, stale pulses amber |

## L1 — Ticker board (one row per ticker)
Pipeline: watchlist → RunLog fresh? → ChangeGate → Summary (n/28) → significance →
Planner tier → sweep → CREATED → risk verdict → PEND → allocator → ACTIVE/live/shadow →
Monitor → feedback/ledger. Artifact statuses: `CREATED / BENCHING / MONITORING / PEND / ACTIVE / REJECTED / decayed`.
Formats (switchable, same state): table | kanban (by artifact status) | timeline (pipeline dots) | raw JSON.

## L2 — Ticker detail (drill from L1 row)
- Artifact timeline (CREATED→…→ACTIVE, actor: team/hook/manual `force`).
- 28-angle grid: per angle `completed / skipped_existing / failed`, run_id, elapsed,
  `row_count>0`, `low_trust<0.45` flag. Honest badge: forecast reads only
  `shock_personality` + `shock_clustering` (other 26 visible, marked unread ★).
- Sweep/backtest evidence + promotion bar (Sharpe/PSR/drawdown/paper-days + correlation verdict).
- Live gates: 11 entry blocks (`entry_blocked_by_*`) + exit chain
  (contingency → invalidation → rebalance-advisory → trailing ratchet (bookkeeping) →
  bracket 25%@1R / 50%@2R / cap75% → hold).
- Charts (in L2 only): lightweight-charts candles + entries/exits + overlays;
  ECharts equity/drawdown/sweep; three.js 3D correlation preview.
- Ledger excerpt (append-only) + HypothesisRegistry outcome.

## L3 — Trace (drill from any order/decision)
`GET /agent/trace/{ref_id}`: OrderGuard 7 checks in order
(halt → throttle 10/s → symbol override → mandate expiry → notional caps →
risk budget → submit + resting `oto` stop) + TeamRunStore + `order_placed` id.

## Donor mapping (reference repos)
Shell (sidebar/sessions/SSE banner/dark/i18n) ← Vibe-Trading `Layout+router+stores`;
page contents (screener/backtest/portfolio/chat) ← dsa-web (refactored);
bot-control semantics ← freqtrade FreqUI+API; completeness checklist ← FinceptTerminal;
L0→L3 flow/trace ← vinu-only.

## Build order
1. `demo.html` (this folder, mock data) → confirm layout + chart lib. ✅
2. `vinu-components/vinu-ui/` — single Vite+TS portal, read-only GETs first, shared `components/charts`.
3. MVP Live wiring (poll 5s, WS later), confirm-modals, audit-trail page.
4. Read-only GET gaps (no trading-logic change): ChangeGate verdict, Planner fit-tier, per-ticker RunLog/angle status.
