# Project Status — Update (post status-1 roadmap + quant-review fixes)

Companion to [status-1.md](../status-1/status-1.md) (the original architecture snapshot and gap
list), [roadmap-fullplan-A-F.md](../status-1/roadmap-fullplan-A-F.md) (the phased plan written from
it), [trade-plan-and-fixes-plan.md](../status-1/trade-plan-and-fixes-plan.md) (the trade-plan
generator + first bug-fix pass), and this folder's [status-2.md](./status-2.md) /
[status-2-fix-plan.md](./status-2-fix-plan.md) (the senior-quant pre-trading readiness review and
its fix plan). This document is a refresh of status-1's Sections 1–2 — **what exists and how it
coordinates, right now** — since a great deal has changed: two new services were built
(`vinu-portfolio`, `vinu-live`), a real research-decay worker now runs continuously, and five
concrete correctness/safety gaps identified in the quant review have been closed. Like status-1,
every claim here was checked against the actual code, not design intent.

---

## 0. What changed since status-1.md, in one paragraph

status-1.md described a pipeline that stopped at `agent-api` — a capable manual/co-pilot trading
assistant with `vinu-live` not started. Since then: `vinu-portfolio` (capital allocation across
strategies) and `vinu-live` (execution engine skeleton) were built; a `research-decay-scan` worker
now runs the decay-scan loop continuously instead of requiring a human to trigger it; and, in this
session's review pass, five real gaps were found and fixed — unadjusted price data flowing through
every backtest and signal, a multiple-testing correction that was never actually wired to real
backtest results, a "promotion gate" (BENCHING → ACTIVE) that didn't actually gate anything, no
stress-testing against historical crisis windows, and no cap on either total capital deployed or
per-order liquidity. `vinu-live` itself remains intentionally inert (see §3) pending a paper-trading
broker account — this document does not change that.

---

## 1. Component architecture — what exists and how it coordinates today

### 1.1 The pipeline, end to end

```
news-ingest ──┐
              ├──► news-api (8080) ──┐
stock-ingest ─┤                      │
              ├──► stock-api (8081) ─┼──► initial-analysis-compute ──► initial-analysis-api (8083)
              │   (adjusted=True         (16 deterministic angles)
              │    by default now)                 │
              └──► features-worker ──┴──► features-api (8082)                    │
                        (vinu-tools)     (indicators/factors/ML)                 │
                                                  │                              │
                                                  ▼                              ▼
                                          strategy-api (8084) ◄──────────────────┘
                                       (YAML rule engine → target weights)
                                                  │
                                                  ▼
                                          simulator-api (8085)
                                 (backtest engine — Monte Carlo permutation,
                                  bootstrap Sharpe CI, walk-forward, now also
                                  ADV-capped order sizing via max_pct_of_volume)
                                                  │
                                                  ▼
                                          research-api (8087)
                        (generate → backtest → critique → refine loop; autonomous
                         hypothesis generation from angles; decay scan runs
                         continuously via research-decay-scan; promotion to
                         ACTIVE now gated on deflated Sharpe + holdout + stress
                         test, not just a human clicking "approve")
                                                  │
                                                  ▼
                                         portfolio-api (8090)
                        (NEW — correlation matrix + risk-parity allocation
                         across all ACTIVE artifacts, YAML + LLM-Python alike)
                                                  │
                                                  ▼
                                            agent-api (8086)
                     (chat/orchestration; now has real inter-service env vars
                      in compose — previously had none; broker module gated by
                      TradingMandate incl. new max_capital_utilization_pct)
                                                  │
                                                  ▼
                                      live-api / live-worker (8091)
                     (NEW package — signal-to-order translation, TWAP execution,
                      scheduler skeleton. Intentionally not load-bearing yet —
                      see §3. No broker account exists to run it against.)
```

All sixteen services above run continuously via `docker-compose.yml` (`restart: unless-stopped`).
`research-decay-scan` is new since status-1 — a dedicated worker service (not a manual CLI
invocation) running `vinu-research schedule-decay --interval-hours 24` on its own, following the
same `while True: sleep(...)` convention as the rest of the stack.

