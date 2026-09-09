# Stage 4 — Implementation Plan (fetch → store → use)

Companion to `stage-4-data-research.md` (which data, from where, cost). This file is
**how to wire it into `vinu-components` efficiently.** Assumes spot-ETH or US-equities
go-live; both tracks noted. All data is $0 for spot ETH (see research §3b).

---

## 0. The one architectural rule

> **Pollers write to a local store. The live loop reads locally. No external API
> call inside `orchestrator.cycle()` — except the single at-order-time depth check.**

`cycle()` runs every 90s and is the critical path to placing an entry *and to pulling
an exit*. A slow or rate-limited third-party API must never be able to stall a trade
or a stop. So: calendars and funding are **daily / 8-hourly background writes** to
SQLite; the loop reads them over the local Docker network (cheap); microstructure is
fetched **only when an order is about to be placed**, behind a 5-second cache.

---

## 1. Components — what to add vs extend

| Concern | Where | New / extend | Size |
|---|---|---|---|
| Event calendars (earnings, macro, token unlocks) | **new `vinu-events`** micro-service (copy the `vinu-news` skeleton: `feed_poller.py` + `server/app.py` + one SQLite table) | new, small | ~2–3 d |
| Spread + L2 order-book depth | **extend `vinu-stock-price`** — add `/stock/quote/{sym}` + `/stock/orderbook/{sym}` | extend | ~1 d |
| Funding rate (perps only) | worker inside `vinu-events` (8h poll) | extend | ~1 d |
| 2nd venue / broker | **`vinu-agent/broker/`** — new provider class + one line in `factory.py._PROVIDERS`; abstraction (`Broker` Protocol, `get_live_broker`) already exists | extend | ~2–4 d / provider |
| Broker outage detector + pause | **`vinu-live/orchestrator`** — `_check_broker_health()` in `cycle()` | extend | ~0.5 d |

Compose: `vinu-events` gets a service block mirroring `news-api` (same `env_file:
.env`, a bind-mounted `./data/events`, `depends_on: [stock-api]` for the watchlist).

---

## 2. Per-gap: fetch → store → consume

### #13 — Liquidity / spread gate  ·  ✅ **DONE 2026-09-09** (see CHANGES §S4-13)

> Implemented as described below, minus the optional depth check (deferred).
> New `vinu_stock/providers/quote.py` + `StockService.get_quote()` (5s TTL cache)
> + `GET /stock/quote/{symbol}`; `orchestrator._maybe_enter` gains
> `MAX_SPREAD_BPS` (`VINU_LIVE_MAX_SPREAD_BPS`, default 25) →
> `entry_blocked_by_wide_spread`. Entries only, fail-open. +8 tests
> (stock-price 48 pass, vinu-live 215 pass, 0 regressions).

**Fetch** — add to `vinu-stock-price/vinu_stock/`:
- `providers/quote.py` → `get_quote(symbol) -> {bid, ask, mid, spread_bps, ts}`
  - equities: Alpaca `GET /v2/stocks/{sym}/quotes/latest`
  - crypto: Alpaca `GET /v1beta3/crypto/us/latest/quotes` **or** Binance
    `GET /api/v3/ticker/bookTicker` (keyless)
- `providers/orderbook.py` → `get_orderbook(symbol, depth=10) -> {bids, asks, ts}`
  - crypto: Alpaca L2 `/v1beta3/crypto/us/latest/orderbooks` **or** Binance
    `GET /api/v3/depth?limit=20`
- routes: `GET /stock/quote/{symbol}`, `GET /stock/orderbook/{symbol}?depth=N`
- **in-process 5 s TTL cache** (`{symbol: (payload, monotonic_ts)}`) so a burst of
  order-time checks collapses to one upstream call.

**Store** — none. Real-time only; the in-memory TTL cache is the whole "store".

**Consume** — `vinu-live/orchestrator._maybe_enter`, right after the signal-conflict
guard, before sizing:
```python
if MAX_SPREAD_BPS > 0:
    q = await self._http.get(f"{stock_api}/stock/quote/{symbol}")
    if q ok and q["spread_bps"] > MAX_SPREAD_BPS:
        return {"symbol": symbol, "action": "entry_blocked_by_wide_spread",
                "reason": f"spread {q['spread_bps']:.1f}bps > {MAX_SPREAD_BPS}"}
```
Optional depth check: if `order_qty > MAX_BOOK_PCT × sum(top-N ask/bid qty)` → shrink
`size_pct` to fit or block. (`market-microstructure` skill has the impact formula.)
- **Exits / reduces: never gated** — log only, same as the data-freshness guard.
- Fail-open: quote fetch error ⇒ proceed.
- Knobs: `VINU_LIVE_MAX_SPREAD_BPS=25` (0 disables), `VINU_LIVE_MAX_BOOK_PCT=0.10`.
- Tests: `TestSpreadGate` in `test_trade_plan_orchestrator.py` — wide spread →
  `entry_blocked_by_wide_spread`, `post_mock.call_count == 0`; tight spread → enters;
  quote unavailable → enters (fail-open); `MAX_SPREAD_BPS=0` → enters.

