# Consolidated Fix Plan

Companion to [status-4.md](./status-4.md) (the full gap list). Splits the 9 remaining gaps into what
can be fixed right now versus what genuinely has to wait on a broker/paper-trading account, so nothing
sits in limbo without a reason attached to it.

---

## Can be done now — no broker account needed

### Priority 1 — Fix `vinu-portfolio`'s kill-switch duplication — DONE
**Turned out more serious than originally scoped.** The original framing ("duplicates the kill-switch
path instead of importing the shared module") understated it: every service in `docker-compose.yml`
runs with its own private `tmpfs` mount at `/tmp` (`tmpfs: [/tmp]` per service). That means even a
*correct* shared import of the file-path constant would not have worked — touching
`/tmp/vinu-trading-halt` inside the `portfolio-api` container was never visible to `OrderGuard`
checking that same-looking path inside the `agent-api` container. They are different filesystems.
It also surfaced that `PortfolioDrawdownMonitor` (the class meant to trigger this) was never
instantiated or called from anywhere — dead code, not just miswired.

**What was actually done:**
1. Added `POST /broker/halt`, `POST /broker/resume`, `GET /broker/status` to agent-api
   (`vinu-agent/vinu_agent/server/routes_broker.py`), wrapping the existing
   `broker/kill_switch.py` functions — the one process that actually enforces the switch now exposes
   it over the network, the way every other cross-service interaction in this codebase already works.
2. `vinu-portfolio/vinu_portfolio/circuit_breakers.py::PortfolioDrawdownMonitor._halt_trading()` now
   calls that endpoint via `httpx` instead of touching a local file. A failed call is logged at ERROR
   level with an explicit "trading is NOT halted" message rather than failing silently.
3. Added `VINU_AGENT_API_URL` to `portfolio-api`'s environment in `docker-compose.yml`.
4. Tests: 5 new in `vinu-portfolio/tests/test_circuit_breakers.py`, 5 new in
   `vinu-agent/tests/test_routes_broker.py`. Full suites: vinu-agent 84/84 passing, vinu-portfolio
   5/5 passing.

**Still open, not done today:** `PortfolioDrawdownMonitor` is still never called by anything — no
scheduled loop feeds it live portfolio values. Wiring that up is effectively the "automated kill-switch
trigger" gap (status-4.md item 6) — and, now that the transport is fixed, it turns out **not** to need
a broker account at all, since portfolio value can come from `vinu-portfolio`'s own computation. Worth
revisiting as a near-term item rather than leaving it parked with the broker-dependent ones.

**What to do:**
1. Read `vinu-portfolio/vinu_portfolio/circuit_breakers.py` and confirm exactly what it reimplements
   from `vinu_agent/broker/kill_switch.py` (`is_trading_halted`, `halt_trading`, the file paths used).
2. Either import `vinu_agent.broker.kill_switch` directly if `vinu-portfolio` can depend on
   `vinu-agent`, or extract the shared halt-file logic into a small standalone module both packages
   depend on if a direct dependency isn't desired between those two services.
3. Add a test that halts trading via one path and asserts the other path sees it.

**Effort:** small.

---

### Priority 2 — Decide and act on survivorship bias — DONE (decision: accept, document)

**Decision made:** accept the survivorship-biased universe for now rather than expand it, and make
that an explicit, documented boundary instead of a silently-forgotten gap.

**Correction to how this was originally scoped:** the 7-mega-cap list was assumed to be a hardcoded
universe. It's actually only a *fallback default* — `vinu-initial-analysis/vinu_initial_analysis/cli.py`
tries `GET /watchlist/tickers` on `vinu-stock-price` first (a real, already-existing, dynamically
configurable watchlist mechanism with `POST`/`DELETE` routes), and only falls back to the 7 names when
that watchlist is empty. So "expand the universe" was already possible without new engineering — it
just needs someone to populate the watchlist. That option stays open later without code changes.

**What was done:** the fallback in `cli.py::_resolve_tickers()` now carries an explicit comment
flagging it as a known, accepted limitation, with a pointer back to this document, and the log message
on the fallback path now says so out loud instead of a generic "using defaults" warning — so hitting
this path is visible in logs, not silent.

---

### Priority 3 — Point-in-time data discipline audit — DONE (audited, nothing to fix in the live path)

**News/event angles — confirmed clean.** `news_price_causality`, `event_study_methodology`, and
`news_first_analysis` all key off `sort_ts`, which traces back to the source's actual publish
timestamp — Yahoo's `_parse_pub_ts(pub_date)` and Alpaca's `_parse_alpaca_ts(created_at)`, both parsed
from the provider's own reported publish time, not an ingestion/scrape time. No look-ahead found here.
(The third configured provider, FMP, is an unimplemented stub returning `[]` — not a live data path,
not a concern.)

**Indicator computation — confirmed clean.** Checked for the two classic look-ahead bugs: centered
rolling windows (`center=True`) and negative `.shift()` used as a live feature. Found none in
`vinu-tools/vinu_tools/compute` or the initial-analysis angles. The only `shift(-N)` usages found
(`bench/runner.py`, `bench/decay.py`, `ml_model_pipeline/compute.py`, `decay_monitoring/compute.py`)
are all legitimate — they build the forward-return *label* for IC/decay evaluation, which by
definition needs to look forward; that's not the same as leaking future data into a live signal.

**Fundamentals factors — not a live bug, but a real, previously-undocumented finding.**
`vinu-tools/vinu_tools/compute/factors/singles/fundamental/{earnings_yield,roe}.py` both claim
"PIT-safe" (point-in-time-safe) in their docstrings, but there is no fundamentals data source wired
into the pipeline anywhere — `FeatureEngine.process()` only ever calls `fetch_candles()` (OHLCV), and
the `fund:net_income` / `fund:shares_diluted` columns these factors require are never populated by
anything. Neither factor appears in any of the three presets actually used in production
(`basic_ta`, `trend_pack`, `alpha158`, per `trade_plan_tool.py`). Net effect: these two factors are
unreachable dead code today, not a live PIT leak — but the "PIT-safe" claim in their docstrings is
unverified and should not be trusted if anyone wires fundamentals data in later without re-checking it
against a real point-in-time-aligned source.

**Verdict:** the currently *active* pipeline (the angles and presets actually used by
`generate_trade_plan` and research) has no point-in-time leak found. The one loose thread is
cosmetic today (dead fundamentals factors with an unverified claim) but worth a one-line docstring
fix so it doesn't get trusted blindly later — flagged, not fixed, since it doesn't affect anything
live.

---

## Parked — needs the broker/paper account first

### Priority 4 — Stop-loss enforcement via bracket orders
Add `order_class`/`stop_loss`/`take_profit` support to `alpaca.py`, and have the trade tool place the
exit levels the trade plan already computes as a real bracket order at entry time.

### Priority 5 — Automated kill-switch triggers
A monitor (same `while True: cycle(); sleep(interval)` pattern as `research-decay-scan`) watching
realized P&L/drawdown against a threshold, calling `halt_trading()` automatically.

### Priority 6 — Market-hours / stale-data check
Call Alpaca's clock endpoint from `OrderGuard.check()`, reject orders when the market's closed, and
check staleness on the price data used to size the order.

### Priority 7 — Fix `vinu-live`'s known execution bugs
Wire it to real agent-api/broker routes, add close-order generation, remove the hardcoded
portfolio-value fallback, add VWAP as an alternative to TWAP-only, respect the `--interval` flag.

### Priority 8 — Portfolio-level correlation/concentration enforcement at order time
Sequenced *after* Priority 7, since it needs a working execution path to protect. Re-check
`vinu-portfolio`'s correlation/concentration state at the moment an order is about to fire, independent
of whatever target weights were computed upstream.

**All five require live Alpaca API access to build against verified real behavior (bracket-order
semantics, the actual clock endpoint, real fills/P&L) rather than assumptions — this is why they wait,
not because they're lower priority in principle.**

---

## Suggested order of work

1. **Priority 1** (kill-switch duplication) — small, fixes a real safety-mechanism bug, do it now.
2. **Priority 3** (point-in-time audit) — needs to happen before Priority 2's decision is fully
   informed, since a point-in-time leak would also affect how much the survivorship-bias fix even
   matters.
3. **Priority 2** (survivorship bias decision) — requires your call; implement whichever direction is
   chosen.
4. **Priorities 4-8** — stay parked until the paper-trading broker account exists, then work through
   them in the listed order (7 before 8, since 8 depends on 7).
