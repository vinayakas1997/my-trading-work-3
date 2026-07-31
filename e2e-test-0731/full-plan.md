---
name: full-plan
status: definition-phase
purpose: single source of truth for the E2E validation plan — what we're testing, with what data, over what period, before any test is actually run
---

# End-to-End Validation Plan (2026-07-31 draft)

**This is a definition document, not a test log.** Nothing described here has
been executed yet. This file exists so that when Stage 1 actually starts, the
scope, dates, tickers, and strategies are already fixed and agreed — no
mid-test scope drift.

## Why this exists

The `steps-to-implement-plan-2` audit (see
`portfoli-mc-improvement/the-skills-plan-new-discussion-2/`) built and
unit-tested every piece of the allocation/game-plan/risk system, but Step 07
(Validation) is explicitly blocked: no real historical data has ever been run
through it, and no paper-trading window has ever been observed. This plan is
the concrete, scoped answer to "how do we actually validate this system
before risking real money."

## The three stages

| Stage | What happens | Capital at risk | Duration |
|---|---|---|---|
| 1 | Full historical simulation against real market data | None | One-off, retrospective |
| 2 | Live paper-trading account (Alpaca paper), system runs for real in real time | None (paper) | ~1 week of market days, results stored, then re-researched |
| 3 | Real-money trading | Yes | Ongoing, after Stage 2 passes review |

This document defines **Stage 1** in full. Stage 2 and 3 are named here for
context but are out of scope for the current definition pass — they get their
own plan once Stage 1 actually produces results.

## Data source

**Alpaca Markets API** — already verified reachable this session (paper
trading account, market data, and news endpoints all returned real data back
to 2022-01-01). Credentials live in `alpaca-details/details.md` and are wired
into `vinu-components/.env` (see
[scope-responsibilities/vinu-stock-price.md](scope-responsibilities/vinu-stock-price.md)
and
[scope-responsibilities/vinu-news.md](scope-responsibilities/vinu-news.md)).

- Trading: `https://paper-api.alpaca.markets/v2`
- Market data: `https://data.alpaca.markets/v2`
- News: `https://data.alpaca.markets/v1beta1`

## LLM source

A local OpenAI-compatible model server running on the host at port 8009
(`qwen36-35B`), used by `vinu-news` (article enrichment), `vinu-research`
(complex-tier strategy generation), and `vinu-agent` (default LLM
provider). Wired into `vinu-components/.env` as
`VINU_LLM_BASE_URL=http://host.docker.internal:8009/v1` — `host.docker.internal`,
not `127.0.0.1`, is required so the three containers that use it
(`news-api`, `research-api`, `agent-api`) can reach a server running on the
host rather than inside their own container; `docker-compose.yml` already
has `extra_hosts: host.docker.internal:host-gateway` set on exactly those
three services for this.

## Time range — locked

- **Start date: 2022-01-01**
- **End date: 2026-06-30**
- No segmentation, no splitting into sub-periods. One continuous historical
  window covering multiple regimes (2022 rate-hike drawdown, 2023-24 recovery,
  through mid-2026).
- Every ticker in scope must have data starting from 2022-01-01 — if a ticker
  IPO'd or has a shorter history, it is not eligible for Stage 1 as currently
  scoped (no backfill-then-truncate logic is planned yet; that's future
  research work, not part of this pass).

## Timeframes

- **Base data: 1-minute OHLCV candles**, fetched from Alpaca via
  `vinu-stock-price`.
- **Aggregated up to: 1-day, 4-hour, 1-hour, 15-minute** bars, derived from the
  1-minute base — not fetched separately. Aggregation happens once, from the
  single 1-minute source, so every higher timeframe is internally consistent
  (no drift between what a "1-day candle" means depending on which endpoint
  produced it).
- 1-minute data itself is not currently present locally in this environment —
  it will be fetched from Alpaca and cached via `vinu-stock-price` before any
  aggregation or simulation runs. This fetch has not happened yet as of this
  document.

## Ticker scope — locked

**Equities only, 3 tickers, chosen for genuinely different behavior so the
regime/tilt/risk logic gets exercised differently per name, not identically
three times:**

| Ticker | Profile | Why |
|---|---|---|
| **AAPL** | Mega-cap tech, steady trend, low-to-moderate volatility | Baseline/easy case — clean trends |
| **TSLA** | High-volatility, large swings, momentum-driven | Stress case for risk budget, regime-tightened bands, probabilistic exits |
| **JNJ** | Defensive, low-beta, historically low correlation to tech | Contrast case — breaks the AAPL/TSLA tech correlation so shock-clustering has something non-trivial to measure |