### #14 — Broker fallback + outage pause

**Half A — outage detector — ✅ DONE 2026-09-09 (see CHANGES §S4-14A):**

> Implemented as below. `_check_broker_health()` runs once per `cycle()` before
> the plan loop; `BROKER_STALE_SEC` (`VINU_LIVE_BROKER_STALE_SEC`, default 180,
> 0 disables); `self._broker_degraded` → `_maybe_enter` returns
> `entry_blocked_by_broker_outage`; exits never gated; auto-clears on the next
> healthy probe. +7 tests, vinu-live 222 pass, 0 regressions. Half B (2nd
> venue) still pending.

`vinu-live/orchestrator._check_broker_health()`, called once per `cycle()` (like
`_reconcile_book_with_broker`):
- `GET {agent_api}/agent/broker/account`; on success stamp
  `self._broker_ok_at = monotonic()`.
- If it errors **or** `monotonic() - self._broker_ok_at > BROKER_STALE_SEC` →
  `self._broker_degraded = True`.
- `_maybe_enter` checks `self._broker_degraded` first thing → returns
  `entry_blocked_by_broker_outage`. **Exits / reduces still route through** (same
  entries-only shape). Auto-clears on the next successful health call.
- Knob: `VINU_LIVE_BROKER_STALE_SEC=180` (0 disables).
- Tests: health route 500 for N calls → next `_maybe_enter` blocked; exit still fires;
  health recovers → entries resume.

**Half B — second provider — FUTURE CONSIDERATION (out of scope, decided 2026-09-09).**
Not part of equities v1. Accepted interim risk: with Alpaca fully down there is no
exit path (Half A only pauses *entries*). Revisit post-launch. Sketch kept below.
- implement the 7 `Broker` methods in `vinu-agent/broker/<name>.py`
  (`is_configured, get_account, get_positions, get_orders, get_clock, submit_order,
  cancel_order`).
- register: `factory.py._PROVIDERS["tradier"] = TradierBroker`.
- `VINU_AGENT_BROKER_ORDER=alpaca,tradier`; `get_live_broker()` walks the list,
  returns the first `is_configured()` + healthy one.
- Candidates: **Tradier** (equities, free sandbox), **CCXT** or **Hyperliquid**
  (crypto — Hyperliquid needs no key/KYC, adapter shape is in `ref-fincept-terminal`).

### #2 — Event risk (calendars)  ·  ✅ **DONE 2026-09-09** (see CHANGES §S4-2)

> **Built inside `vinu-stock-price`, not as a new `vinu-events` service** —
> `vinu_stock/events/` (store + Finnhub provider + poller), `GET /stock/events/{symbol}`,
> daily refresh hooked into the existing ingest-worker loop. `vinu-live`
> `_maybe_enter` gains `EVENT_BLACKOUT_HOURS` (`VINU_LIVE_EVENT_BLACKOUT_HOURS`,
> default 24) → `entry_blocked_by_event_blackout`. Entries only, fail-open,
> inert without `FINNHUB_API_KEY`. +19 tests (stock-price 61, vinu-live 228),
> 0 regressions. Rationale for folding it in: no new image / Compose block /
> healthcheck for one table + one poller + one route.

**Fetch** — `vinu-events` worker loop, one pass at ~00:30 UTC daily:
- equities: Finnhub `GET /calendar/earnings?from&to` (next 30 d) for each watchlist
  symbol; `GET /calendar/economic` for a fixed macro set (FOMC / CPI / NFP / PCE).
- crypto: CoinGecko `GET /coins/{id}/events`; token-unlock only if the universe holds
  alt-coins (ETH itself has none worth gating).
