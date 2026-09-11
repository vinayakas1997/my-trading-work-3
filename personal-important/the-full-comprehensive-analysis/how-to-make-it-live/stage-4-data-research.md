# Stage 4 — Data-Source Research (2026-09-09)

Companion to `how-to-make-it-live.md`. Stages 1–3 are code-complete; Stage 4 items
are the ones that "need a new data feed, a new service, or an architecture change."
This file answers: **which of them are actually data problems, what the repos here
already give us, what Alpaca provides, and what to buy/pull from the web for the
rest.**

Method: (1) grepped every doc + the reference repos under
`personal-important/other-reference-repos/`; (2) checked Alpaca's live 2026 docs;
(3) web-searched the remaining gaps. Sources at the bottom.

---

## 0. First split — data vs. not-data

| # | Stage 4 gap | Really a data problem? |
|---|---|---|
| 2 | Event risk (earnings / FDA / corp actions / borrow) | **Yes** — needs a calendar/events feed |
| 13 | Liquidity / spread gate | **Yes** — needs quote/orderbook data (not just bars) |
| 14 | Broker fallback + outage pause | **Half** — the *abstraction* is already built (see §2); needs a 2nd provider + failover logic |
| 26 | Borrow / dividend / tax modeling | **Yes** — needs borrow-rate + dividend (or funding-rate) data |
| 25 | 1D/1H timeframe sleeves | No — portfolio architecture change, no new data |
| 29 | Secrets vault | No — infra (Vault / AWS Secrets Manager) |
| 33 | OOD detector + emergency flatten | No — new detector + action path over data we already have |
| 32 | Broader learning loop | No — training pipeline |
| 35 | Sub-90s reconciliation | No — event-driven architecture change |

