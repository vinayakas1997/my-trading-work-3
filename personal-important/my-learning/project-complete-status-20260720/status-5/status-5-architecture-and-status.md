# Project Status — Update (post status-3/4/5 analysis-to-execution + broker-independent fixes)

Companion to [status-2-architecture-and-status.md](../status-2/status-2-architecture-and-status.md)
(the previous full refresh), and this folder's [status-5.md](./status-5.md) /
[status-5-fix-plan.md](./status-5-fix-plan.md) (what changed and why). Between that document and this
one, three more review rounds happened (status-3, status-4, status-5) and — as of this document —
**every gap identified across all of them that could be closed without a live broker account has been
closed.** Like every prior document in this series, every claim here was checked against the actual
code, not design intent.

---

## 0. What changed since status-2-architecture-and-status.md, in one paragraph

status-2's refresh left two clusters of open work: a senior-quant gap list (survivorship bias,
point-in-time discipline, `vinu-portfolio`'s kill-switch duplication) and a separate, deeper finding —
that the research/promotion pipeline and the order-submission path were never actually connected, so
an unresearched or unpromoted symbol could still be traded. Since then: the analysis-to-execution gate
was built (`OrderGuard` now checks artifact status before allowing an order), the kill-switch
duplication turned out to be a real cross-container isolation bug (each service has its own private
`/tmp`) and was fixed via a proper networked endpoint, that endpoint is now actually driven by a
scheduled drawdown monitor, and — in the final pass — stop-loss bracket orders, a market-hours check,
portfolio-level correlation/concentration enforcement, and all five of `vinu-live`'s known execution
bugs were built and fixed. `vinu-live` moves from "exists but not safe to treat as functional" to
"implemented and tested against Alpaca's documented API contracts, not yet run against a real
account." That last clause — no broker account — is now the only thing this whole series of documents
has left unresolved, and it isn't a code gap.

---

## 1. Component architecture — what exists and how it coordinates today

### 1.1 The pipeline, end to end

```
news-ingest ──┐
              ├──► news-api (8080) ──┐
stock-ingest ─┤                      │
              ├──► stock-api (8081) ─┼──► initial-analysis-compute ──► initial-analysis-api (8083)
              │   (adjusted=True         (16 deterministic angles;
              │    by default)            fallback universe explicitly
              │                           documented as a known,
              └──► features-worker ──┴──► features-api (8082)         accepted survivorship-bias
                        (vinu-tools)     (indicators/factors/ML)      limitation — see §1.2)
                                                  │                              │
                                                  ▼                              ▼
                                          strategy-api (8084) ◄──────────────────┘
                                       (YAML rule engine → target weights)
                                                  │
                                                  ▼
                                          simulator-api (8085)
                                 (backtest engine — Monte Carlo permutation,
                                  bootstrap Sharpe CI, walk-forward, stress
                                  test, ADV-capped order sizing)
                                                  │
                                                  ▼
                                          research-api (8087)
                       (generate → backtest → critique → refine; promotion to
                        ACTIVE gated on deflated Sharpe + holdout + stress test)
                                                  │
                                                  ▼
                                         portfolio-api (8090)
                     (correlation matrix + risk-parity allocation across all
                      ACTIVE artifacts — now also re-consulted live, at order
                      time, by OrderGuard — see §1.5)
                                                  │
                          ┌───────────────────────┴───────────────────────┐
                          ▼                                               ▼
                    agent-api (8086)                        portfolio-drawdown-monitor
        (chat/orchestration; OrderGuard now gates            (NEW — polls agent-api's
         on: kill switch, mandate limits, ACTIVE-             /broker/account every 300s,
         artifact status, market hours, portfolio             halts trading via
         concentration/correlation — every check              /broker/halt on breach)
         fails open with a logged warning if its
         upstream service is unreachable)
                          │
                          ▼
                 live-api / live-worker (8091)
     (execution engine — signal-to-order translation now
      generates real close orders, TWAP or VWAP execution,
      real portfolio value from account equity, submits
      through agent-api's /broker/order — which itself goes
      through TradeTool/OrderGuard, not a bypass. Implemented
      and tested against Alpaca's documented API; not yet run
      against a real account — see §1.6)
```

All seventeen services above run continuously via `docker-compose.yml` (`restart: unless-stopped`).
`portfolio-drawdown-monitor` is new since status-2 — the automated kill-switch trigger that was
previously just a transport with nothing calling it.