All three have decades of trading history (well before 2022-01-01) and are
Alpaca-supported.

## Strategies — locked, two tiers run differently from the third

Three difficulty tiers, so the validation exercises both the simple and the
full-complexity paths of the system. **Important architectural finding from
this session:** only the easy and medium tiers fit `vinu-strategy`'s
rule-based YAML DSL (`gt`/`lt`/`eq`/etc. comparisons on precomputed features
and correlation fields — no LLM call is expressible there). The complex tier
runs through a **different service and API entirely**.

| Tier | Strategy | Runs via | YAML file |
|---|---|---|---|
| Easy | 20/50 SMA crossover, bear-regime exit | `vinu-strategy`'s `POST /strategies/{name}/evaluate` | `vinu-components/vinu-strategy/strategies/e2e_easy_sma_crossover.yaml` |
| Medium | SMA trend direction gated by ADX trend-strength + `volatility_20d`/regime volatility filters | `vinu-strategy`'s `POST /strategies/{name}/evaluate` | `vinu-components/vinu-strategy/strategies/e2e_medium_trend_vol_filter.yaml` |
| Complex | LLM forecast + calibrated probabilistic exit | `vinu-research`'s `POST /trade-plan/{symbol}` (real code: `forecast_skill.py`, `trade_plan_authoring.py`, `judgment_store.py`) | **None — not a `vinu-strategy` YAML.** Testing this tier means calling the `vinu-research` endpoint directly and inspecting its output, not writing rule conditions. |

This isn't a gap to "enhance" — deliberately keeping `vinu-strategy`'s
execution layer as a simple, deterministic, auditable rules engine and
keeping LLM-driven forecasting in `vinu-research` is the correct boundary,
not a missing feature. Building a fake LLM-lookalike inside a `vinu-strategy`
YAML (e.g. approximating "forecast" with correlation fields) was considered
and rejected — it would test an approximation nobody actually uses instead of
the real Step 03 probabilistic-exit machinery that already exists.

## What Stage 1 will actually produce

Per component (see each file under
[scope-responsibilities/](scope-responsibilities/) for exact detail):

1. `vinu-stock-price` — fetches and stores real 1-minute candles for
   AAPL/TSLA/JNJ, 2022-01-01 → 2026-06-30, aggregates to the four higher
   timeframes.
2. `vinu-tools` — computes technical/alpha features from that price data.
3. `vinu-news` + `vinu-initial-analysis` — historical news and its
   correlation/impact analysis for the same period and tickers (best-effort;
   depends on how far back Alpaca's news API actually has coverage).
4. `vinu-strategy` — evaluates the easy and medium tier YAMLs into target
   weights per rebalance point.
5. `vinu-simulator` — replays those weights against real price data,
   producing P&L, Sharpe, max drawdown, win rate, Calmar ratio, and a
   comparison against baselines (equal-weight, buy-and-hold benchmark).
6. `vinu-portfolio` — runs the unified daily-allocation / game-plan / risk
   layer on top of the easy and medium strategies together, not just
   per-strategy in isolation.
7. `vinu-research` — runs the complex tier directly via
   `POST /trade-plan/{symbol}` (LLM forecast + calibrated probabilistic
   exit), and separately records artifacts so results are queryable later,
   feeding the "research again" step between Stage 1 and Stage 2.

The concrete numbers from all of the above do not exist yet — this document
defines what will be produced, not the results themselves. Results get
written up separately once Stage 1 is actually executed.

## What this plan explicitly does NOT cover yet

- Stage 2 (paper trading) mechanics — needs `vinu-live` + `vinu-agent`
  broker wiring, deferred per earlier scope decision.
- Stage 3 (live capital) — not planned at all yet, gated on Stage 1 and
  Stage 2 both passing review.
- Backfill/reconciliation logic for tickers with less than the full
  2022-01-01+ history.

## Related documents

- [scope-responsibilities/](scope-responsibilities/) — per-component scope,
  responsibilities, data storage, and dependencies.
- [architecture.md](architecture.md) — full system architecture as a Mermaid
  diagram.
- `portfoli-mc-improvement/the-skills-plan-new-discussion-2/steps-to-implement-plan-2/07-validation.md`
  — the original validation step definition and honest blocked-status record
  this plan supersedes with a concrete scope.