- Finnhub free = 60 req/min; one batched daily pull is trivial. Back off + retry on
  429; never raise (a bad pull just leaves yesterday's rows).

**Store** — `vinu-events/data/events.db`, table
`events(symbol TEXT, kind TEXT, event_ts REAL, title TEXT, severity INT, pulled_at REAL)`,
bind-mounted `./data/events` (survives restart, same as every other `*.db`).

**Consume** — `GET /events/{symbol}?within_hours=48` → `{blackout: bool, next: [...]}`.
In `_maybe_enter`, after the signal-conflict guard:
```python
if EVENT_BLACKOUT_HOURS > 0:
    ev = await self._http.get(f"{events_api}/events/{symbol}?within_hours={EVENT_BLACKOUT_HOURS}")
    if ev ok and ev["blackout"]:
        return {"symbol": symbol, "action": "entry_blocked_by_event_blackout",
                "reason": ev["next"][0]["title"]}
```
- **Entries only.** Exits unaffected. Fail-open if `vinu-events` is unreachable.
- Knobs: `VINU_LIVE_EVENT_BLACKOUT_HOURS=24` (0 disables),
  `VINU_EVENTS_MACRO_ENABLED=true`.
- Tests: mock events route → `blackout:true` → `entry_blocked_by_event_blackout`;
  `blackout:false` → enters; route down → enters.

### #26 — Funding / borrow cost  ·  **FUTURE CONSIDERATION (out of scope, decided 2026-09-09)**

Not part of equities v1. Perps-only for funding; equity borrow only bites on shorts
and needs a paid data source (Fintel/ORTEX/IBKR fee schedule). Long-only spot
equities do not need it. Splits & dividends are already handled via Alpaca
`adjustment=all` on bars. Sketch kept below for whenever shorts or perps enter scope.
- **Fetch** — `vinu-events` 8-hourly: Binance `GET /fapi/v1/premiumIndex` +
  `/fapi/v1/fundingRate` per symbol → `funding(symbol, rate_8h, annualized, ts)`.
- **Consume** — `vinu-portfolio.compute_daily_allocation`: subtract expected
  annualized funding-against-your-side from the strategy's expected return (a carry
  drag). Optionally in `vinu-live`: dampen `size_pct` when annualized funding against
  your direction > `VINU_RISK_FUNDING_MAX_ANNUALIZED=0.30`. (`perp-funding-basis`
  skill has the regime bands.)
- Equity borrow: same shape, source Fintel/ORTEX (paid) or read IBKR's published fee
  once IBKR is the/a broker.

---

## 3. Efficiency — nothing new on the hot path

| Data | Poll cadence | Cached where | External calls per `cycle()` |
|---|---|---|---|
| Earnings / macro / unlock calendars | 1× / day | `vinu-events` SQLite | **0** — loop reads local `vinu-events` |
| Funding rate | every 8 h | `vinu-events` SQLite | **0** |
| Quote / spread | on demand, **at entry attempt only**, 5 s TTL | in-memory in `vinu-stock-price` | ≤ 1 per *entry attempt* (not per symbol per cycle) |
| L2 depth | same | in-memory | ≤ 1 per entry attempt |
| Broker health | 1× per `cycle()` | — | 1 local `/account` GET (already cheap) |

`cycle()` keeps its current speed: the only added per-cycle cost is one local broker
health GET. Everything else is either a background writer or fires solely when an
order is imminent.

---

## 4. Rollout order

| # | Item | Data source | Effort | Blocks live money? |
|---|---|---|---|---|
| 1 | **#13 spread gate** ✅ done 2026-09-09 | Alpaca (keyed) | ~1 d | Recommended before real capital |
| 2 | **#14 Half A — outage pause** ✅ done 2026-09-09 | none (uses existing `/account`) | ~0.5 d | Recommended before real capital |
| 3 | **#2 events calendar + blackout guard** ✅ done 2026-09-09 (folded into `vinu-stock-price`, not a new service) | Finnhub free | ~2–3 d | Matters for equities (earnings) |
| — | ~~#14 Half B — 2nd venue~~ | — | — | **FUTURE CONSIDERATION** — out of scope for v1 (2026-09-09) |
| — | ~~#26 funding / borrow drag~~ | — | — | **FUTURE CONSIDERATION** — out of scope for v1 (2026-09-09) |
| 4 | **#33 emergency flatten (part 1) + auto-OOD detector (part 2)** ✅ done 2026-09-09 | none (book price history + agent kill switch) | ~1 d | Safety. Part 2 ships DORMANT (`VINU_LIVE_OOD_DETECTOR=off`), graduated activation. |
| — | #25 sleeves, #29 vault, #35 recon, #32 learning | — (no data) | separate track | Post-launch |

**The data-dependent half of Stage 4 is COMPLETE for equities v1** (#13, #14A, #2),
plus the full **#33** panic switch — manual `emergency-flatten` **and** the
dormant auto-OOD trigger. #14B and #26 are deferred by decision. Nothing left in
Stage 4 blocks a paper→live start.

---

## 5. Every consumer follows the Stage 3 guard pattern

(Same shape as the CVaR / data-freshness / signal-conflict guards already in
`_maybe_enter`.)

1. Module constant from env (`VINU_LIVE_*` / `VINU_RISK_*`); `0` / `false` disables.
2. Small helper; **fail-open** — missing/unparseable data returns `None` / passes.
3. Called in `_maybe_enter` **after the existing guard cluster**, before sizing;
   returns an `entry_blocked_by_*` dict *or* scales `size_pct`.
4. **Exits and reduces are never gated** — mirror HALT-entries-only / turbulence /
   cooldown / data-freshness.
5. Test class in `vinu-live/tests/test_trade_plan_orchestrator.py`: blocked case
   (asserts `post_mock.call_count == 0`), pass case, fail-open case, disabled-by-env
   case.

Reuse `_router` / `_make_orchestrator` test helpers; run in Docker against
`vinu-components-live-api:latest` with the source volume-mounted, exactly as the
Stage 3 work was verified.