### 1.2 Data layer — survivorship bias now explicit, point-in-time audited

Same layer as status-2 (`vinu-news`, `vinu-stock-price`, `vinu-tools`, `vinu-initial-analysis` with 16
angles). Two things resolved since:

- **Survivorship bias** (7 mega-cap fallback universe) — was flagged, unassigned, since status-2.
  Decision made: accept it for now rather than expand, and make it loud instead of silent. The
  fallback in `vinu-initial-analysis/vinu_initial_analysis/cli.py::_resolve_tickers()` now logs
  explicitly when it's used, with a comment pointing back to this decision. Turned out the universe
  was never actually hardcoded — `vinu-stock-price` already has a real, dynamically configurable
  watchlist (`GET`/`POST`/`DELETE /watchlist/tickers`); the 7 names are only what's used when that
  watchlist is empty. Expanding later needs no new code.
- **Point-in-time data discipline** — audited, not just flagged. News/event angles
  (`news_price_causality`, `event_study_methodology`, `news_first_analysis`) key off each article's
  actual source-reported publish timestamp, confirmed by reading the Yahoo/Alpaca provider code, not
  an ingestion/scrape time. Indicator computation has no look-ahead (checked for centered rolling
  windows and misused negative `.shift()` — the only ones found are legitimate forward-return labels
  for factor decay evaluation, not live signal leakage). One loose thread, not live: two fundamentals
  factors (`fund_earnings_yield`, `fund_roe`) claim "PIT-safe" in their docstrings but have no data
  source wired in anywhere and appear in none of the three presets actually used in production —
  unreachable dead code today, flagged so the claim isn't trusted blindly if fundamentals get wired in
  later.

### 1.3 Strategy layer — unchanged since status-2

No changes in this review round. Deflated Sharpe, holdout, stress testing, and the promotion gate all
remain as described in status-2-architecture-and-status.md §1.3.

### 1.4 Portfolio layer — kill switch fixed, now consulted live at order time

**What changed:** `vinu-portfolio`'s circuit breaker was flagged in status-2 as "reimplements the
kill-switch path instead of importing it" — investigating further, the actual bug was worse: every
service in `docker-compose.yml` runs with its own private `tmpfs` mount at `/tmp`, so even a *correct*
shared import of the file path would never have worked — touching a file inside `portfolio-api`'s
container was never visible to `OrderGuard` checking that same-looking path inside `agent-api`'s
container. Fixed properly: agent-api now exposes `POST /broker/halt` / `POST /broker/resume` /
`GET /broker/status`, and `PortfolioDrawdownMonitor` calls that over HTTP instead of touching a local
file. It was also, separately, dead code — nothing called `.update()`. A new
`portfolio-drawdown-monitor` service now does, polling account equity via a new `GET /broker/account`
route every 300s.

**Also new:** `vinu-portfolio`'s correlation matrix and target weights are no longer just a
construction-time input — `OrderGuard._check_portfolio_concentration()` re-fetches them at the moment
an order is about to fire and rejects buy orders that would breach a configured concentration or
correlation limit. This closes status-2's explicitly-parked gap ("not yet consulted at order time") —
it was parked pending `vinu-live`'s execution path being real, which it now is (§1.6).

### 1.5 Orchestration layer — vinu-agent, now the single enforcement point for every safety check