So **4 of 9 Stage 4 items are data-acquisition** (#2, #13, #26, and half of #14).
The rest is engineering you can do without buying anything.

---

## 0b. Which asset class? This changes everything

`vinu-components` today is wired for **US equities** (`.env-example` has
`ALPACA_API_KEY`, `POLYGON_API_KEY`, `FMP_API_KEY`; `VINU_PROVIDER_ORDER=alpaca,
polygon,tushare,yahoo`). There is a `crypto-analysis` SKILL but **no crypto
exchange keys and no crypto price ingest**.

If the real go-live target is **ETH / crypto**, the Stage 4 shopping list is almost
entirely different — "earnings / FDA / borrow rate" become "token unlocks / protocol
upgrades / perp funding rate". Both tracks are given below. **Decide this before
spending on data.**

---

## 1. What the repos here already contain (don't rebuild)

### 1.1 Broker abstraction — DONE (`#14` scaffolding)

`unwanted/New-talk-agents/new-restructure/broker-abstraction-implement-test.md`
(built 2026-08-11):

- `vinu-agent/vinu_agent/broker/base.py` — `Broker`, a `@runtime_checkable`
  Protocol: `is_configured`, `get_account`, `get_positions`, `get_orders`,
  `get_clock`, `submit_order`, `cancel_order`.
- `vinu-agent/vinu_agent/broker/factory.py` — `get_live_broker(provider=None)`
  reads `VINU_AGENT_BROKER_PROVIDER` (default `alpaca`) against a `_PROVIDERS`
  registry; unknown provider raises, never silently falls back.
- All 6 production call sites already route through the factory.
- `HistoricalFillBroker` is a proven second implementation of the same shape
  (used for replay).

**What #14 still needs:** (a) one real second provider — implement the 7 Protocol
methods + one line in `_PROVIDERS`; (b) an **outage detector** (`VINU_BROKER_
FALLBACK_URL` / `VINU_OUTAGE_PAUSE_ENTRIES` are documented in `money-gate.md` but
`seceniors.md` §D confirms they were never verified as read in code) that flips
`get_live_broker`'s active provider and pauses *entries* (not exits) when the
primary's `get_clock`/`get_account` errors or lags.

### 1.2 Price-provider failover — planned, not built (`18-data-pipeline.md` gap #3)

Keys for **Alpaca, Polygon, Tushare, FMP** already exist. Missing: a pinned order
+ per-provider lag metric + auto-switch. Knobs already named:
`VINU_STOCK_PROVIDER_ORDER=alpaca,polygon,tushare`,
`VINU_STOCK_FAILOVER_LAG_MULT=3`. Small config + one switch function.

### 1.3 Partial-fill / spread / queue in the simulator (`16-broker-fills.md`)

Knobs already named: `VINU_SIM_SPREAD_BPS`, `VINU_SIM_QUEUE_PCT`,
`VINU_SIM_LATENCY_MS`. NautilusTrader's fill/latency/book models
(`05-other-repos-research.md` #3) are the reference port. This is the *sim* side of
#13 — the *live* gate still needs real quote data (§3).

### 1.4 Reference repos on disk — ready-made methods (not wired, but complete)

`personal-important/other-reference-repos/`:

| Repo | Stage 4 relevance |
|---|---|
| **Vibe-Trading** (`agent/src/skills/`) | Richest. Concrete methods + provider routing for: `perp-funding-basis` (funding-rate regimes, annualized carry, cross-exchange arb — 8h schedule, OKX 00/08/16 UTC), `market-microstructure` (quoted/effective/realized spread, VPIN, Kyle's λ, Amihud, Roll), `liquidation-heatmap`, `okx-market` (order-book depth), `ccxt` (100+ exchanges), `token-unlock-treasury`, `corporate-events`, `earnings-forecast`/`earnings-revision`, `edgar-sec-filings`, `dividend-analysis`, `onchain-analysis`, `stablecoin-flow`. `data-routing/SKILL.md` is a full provider→capability router. |
| **ref-qlib** | Point-in-Time DB + `examples/orderbook_data` — the PIT pattern `18-data-pipeline.md` gap #1 wants. |
| **ref-fincept-terminal** | Terminal-style multi-source aggregation. |

These are *reference implementations to copy the logic from*, not runnable in
`vinu-components` as-is.

### 1.5 `new-vision/other-our-repo-full-research-features/` — the 6 high-star repos

(Real files at `personal-important/new-vision/other-our-repo-full-research-features/`;
the top-level `new-vision/` copy is empty skeleton dirs.)

This folder deep-dives **Qlib, Freqtrade, Nautilus, FinRL, VectorBT, PyPortfolioOpt**
against an *older* "16 pending shortcomings" list — all about **backtest / sizing /
execution quality**, not event-risk / spread / borrow / funding. **None of these six
is a data provider.** What each actually is, and its only Stage-4 bearing:

| Repo | What it is | Stage 4 bearing |
|---|---|---|
| **Qlib** (48K⭐) | PIT database *pattern*, factor mining, ML zoo, RD-Agent | `02-adoptable-logic-catalog.md` row 26: "Qlib Arctic + Orderbook → LOB feature + market-impact beyond Almgren-Chriss" — **marked "only if intraday"**. PIT pattern hardens data *integrity*, adds no new feed. |
| **Freqtrade** (54K⭐) | Crypto bot, hyperopt, lookahead/leak guards, dry-run wallet | Connects exchanges via **CCXT** — the integration library for #14 (2nd crypto venue) and #13 (crypto orderbook). Freqtrade itself = no data. |
| **Nautilus** (29K⭐) | Deterministic engine: fill / latency / **orderbook (book) models**, Parquet catalog, broker adapters | Fill/book models = the **simulator** side of #13 (`costs.py` realism); broker-adapter pattern = a reference for #14. Not a live feed. |
| **FinRL** (16K⭐) | RL agents (A2C/PPO/…), turbulence/VIX feature | `02` row 23: turbulence index → vol-adjusted sizing. Regime feature computed from prices you already have. No new data. |
| **VectorBT** (9K⭐) | Vectorized backtest sweep | Sweep speed only. Irrelevant to Stage 4. |
| **PyPortfolioOpt** (3K⭐) | HRP / Black-Litterman / L2 portfolio opt | Sizing/allocation only. Irrelevant to Stage 4. |

`01-pending-vs-outer-coverage.md`'s own verdict: 11/16 of *those* gaps have outer
coverage, 5/16 are Vinu-specific. **Stage 4 data acquisition is not in that matrix at
all** — that folder answers "how do I make the backtest/sizing/execution mature",
not "where do I get earnings / unlock / funding / borrow data". For the data itself,
§3 below (external APIs) is the answer; these repos only help build the *plumbing*
(CCXT for a venue, Nautilus fill models for sim realism).

The broader 18-repo list (`05-other-repos-research.md`) adds **Lean** (broker adapter
registry: IBKR / Coinbase / Binance / OANDA) and **Hummingbot** (exchange
connectors) — also integration references for #14, still not data sources.

### 1.6 `ref-fincept-terminal/` — checked (Bloomberg-style terminal, C++/Qt6, AGPL-3.0)

A broad **connector aggregator**, not a new data feed. What it actually contains and
its Stage-4 bearing:

| Piece | What it is | Stage 4 bearing |
|---|---|---|
| **Data connectors** (`screens/data_sources/connectors/`) | Registry over the standard providers: Polygon, Finnhub, Tiingo, AlphaVantage, IEX, Nasdaq, Quandl, Marketstack (equities); Binance, CoinGecko, Kraken (crypto); DBnomics/FRED/IMF/World Bank (macro) | Same shortlist as §3. **Confirms** Finnhub/Polygon/Tiingo (equities) and Binance/Kraken/CoinGecko (crypto) as the retail-viable set. No dedicated earnings-calendar / corp-actions connector — it leans on Finnhub/FMP/Polygon for that, plus an EDGAR tool for filings. |
| **Alt-data connectors** (`AlternativeData.cpp`) | RavenPack, Refinitiv Tick History, Bloomberg Second Measure, Thinknum, Orbital Insight, SafeGraph/Placer, Revelio, Earnest Research | All **institutional-priced** — not retail-viable. Ignore. |
| **16 broker adapters** (`trading/brokers/`) behind `BrokerInterface.h` + `BrokerRegistry` | alpaca, **tradier**, **ibkr**, **saxo**, metaapi + 11 Indian brokers | A bigger C++ sibling of vinu's `Broker` Protocol. For **#14**: shows **Tradier / IBKR** as the realistic Western additions alongside Alpaca; its Alpaca adapter hits the *same* endpoints vinu already uses (no extra events/borrow data). |
| **HyperliquidVenue** (`trading/exchanges/hyperliquid/`) | Complete crypto **perpetuals** venue adapter: funding rate (`/info` fundingHistory), L2 order book, EIP-712 on-chain signing (Keccak256) | **The single most useful thing here for an ETH go-live.** One adapter covers **#13 (depth)** + **#26 (funding rate)** + **#14 (2nd venue)** — no API key, no KYC. `ExchangeService::fetch_funding_rate`, `CryptoOrderBook.cpp`, `CryptoDepthChart.cpp`, `CryptoBottomPanel` (funding rate + open interest as first-class UI) are the reference points. |

**License caveat:** AGPL-3.0 (strong copyleft) *and* C++ — do not copy code into
`vinu-components`. Use it as a **reference for which endpoints to call and the
integration shape**, then write clean Python.

**Net:** fincept adds no data source §3 doesn't already name, but its
**Hyperliquid perp adapter** is a concrete, keyless reference that collapses three
crypto Stage-4 gaps (#13/#26/#14) into one integration, and its broker registry
confirms Tradier/IBKR for the equities #14 path.

---

## 2. Alpaca capability matrix (checked against 2026 docs)

| Stage 4 need | Alpaca provides it? | Detail |
|---|---|---|
| **Corporate actions** (splits, dividends, mergers, spinoffs) | ✅ **Yes** | `GET /v1/corporate-actions` (and Broker API `/v2/corporate_actions/announcements`). Historical **and future**. June 2026 added `cas_region` = `us` / `non_us` / `all`. Ingested ~next trading day after declaration. Covers **#2 (corp actions)** and **#26 (dividend calendar)** for US equities. |
| **Earnings calendar** (dates + EPS estimates) | ⚠️ **Weak** | The CA API mentions "earnings" but in practice it's dividends/splits/M&A. No consensus EPS estimate feed. Use Finnhub or FMP (§3). |
| **Economic calendar** (FOMC, CPI, NFP) | ❌ No | Use Finnhub or FMP economic-calendar endpoints, or FRED for the series themselves. |
| **FDA / trial calendars** | ❌ No | Niche; biotech-only. Skip unless the universe holds biotech. |
| **Borrow rate / fee for shorts** | ❌ **No rate** | Asset endpoint has `shortable` + `easy_to_borrow` **booleans** only (vinu-live already reads these for the borrow *check*, Scenario 16). No % fee. Use Fintel or ORTEX (§3), or just IBKR if you add it as the 2nd broker. |
| **Real-time quotes → bid/ask spread** | ✅ **Yes** | Equities: `/v2/stocks/{sym}/quotes/latest` + snapshots (IEX free, SIP paid). Crypto: `/v1beta3/crypto/{loc}/latest/quotes`. Both give NBBO/best bid-ask → quoted spread directly. Covers **#13** at the top-of-book level. |
| **Order-book depth (L2)** | ✅ Crypto / ❌ equities (retail) | Crypto: **L2 orderbook streaming for 20+ coins incl. ETH** (`/v1beta3/crypto/.../latest/orderbooks`, websocket `orderbooks`), data from Alpaca + Kraken venues. Equities: no true depth on the retail data plan — quoted spread only. |
| **Crypto perp funding rate** | ❌ No | Alpaca crypto is **spot only** (Alpaca + Kraken). No perpetuals ⇒ no funding rate. Use Coinglass / CoinAPI / Xoomar (§3). |
| **News (event proxy)** | ✅ Yes | Alpaca News API (Benzinga-sourced), real-time websocket + historical. `vinu-news` service already exists — a reasonable stand-in for "something happened" event risk without a structured calendar. |
| **Broker failover** | ❌ No | No built-in redundancy. Needs a 2nd provider (§4). |

**Bottom line on Alpaca:** it covers **corp actions + dividends + spread (top of
book) + crypto L2 + news** out of the box. It does **not** cover earnings/economic
calendars, borrow *rates*, or crypto funding rates — those are the real buys.

---

## 3. Recommended external data sources per gap

### Track A — US equities

| Gap | Source | Tier | Notes |
|---|---|---|---|
| #2 earnings calendar + EPS | **Finnhub** `/calendar/earnings` | Free 60 req/min | Also has `/calendar/economic`, IPO calendar, insider tx. Cleanest free option. |
| #2 economic calendar | **Finnhub** or **FMP** `economics-calendar` | Free / low | FRED (`FRED_API_KEY`) for the raw series if you want to compute surprises. |
| #2 corp actions / #26 dividends | **Alpaca** CA API | Included | Already have the key. No new integration cost. |
| #26 borrow fee (only if shorting) | **Fintel.io** API or **ORTEX** | Paid (~$30–100/mo) | Sourced from exchanges/FINRA. Or skip shorting v1 and the whole gap goes away. |
| #13 spread gate | **Alpaca** quotes/snapshots | Included (SIP paid for full-tape) | IEX free tier is enough for a max-spread reject; SIP if you need true NBBO. |
| #14 2nd broker | **Alpaca Broker API** is the primary; **IBKR** (`ib_insync`/Web API) or **Tradier** as the failover | IBKR: funded acct; Tradier: $10/mo sandbox-free | IBKR also solves the borrow-rate gap (it publishes fees). |

### Track B — ETH / crypto (if that's the real target)

| Gap | Source | Tier | Notes |
|---|---|---|---|
| #2 event risk → token unlocks | **CoinGecko** token-unlocks (free tier) / **CryptoRank** / scrape `defillama.com/unlocks` HTML | Free | ⚠️ **DefiLlama's `/unlocks` *API* endpoint is Pro-only ($300/mo)** — the free `api.llama.fi` has 31 endpoints, unlocks is not one of them. The *website* is free to read/scrape. CoinGecko's free tier covers upcoming-unlock date + % of supply. For ETH specifically this barely matters (no meaningful unlock schedule) — it's for alt-coins. |
| #2 event risk → protocol upgrades / hard forks / listings | **CoinGecko** `/events` + Alpaca crypto **news** feed | Free / included | No clean structured "hard fork calendar"; news + a manual no-trade date list is the pragmatic interim (same pattern `how-to-make-it-live.md` suggests for equities #2). |
| #2 macro (FOMC/CPI still move ETH) | **Finnhub** `/calendar/economic` | Free (60 req/min) | Crypto is highly macro-sensitive; keep this even on the crypto track. |
| #13 spread + depth | **Binance public** `/api/v3/depth` + **Bybit public** — full order book, **no key** / or **Alpaca crypto L2 orderbook** (ETH, 20+ coins, free) | **Free, no key** | Binance spot public API = 6000 req/min, futures 2400/min, no auth for market data; full depth + trades + OHLCV. CCXT wraps Binance/OKX/Kraken/Coinbase behind one interface. `market-microstructure` skill has the spread/VPIN math. |
| #26 perp funding rate (only if perps/leverage) | **Binance** `/fapi/v1/premiumIndex` + `/fapi/v1/fundingRate`, **Bybit** public, or **ByKaranteli** free JSON (no key) — aggregated. Also **Hyperliquid** `/info` (keyless, from the fincept adapter, §1.6) | **Free, no key** | `perp-funding-basis` skill has regime-classification + annualized-carry. **Spot ETH only ⇒ this gap is ~zero** (no funding, no borrow, no dividend — just exchange fee + spread). |
| #14 2nd venue | **CCXT** (Binance/OKX/Kraken/Coinbase, free) or **Hyperliquid** (keyless perp DEX, adapter reference in `ref-fincept-terminal`) | **Free** | Maps onto the existing `Broker` Protocol — implement 7 methods, add one `_PROVIDERS` line. Freqtrade/Hummingbot/Lean all do this via CCXT. |

---

## 3b. What is actually FREE — the short list

**Fully free, no API key, generous limits (best value):**

| Need | Source | Free-tier reality |
|---|---|---|
| Crypto price / **depth / order book** / OHLCV / open interest | **Binance public REST + WS** (`api.binance.com`, `fapi.binance.com`) | 6000 req/min spot, 2400/min futures, 5 WS conns/IP. No key for any market data. **Bybit / OKX / Kraken** similar. |
| Crypto **funding rate** (perps) | **Binance** `premiumIndex` / `fundingRate`, **Bybit** public, **ByKaranteli** free JSON, **Hyperliquid** `/info` | All keyless. |
| Crypto **L2 order book** (if staying on Alpaca) | **Alpaca crypto market-data** (`v1beta3`) | Crypto data is **free** on Alpaca — no SIP/subscription concept for crypto. L2 for 20+ coins incl. ETH. |
| Crypto prices, market cap, **token unlocks (basic)**, categories | **CoinGecko** free | 30 req/min, no key for basic endpoints. **CoinCap** = 200 req/min, no key. |
| **Corporate actions** (splits, dividends, mergers, spinoffs) — equities | **Alpaca Corporate Actions API** | Included with the account you already have. |
| Equities **quotes → spread** | **Alpaca** IEX quotes/snapshots | Free (IEX tape). SIP (full NBBO) is the paid upgrade — not needed for a max-spread reject. |
| Equities **news** (event proxy) | **Alpaca News API** | Free, real-time WS + historical. `vinu-news` already exists. |
| Macro series (FRED) | **FRED API** | Free with a free `FRED_API_KEY`. |

**Free tier exists but limited (usable with care):**

| Need | Source | Limit |
|---|---|---|
| **Earnings calendar** + dates, **economic calendar**, news sentiment, transcripts — equities | **Finnhub** | **60 req/min free** — the best free equities-event source. Cache aggressively; you only need a daily pull. |
| Earnings / dividend / splits **calendars** — equities | **FMP** free tier | ~250 req/day historically; splits + dividend + earnings calendars are on the free tier. |
| Dividend history + corporate-events calendar — equities | **EODHD** free | 1 year of dividend history, limited calls. |
| Technical indicators, basic quotes | **Alpha Vantage** free | **25 req/day, 5/min** — too tight for calendars; only for indicators. |

**No meaningful free tier (paid only) — and when you actually need it:**

| Need | Source | Cost | Needed only if… |
|---|---|---|---|
| Equity **borrow fee / rate** for shorts | **Fintel** API / **ORTEX** | ~$30–100/mo | …you short equities. Skip shorting v1 ⇒ gap gone. (IBKR as 2nd broker also publishes borrow fees for free once you have an account.) |
| Aggregated multi-exchange funding **history** | **Coinglass** / **CoinAPI** paid tiers | ~$30–80/mo | …you want cross-exchange funding arb. Single-venue funding from Binance/Bybit direct is free. |
| **DefiLlama token-unlocks API** endpoint | DefiLlama Pro | $300/mo | …you trade many alt-coins and need it programmatically. For ETH: not needed. Scrape the free website or use CoinGecko. |
| Full-tape US equities (SIP) | Alpaca / Polygon paid | $99+/mo | …you need true consolidated NBBO. IEX free is fine for a spread gate. |

**For a spot-ETH go-live specifically: everything you need is free.** Binance/Bybit
public API (or Alpaca crypto) covers price + depth + spread; there is no
borrow/dividend/funding cost on spot; Finnhub free covers macro; token unlocks are
irrelevant for ETH. The only thing you'd ever pay for is cross-exchange funding
history or SIP equities data — neither is on the ETH critical path.

---

## 4. Suggested order (cheapest / highest-safety first)

1. **#14 outage detector + pause-entries** — no new data, uses the broker
   abstraction that already exists. Detect: `get_clock`/`get_account` error or
   stale > `VINU_BROKER_FALLBACK_LAG_MULT × poll`; action: pause entries (exits
   still go), alert. A *second provider* can come later — the pause alone removes
   the single-point-of-failure risk `seceniors.md` rates CRITICAL.
2. **#13 spread gate (lightweight)** — one `GET latest quote` before `_maybe_enter`
   places an order; reject if `(ask-bid)/mid > VINU_LIVE_MAX_SPREAD_BPS`. Data is
   **already available from Alpaca** (equities quotes or crypto L2). This is
   arguably a Stage 3-sized change now that the data question is answered.
3. **#2 calendar feed** — a `vinu-news`-adjacent poller: **Finnhub free** (equities
   earnings + economic calendar) or **Finnhub economic + CoinGecko** (crypto — macro
   matters, unlocks don't for ETH). One daily pull, cached. Expose
   `GET /events/{symbol}` → `{next_earnings, next_macro, blackout: bool}`;
   `_maybe_enter` pauses entries inside a blackout window. **All free.**
4. **#26** — only if you short (equities → Fintel/ORTEX, paid) or use perps/leverage
   (crypto → Binance/Bybit funding, free). **Spot-ETH go-live defers this entirely.**
5. **#29 secrets vault**, **#33 OOD flatten**, **#35 event-driven recon**,
   **#25 sleeves**, **#32 learning loop** — engineering, no data dependency, own
   timeline.

---

## Sources

- [Alpaca — Corporate Actions API reference](https://docs.alpaca.markets/us/reference/corporateactions-1)
- [Alpaca blog — Corporate Actions API: Announcements](https://alpaca.markets/blog/introducing-corporate-actions-api-announcements/)
- [Alpaca changelog — global corporate actions (2026-06-03)](https://docs.alpaca.markets/us/v1.1/changelog/2026-06-03-market-data-9dddd18)
- [Alpaca — Real-time Crypto Data (orderbooks, quotes)](https://docs.alpaca.markets/us/docs/real-time-crypto-pricing-data)
- [Alpaca — Visualizing Orderbook Data with the Crypto API (L2, 20+ coins)](https://alpaca.markets/learn/visualizing-orderbook-data-with-alpaca-crypto-api)
- [Alpaca — Crypto Spot Trading docs](https://docs.alpaca.markets/docs/crypto-trading)
- [Finnhub — Earnings Calendar API](https://finnhub.io/docs/api/earnings-calendar)
- [Finnhub — Economic Data / Calendar API pricing](https://finnhub.io/pricing-economic-data-api)
- [Financial Modeling Prep — Earnings Calendar API](https://site.financialmodelingprep.com/developer/docs/stable/earnings-calendar)
- [Financial Modeling Prep — Economic Data Releases Calendar API](https://site.financialmodelingprep.com/developer/docs/stable/economics-calendar)
- [Fintel — Short interest / borrow-rate API](https://fintel.io/ss/us/api)
- [ORTEX — live short-interest / borrow data & API](https://public.ortex.com/)
- [CoinAPI — historical crypto funding rates API](https://www.coinapi.io/blog/historical-crypto-funding-rates-api-coinapi)
- [Xoomar — free crypto funding-rates JSON API](https://xoomar.com/markets/funding-rates)
- [CoinGlass — funding rate tracker](https://www.coinglass.com/FundingRate)
- [DefiLlama — Token Unlocks (website)](https://defillama.com/unlocks) · [DefiLlama Pro API pricing ($300/mo — unlocks is Pro-only)](https://docs.llama.fi/pro-api)
- [CoinGecko — Incoming Token Unlocks](https://www.coingecko.com/en/highlights/incoming-token-unlocks)
- [CoinGecko — Best Free Crypto APIs 2026 (keyless access, free plans)](https://www.coingecko.com/learn/best-free-crypto-api)
- [Binance API rate limits — public market-data endpoints, no key](https://terminalfeed.io/blog/free-apis-2026)
- [ByKaranteli — free crypto derivatives JSON API (funding, OI, no key)](https://bykaranteli.com/developers)
- [Finnhub — free tier 60 req/min (calendars, news, sentiment)](https://tradingdatacompare.com/providers/finnhub/)
- [Alpha Vantage — free tier 25 req/day, 5/min](https://alphalog.ai/blog/alphavantage-api-complete-guide)
- [FMP — free API for stock splits & corporate actions](https://site.financialmodelingprep.com/how-to/how-to-track-stock-splits-and-corporate-actions-with-a-free-api)
- [EODHD — corporate actions (splits & dividends) API, free dividend history](https://eodhd.com/financial-apis/api-splits-dividends)