### 1.2 Data layer — now with a real price-adjustment fix

Same three services as status-1 (`vinu-news`, `vinu-stock-price`, `vinu-tools`), plus
`vinu-initial-analysis` computing **16** deterministic angles (status-1 said 25 — that was always
wrong; verified directly against `catalog/angles.yaml` both then and now).

**What changed:** `vinu-stock-price`'s candle fetch took `adjusted: bool = False` everywhere,
and — more importantly — Alpaca (the live provider) never requested split/dividend-adjusted bars
from Alpaca's API at all, so the flag was a no-op regardless of setting. A stock split would show up
as a fake 50%+ price crash in every backtest, every angle, every signal. Both are fixed: Alpaca's
request now sets `adjustment: all`, and every downstream client (vinu-tools, vinu-simulator,
vinu-initial-analysis, vinu-research) now defaults to and explicitly requests adjusted prices.
Data ingested before this fix predates the correction and should be re-backfilled before being
trusted.

### 1.3 Strategy layer — unchanged mechanism, now with a real promotion gate

The two-mechanism split from status-1 still holds: **vinu-strategy** (deterministic YAML rules) and
**vinu-research** (LLM-generated/refined Python strategies), both backtested through the shared
**vinu-simulator** engine. What's new inside vinu-research:

- **Autonomous hypothesis generation** (status-1's top Phase-A gap) is now real: `ensure_strategy`
  and the `run` CLI subcommand propose an idea from a symbol's angle context when none is given,
  and a real bug where the CLI computed this idea but then discarded it and used the original
  (still-`None`) argument has been fixed.
- **Decay → re-research is now wired**: `research-decay-scan` runs continuously, and a DECAYED
  transition triggers `_trigger_re_research`, calling `ensure_strategy(user_idea=None, ...)` — no
  human has to notice and re-trigger.
- **Deflated Sharpe ratio is now actually computed against real results.** It existed as a function
  before (`walk_forward.py::deflated_sharpe_ratio`) but was never fed real backtest data anywhere in
  the live code path — the only call sites ran pre-backtest, so `n_trials` was computed but the
  statistic itself was always the no-op default. It's now computed once per run, on the winning
  candidate, with `n_trials` **cumulative across every past research run for that symbol** (a new
  `cumulative_trial_count()` store method) — not reset to ~5 every time the decay-scan loop
  re-researches the same symbol.
- **The holdout check is now persisted, not just embedded in report text.** `HoldoutResult.passed`
  was always computed but discarded after being folded into markdown; it's now stored on both the
  run record and the artifact (`holdout_passed`).
- **A new stress test runs once per research run**: the winning strategy is replayed through fixed
  historical crisis windows (2020-03 COVID crash, 2022 rate-hike drawdown) it was never tuned
  against — distinct from walk-forward/holdout, whose windows are still carved from the researched
  range itself. Result persisted as `stress_test_passed`.
- **`POST /research/artifacts/{id}/promote` now actually gates.** Previously it unconditionally
  flipped BENCHING → ACTIVE; its docstring said "called by shadow-evaluator" but nothing called it
  and no such evaluator existed anywhere in the codebase (the `vinu_research/shadow/` module that
  name evokes turns out to be an unrelated feature — mining a human trader's journal into rules, not
  a paper-trading validator). The route now checks `deflated_sharpe >= 0.95` AND `holdout_passed`
  AND `stress_test_passed` (all configurable, all `promotion_*` fields in `ResearchConfig`), refusing
  with a 409 and the specific reasons unless `force=true` is passed. A new `promote-scan` CLI command
  lists BENCHING artifacts and reports/promotes only those clearing the bar — deliberately a
  human/agent-invoked command, not a scheduled worker, since auto-promoting to ACTIVE has bigger
  consequences than auto-triggering more research.

**Aim achieved (new):** a strategy can no longer reach ACTIVE status — where it starts influencing
`portfolio-api`'s capital allocation — purely because a human clicked approve on a good-looking
in-sample Sharpe. It has to clear a multiple-testing-corrected confidence bar, hold up on data it
was never tuned against, and survive a replay through two real historical crises.

### 1.4 Portfolio layer — new since status-1

**vinu-portfolio** (`portfolio-api` :8090) did not exist in status-1. It now:
- Lists all ACTIVE strategies across both mechanisms (`_list_yaml_strategies` from
  `strategy-api`, `_list_llm_strategies` from `research-api`, merged via `asyncio.gather`).
- Computes a correlation matrix across strategy returns (`compute_correlation_matrix`), guarding
  divide-by-zero on near-zero volatility (`vols.clip(lower=1e-6)`).
- Allocates capital via risk parity, clipped to a max-per-strategy weight and renormalized.
- Has its own circuit-breaker module — currently a known gap (see §3): it reimplements the
  kill-switch file path directly instead of importing `vinu_agent.broker.kill_switch`, so it works
  today only by coincidence and doesn't share vinu-agent's newer per-scope halting.

This closes status-1's §3.3 gap ("no capital allocation across strategies... no correlation-aware
allocation exists anywhere") at the construction-logic level. It is not yet consulted at order time
(see §3, Priority 6 in the fix plan) — that remains explicitly parked until `vinu-live` execution
work resumes.

### 1.5 Orchestration layer — vinu-agent, now with two new guardrails and real networking

Same internals as status-1 (`tools/`, `session/`, `memory/`, `swarm/`, `broker/`, `channels/`,
`skills/`), plus:

- **`docker-compose.yml`'s `agent-api` block had zero `VINU_*_API_URL` environment variables at
  all** — every tool would fall back to `localhost` defaults inside the container, which can't
  resolve to sibling containers. Fixed: all eight sibling-service URLs are now injected, matching
  the pattern already used by `research-api`/`portfolio-api`/`live-api`. `AgentConfig.services` was
  also missing a `vinu_portfolio` entry entirely — the env var alone wouldn't have been read even
  after the compose fix; both are now in place.
- **A new `generate_trade_plan` tool** (`trade_plan_tool.py`) and matching `trade-plan` skill —
  produces a forward-looking, human-readable trading plan document (entry checklist, staged
  profit-booking tranches, invalidation/exit checklist) from the existing angles + vinu-tools
  factors + Monte Carlo validation, timeframe-aware (interval now actually maps to the requested
  timeframe, and a missing-analysis-data case is now surfaced explicitly instead of silently
  rendering as blank). Explicitly out of scope: no order submission, no broker calls.
- **`TradingMandate` gained `max_capital_utilization_pct`** — distinct from the pre-existing
  `max_position_pct` (which only caps a single order/position), this caps *total* capital deployed
  across all open positions combined, as a fraction of account equity (e.g. 0.60 = never more than
  60% of the account in positions at once). Enforced in `OrderGuard.check()`.
- **`vinu-simulator` gained `max_pct_of_volume`** in `SimulationConfig` — caps a single day's order
  for one symbol at a fraction of that day's traded volume, applied at both buy and sell sizing,
  before cost is computed. Volume data was already flowing through the simulator's per-step loop
  (used for Almgren-Chriss market-impact cost) but nothing previously used it to cap size — a
  strategy could look profitable purely by assuming it could trade an unrealistic fraction of ADV.

Both new caps default to "no restriction" (1.0) — nothing changes unless explicitly configured.

### 1.6 Execution layer — vinu-live exists now, but is intentionally not load-bearing

status-1 said vinu-live didn't exist. It now does — `live-api`/`live-worker` (:8091), with a
scheduler, a signal-to-order translator, and TWAP execution. But per the review conducted alongside
this session's fixes, it is **not yet safe to treat as functional**:
- `scheduler.py` calls agent-api routes (`/broker/order`, `/broker/positions`, `/prices/{symbol}`)
  that don't exist anywhere in vinu-agent — every cycle 404s today.
- `signal_translator.py` never generates a close order for a symbol that drops out of target
  weights entirely.
- Portfolio value falls back to a hardcoded $1,000,000 when position-fetch fails.
- Only TWAP is implemented; VWAP is documented in the `execution-model` skill but not built.
- The `vinu-live-worker` console-script entry point ignores its own `--interval` CLI flag (masked
  by a coincidentally-matching default).

None of this was touched in this session's fix pass — it stays parked per your explicit direction:
no paper-trading broker account exists yet, so there is nothing to safely test this layer against.
See [status-2-fix-plan.md](./status-2-fix-plan.md) §Priority 6 for when to revisit it.

---

## 2. Aims achieved so far (by stage) — updated

| Stage | Aim | Status |
|---|---|---|
| Data ingestion | Add a ticker → auto-backfill OHLCV + news, split/dividend-adjusted | ✅ automated, adjustment bug fixed this session |
| Feature/factor compute | Auto-compute indicators/factors for any watchlist ticker | ✅ automated |
| Market structure analysis | Auto-compute 16 deterministic angles per ticker | ✅ automated |
| Deterministic strategy authoring | Human/AI writes YAML rules, gets weights + backtest | ✅ fully wired |
| Generative strategy research | LLM proposes + iteratively refines a strategy against real backtests | ✅ autonomous hypothesis generation wired |
| Strategy statistical validity | Multiple-testing-corrected confidence before trusting a Sharpe | ✅ deflated Sharpe now computed against real results, cumulative per symbol |
| Strategy lifecycle | Approved strategy tracked, decay-monitored, re-researched automatically | ✅ fully wired, worker runs continuously |
| Promotion to ACTIVE capital | Gated on more than a human clicking approve | ✅ deflated Sharpe + holdout + stress test bar, enforced server-side |
| Stress resilience | Strategy checked against real historical crisis windows | ✅ wired this session |
| Portfolio construction | Capital allocated across strategies with correlation awareness | ✅ vinu-portfolio built |
| Orchestration | One chat/API surface can drive the whole pipeline as tools | ✅ working, now with real inter-service networking |
| Trade-plan generation | Human-readable staged entry/exit plan from existing analysis | ✅ built this session |
| Capital/liquidity guardrails | Cap total capital deployed and per-order size vs. ADV | ✅ built this session |
| Manual paper trading | A human, via chat, can approve and place a real (paper) order | ✅ working, gated by mandate + kill switch |
| Portfolio-level pre-trade enforcement | Correlation/concentration re-checked at the moment an order fires | ❌ not started — correctly parked until vinu-live execution work resumes |
| Autonomous live trading | System decides and executes trades on its own, manages a real portfolio | ❌ vinu-live exists but is not functional (see §1.6) — no broker account yet |

---

## 3. What's still short

This document intentionally doesn't repeat the full gap analysis — two companion documents already
cover it in depth and remain current:

- **[status-2.md](./status-2.md)** — the senior-quant pre-trading readiness assessment: what's
  fixed (this document mirrors those fixes back into the architecture picture) and, going forward,
  what to watch for as new components are added.
- **[status-2-fix-plan.md](./status-2-fix-plan.md)** — the prioritized fix plan. Priorities 1–5 are
  now complete (adjusted prices, cumulative multiple-testing correction, promotion gate, stress
  testing, capital/liquidity guardrails). **Priority 6** (portfolio-level correlation/concentration
  enforcement at order time) remains explicitly parked until a paper-trading broker account exists
  and `vinu-live`'s execution bugs (§1.6 above) are addressed — building order-time enforcement
  logic against an execution path that doesn't work yet would be building on sand.

The one gap not previously captured anywhere: **`vinu-portfolio`'s circuit breaker reimplements the
kill-switch file path directly** instead of importing `vinu_agent.broker.kill_switch` — it works
today only because the path happens to match, and will silently drift the moment vinu-agent's
per-scope halting changes further. This was flagged in the original code review (finding #11) and
remains unfixed — it's grouped with the other `vinu-live`/broker-adjacent items staying parked in
§2.2 of `trade-plan-and-fixes-plan.md`, not because it's low-value, but because it sits in the same
"broker/execution" cluster that's waiting on the paper account.