`OrderGuard.check()` now runs, in order: kill switch, ticker allow/blocklist, short-selling
permission, order value, daily order count, position-percentage of equity, capital-utilization
percentage, **ACTIVE-artifact status** (new in status-3 — rejects orders for symbols with no strategy
that cleared the promotion gate), **market-hours** (new — rejects orders while the market is closed,
via Alpaca's clock endpoint), **portfolio concentration/correlation** (new, described above), daily
trade volume. Every broker/service-dependent check fails open with a logged warning if its upstream
is unreachable — a deliberate, consistent posture across all of them, not decided per-check.

`AlpacaBroker.submit_order()` now also supports real bracket/OTO orders
(`take_profit_price`/`stop_loss_price`), exposed through `TradeTool` — the trade plan's exit checklist
can now become an actual resting order at entry time, not just text in a generated document.

`generate_trade_plan`'s entry checklist item 4 ("volume/volatility") — previously a hardcoded
`PENDING` stub that looked like a real check but wasn't — now computes a real signal from recent bars:
volume vs. trailing average, and recent return volatility vs. a longer baseline.

### 1.6 Execution layer — vinu-live, all five known bugs fixed

status-2 described this layer as "exists now, but is intentionally not load-bearing" with five listed
bugs. All five are fixed and tested this round:

- **Nonexistent agent-api routes.** `/broker/order`, `/broker/positions`, and `/prices/{symbol}` were
  all called but none existed. Added `GET /broker/positions` and `POST /broker/order` to agent-api —
  the order route deliberately delegates to `TradeTool.execute()` rather than calling the broker
  directly, so `vinu-live`'s orders inherit every `OrderGuard` check above, not a second, weaker path
  around them. Price fetching now goes to `vinu-stock-price` directly, since agent-api owns the broker
  connection, not price data.
- **No close-order generation.** `SignalTranslator.translate()` only ever looped over target weights;
  a symbol dropped from a strategy's targets was never sold. Now generates a real close instruction.
- **Hardcoded portfolio-value fallback.** Was `sum(...) or 1_000_000.0` — silently fabricated a
  million-dollar balance whenever that sum was falsy, including the ordinary zero-positions case. Now
  reads real account equity via `/broker/account`, with an explicit, logged, configurable fallback.
- **TWAP-only.** Added real VWAP — `compute_volume_profile()` buckets historical intraday volume by
  each day's relative session position, `plan_vwap()` slices orders weighted by it, falling back to
  equal weights per-symbol whenever volume data is missing.
- **`--interval` flag ignored.** Root-caused: the `vinu-live-worker` console-script entry point
  (`pyproject.toml`) calls `worker_main` directly, and pip's generated wrapper invokes that with zero
  arguments — `sys.argv` was never parsed on that path. Fixed.

**What this means in practice:** `vinu-live` is now implemented and tested against Alpaca's
documented, stable API contracts (bracket orders, the clock endpoint, positions, orders) using mocked
responses — the same rigor as every other broker-dependent piece of this codebase. It has not run
against a real account, because none exists. That's the one remaining gap in this entire series of
review documents, and it's not something further code changes can close.

---

## 2. Aims achieved so far (by stage) — updated

| Stage | Aim | Status |
|---|---|---|
| Data ingestion | Add a ticker → auto-backfill OHLCV + news, split/dividend-adjusted | ✅ |
| Feature/factor compute | Auto-compute indicators/factors for any watchlist ticker | ✅ |
| Market structure analysis | Auto-compute 16 deterministic angles per ticker | ✅ (survivorship-bias scope explicitly documented) |
| Deterministic strategy authoring | Human/AI writes YAML rules, gets weights + backtest | ✅ |
| Generative strategy research | LLM proposes + iteratively refines a strategy against real backtests | ✅ |
| Strategy statistical validity | Multiple-testing-corrected confidence before trusting a Sharpe | ✅ cumulative per symbol |
| Promotion to ACTIVE capital | Gated on more than a human clicking approve | ✅ deflated Sharpe + holdout + stress test |
| Portfolio construction | Capital allocated across strategies with correlation awareness | ✅ |
| Analysis-to-execution gate | Order rejected unless the symbol has a promoted (ACTIVE) strategy | ✅ built this round |
| Capital/liquidity guardrails | Cap total capital deployed and per-order size vs. ADV | ✅ |
| Stop-loss enforcement | Exit levels placed as a real resting order, not just documentation | ✅ built this round |
| Automated kill-switch | Portfolio drawdown halts trading without a human touching a flag file | ✅ built this round |
| Market-hours check | Orders rejected while the market is closed | ✅ built this round |
| Portfolio-level pre-trade enforcement | Correlation/concentration re-checked at the moment an order fires | ✅ built this round |
| Execution engine (`vinu-live`) | Signal → order → close, TWAP/VWAP, real portfolio sizing | ✅ implemented and tested against documented API contracts |
| Trading against a real (paper) account | Any of the above verified against live behavior, not mocks | ❌ — no broker account exists; not a code gap |

---

## 3. What's still short

There is exactly one item left across status-2 through status-5, and it isn't a code gap: **no
broker/paper-trading account exists.** Every check, route, and execution path described above is
implemented and unit-tested against Alpaca's documented API contracts and mocked responses — the same
standard applied throughout this codebase — but none of it has executed against real account data or
placed a real order. That's an external prerequisite, not something addressable by further
implementation work, and it's the next action when you're ready to take it.
