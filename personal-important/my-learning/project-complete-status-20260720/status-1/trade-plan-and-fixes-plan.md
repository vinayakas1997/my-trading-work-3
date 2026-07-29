# Trade-Plan Generator + Outstanding Fixes — Combined Plan

Companion to [status-1.md](./status-1.md) and [roadmap-fullplan-A-F.md](./roadmap-fullplan-A-F.md).
Those two documents cover the original gap analysis and the six-phase roadmap. Since then, a
separate agent session partially implemented Phases A/B0/B1/B2-B4/C against the real codebase,
and a code review surfaced 12 concrete bugs in that work (see §2). Separately, the actual
near-term goal has narrowed: **no live/paper broker execution yet** — the immediate need is a
pipeline that runs the existing analysis chain and outputs a granular, staged trading plan
document (entry conditions, profit-booking tranches, invalidation/exit conditions) for a human
to act on. This document combines both threads into one place to work from.

---

## 1. Trade-plan generator — what exists, what's missing, the design

### 1.1 What already exists and is reusable

| Capability | Where | On-demand for one symbol? |
|---|---|---|
| Market-structure context (15 angles: `trend_lifecycle`, `trend_session_structure`, `regime_analysis`, `drawdown_deep_dive`, etc.) | `vinu-initial-analysis` (`initial-analysis-api` :8083), `catalog/angles.yaml` | Yes — already the pattern `vinu-research` uses (`ResearchTools.get_angle_context`) |
| TA indicators, Alpha101, Alpha191(GTJA), Fama-French academic factors, fundamental factors, recipes (`alpha158`, `trend_pack`, `momentum`, etc.) | `vinu-tools` (`features-api` :8082) | **Yes, synchronously** — `POST /requests` with `run_immediately=true` + one symbol runs `FeatureEngine.process()` inline (seconds), no scheduled job needed. `GET /features/{symbol}` is a decoy (just proxies stock-api's raw candle fields) — do not use it for real signal. |
| Statistical significance of a strategy's edge | `vinu-simulator`, `engine/validation.py:7` `monte_carlo_permutation()` — shuffles historical trade P&Ls, returns a p-value vs. chance | Yes, if a backtested strategy/run already exists for the symbol |
| Trained-model score | `vinu-tools` ML registry (`compute/ml/models/registry.py`, `runner.py`) | **No** — batch train+evaluate only, no single-symbol inference endpoint exists yet |
| Staged/tranche profit-booking methodology | — | **Does not exist anywhere.** `execution-model` skill's "tranches" concept is about order-slicing, not profit-taking. |
| Invalidation/bad-trade-exit framework | — | **Does not exist anywhere.** `Artifact.entry_rules`/`exit_rules` DB fields exist but are dead — never populated by any generator. |

### 1.2 Design — four tiers feeding one synthesis step

1. **Structural/contextual** — pull the relevant `initial-analysis` angles for the symbol
   (which ones depends on timeframe — for an intraday/15-min plan: `trend_session_structure`,
   `trend_lifecycle`, `regime_analysis`; add `drawdown_deep_dive` for the invalidation side).
2. **Quantitative signal** — call `vinu-tools`' synchronous `POST /requests` with a
   timeframe-appropriate recipe (e.g. `trend_pack` for trend-following, `alpha158` for a
   broader factor read) — real computed values, not the `/features/{symbol}` proxy stub.
3. **Statistical confidence** — if a matching backtested strategy/artifact exists for the
   symbol, pull its `monte_carlo_permutation` p-value from the simulator's validation output;
   otherwise omit this tier rather than blocking on it.
4. **Model score (deferred, additive only)** — new thin `GET /ml/predict/{symbol}` in
   `vinu-tools`, reusing `train_and_predict()` directly, no new persistence layer. Not built in
   v1; the plan generator must work correctly without it.

**New pieces to build:**
- `vinu-agent/skills/trade-plan/SKILL.md` — the methodology skill: how to turn tiers 1–3 into
  (a) an entry checklist, (b) staged profit-booking tranches (LLM picks e.g. 50/30/20 vs.
  40/30/30 based on trend strength from `trend_lifecycle`), (c) an invalidation checklist with
  explicit exit/reduce/hold decisions per condition.
- `vinu-agent/vinu_agent/tools/trade_plan_tool.py` — the tool that gathers tiers 1–3 (HTTP
  calls to initial-analysis-api, features-api, simulator-api — follow the same pattern as
  `research_tool.py`/`portfolio_comparison_tool.py`, read config URLs from `AgentConfig`, do
  **not** hardcode loopback URLs — see finding in §2), feeds the skill's prompt, returns a
  structured JSON + markdown plan document (reuse `run_card.py`'s markdown-rendering pattern,
  not its schema — it's backtest-retrospective, not forward-looking).
- Timeframe (e.g. "15-minute format") is a parameter to the tool, not new data-ingestion
  infrastructure — default to whatever bar granularity `stock-api` already serves; flag this
  as an assumption to confirm once bar-level detail is checked.

**Explicitly out of scope for this piece:** no order submission, no broker calls, nothing
touching `vinu-live`. Output is a document/report only.

---

## 2. Outstanding fixes from the code review

The other agent session's work (Phases A1–A3, B0–B4, C) was reviewed in full — 370 existing
tests pass and the core math (correlation, risk-parity, SQL parameterization) is sound, but 12
concrete bugs were found. Ordered by what actually blocks the trade-plan work vs. what's
purely for later (`vinu-live`/broker, currently paused per your direction):

### 2.1 Relevant now (touch the analysis chain the trade-plan tool depends on)
1. **`vinu-research/vinu_research/cli.py:257,272`** — `run_main` computes an auto-proposed idea
   but then calls `loop.run()` with the original (still-`None`) `args.idea`. Silently defeats
   autonomous hypothesis generation for the `run` subcommand. *Fix: use the computed variable.*
2. **`vinu-research/vinu_research/server/routes_read.py:118`** — `GET /research/artifacts` with
   an invalid `status` value raises an uncaught `ValueError` → 500 instead of 400. *Fix: wrap
   in try/except, return 400 with the bad value.*
3. **`vinu-agent/vinu_agent/tools/portfolio_comparison_tool.py:29`** — hardcodes
   `127.0.0.1:8090`/`127.0.0.1:8087` instead of reading from `AgentConfig.services`; breaks
   under docker-compose networking. *Fix before building `trade_plan_tool.py` — copy the
   correct config-driven pattern instead of repeating this mistake.*

### 2.2 Defer (part of the paused broker/live-execution work)
4. `vinu-live/vinu_live/scheduler.py:108` — calls agent-api routes (`/broker/order`,
   `/broker/positions`, `/prices/{symbol}`) that don't exist; integration is currently inert.
5. `vinu-live/vinu_live/signal_translator.py:53` — never generates close orders for symbols
   dropped to zero target weight.
6. `vinu-live/vinu_live/scheduler.py:65` — falls back to a fabricated $1,000,000 portfolio
   value when position-fetch fails.
7. `vinu-live/pyproject.toml` — `vinu-live-worker` entry point ignores its own `--interval`
   CLI flag (currently masked by a matching default).
8. `vinu-live/vinu_live/execution.py:30` — only TWAP implemented, VWAP missing.
9. `vinu-agent/vinu_agent/server/app.py:13` — Telegram/Discord channel startup reads
   `config.channels`, a field that doesn't exist on `AgentConfig` — dead code, bots never start.
10. `vinu-agent/vinu_agent/broker/order_guard.py:90` — `max_position_pct` ignores existing
    holdings in the symbol and fails open (silently passes) if `broker.get_account()` errors.
11. `vinu-portfolio/vinu_portfolio/circuit_breakers.py:9` — reimplements the kill-switch file
    path directly instead of importing `vinu_agent.broker.kill_switch`; works today by
    coincidence, will drift if the mechanism changes.

### 2.3 Needs a decision, not urgent
12. `vinu-news`/`vinu-stock-price` cycle loops gained an unrelated `sync_and_backfill()`
    watchlist-sync step not traceable to any assigned phase — confirm intentional or flag to
    whoever ran that session.

---

## 3. Suggested order of work

1. Fix §2.1 items 1–3 first — small, and #3's pattern mistake would otherwise get copied
   straight into the new `trade_plan_tool.py`.
2. Build the trade-plan generator (§1.2) — skill + tool, tiers 1–3, no ML dependency, no
   broker/live touch.
3. Everything in §2.2 stays parked until you've actually set up the paper-trading broker
   account — revisit as its own review pass at that point, since several of those bugs
   (especially #4–#6) compound each other and deserve fixing together, not piecemeal.
4. §2.3 — confirm with the other session or drop it if unintentional.
