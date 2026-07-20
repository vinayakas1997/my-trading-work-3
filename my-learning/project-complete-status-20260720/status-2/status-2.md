# Pre-Trading Readiness Assessment — Senior-Quant Review

Companion to [status-1.md](../status-1/status-1.md), [roadmap-fullplan-A-F.md](../status-1/roadmap-fullplan-A-F.md),
and [trade-plan-and-fixes-plan.md](../status-1/trade-plan-and-fixes-plan.md). Those documents cover
the architecture, the phased roadmap, and the trade-plan-generator work. This document steps back
and asks a different question: **before any money — paper or real — touches this system, is the
analysis pipeline actually sound, or are there gaps that would only show up once it's trading?**

Verdict up front: **the pipeline is not ready to trade real capital yet, and the gaps aren't in the
trading logic — they're upstream and downstream of it, in places that are easy to miss until they
cost money.** The architecture itself is more sophisticated than most solo-built systems at this
stage (deflated-Sharpe-aware ranking, walk-forward validation, Monte Carlo permutation testing,
decay monitoring are not beginner moves). The shortfall is that several of the safety mechanisms
are **built but not actually connected end-to-end** — which is more dangerous than "not built,"
because it's easy to assume protection that isn't actually there.

---

## 1. Data foundation — the part everything else is built on, and it's shaky

### 1.1 Prices are unadjusted by default, and nothing downstream turns adjustment on
`vinu-stock-price`'s fetch takes `adjusted: bool = False` as the default. Checked every caller —
`vinu-tools/vinu_tools/client/stock_price.py`, `vinu-simulator`'s engine, `vinu-research` — **none
of them pass `adjusted=True`.** That means every backtest, every factor computation, every angle is
running on raw, unadjusted prices. A stock split shows up as a 50%+ overnight "crash" in the data.
This isn't a subtle statistical nuance — it can silently corrupt trend/momentum signals and trigger
phantom stop-losses on the invalidation checklist the trade-plan generator produces. **This is the
single highest-priority fix before any signal from this system can be trusted.**

### 1.2 Survivorship bias by construction
The pre-computed `initial-analysis` universe is AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA — seven
mega-cap winners. Any strategy "validated" against this universe only ever sees names that survived
and thrived. There are no delisted, bankrupt, or round-tripped names in the sample. A strategy that
looks great here can be systematically blind to the failure mode that actually loses money.

### 1.3 No visible point-in-time discipline
Nothing found that guards against look-ahead in fundamentals or corporate-action data (e.g., using
a restated earnings figure that wasn't actually known at the time a signal would have fired). Not
confirmed as a live bug, but not confirmed as safe either — worth an explicit audit.

---

## 2. Research methodology — statistically thoughtful in one place, leaking in another

**What's genuinely good:** `vinu-research/comparison.py::rank_candidates` uses a **deflated Sharpe
ratio** (`vinu_research/walk_forward.py::deflated_sharpe_ratio`) to correct for multiple-comparisons
bias when ranking LLM-generated strategy candidates. That's a real, non-trivial piece of statistical
hygiene — most retail-grade systems don't bother with this at all.

**The gap:** it only corrects *within one research loop*. `n_trials` is set to the number of
candidates generated in that single run (typically ~5). But the decay-scan re-research trigger
(`vinu-research/cli.py::_trigger_re_research`) means a symbol can get re-researched many times over
its life — each time resetting the trial count back to ~5. The true number of "shots on goal" taken
against that symbol's data is the **cumulative** count across every research run ever performed on
it, not the count from the most recent run. This is the classic "researcher degrees of freedom"
problem, and right now the system has no memory of it across sessions. Over months of automated
re-research, this will manufacture strategies that look statistically significant in isolation but
are actually (for example) the 40th coin-flip that happened to land heads.

---

## 3. The promotion gate is designed but not wired

There is a full shadow-account subsystem in `vinu-research/vinu_research/shadow/` — `codegen.py`,
`extractor.py`, `backtester.py`, `reporter.py`, `storage.py` — and a route,
`POST /research/artifacts/{artifact_id}/promote`, whose docstring literally says *"called by
shadow-evaluator."* Checked thoroughly: **nothing calls it.** There is no scheduled worker for it in
`docker-compose.yml`, and no automatic decision logic connecting shadow-account performance to that
promotion route. The `BENCHING → ACTIVE` transition is currently a manual, undefended operation.

This matters specifically for the stated goal of "validate a strategy in paper trading before
trusting it with capital" — the entire premise depends on this gate actually functioning as a gate,
not existing only as documented intent.

---

## 4. Risk management — order-level is solid, portfolio-level is real but not enforced pre-trade

- `vinu-agent/vinu_agent/broker/order_guard.py` (`OrderGuard.check()`) is legitimately well-built at
  the single-order level: kill switch, ticker allowlist, shorting restrictions, order-value caps,
  daily order-count caps, and (after the recent fix pass) position-percentage and daily-volume caps.
- Correlation-aware portfolio construction exists in `vinu-portfolio` (risk-parity allocation,
  correlation matrix via `compute_correlation_matrix`) — but it only shapes **target weights**,
  computed periodically. There is no independent pre-trade check that says "this new position would
  push portfolio-level correlation/concentration past a limit" at the moment an order is about to
  fire. If `vinu-live` and `vinu-portfolio` ever drift out of sync — and per the earlier code
  review, `vinu-live` currently can't even reach the intended data path correctly (calls agent-api
  routes that don't exist) — nothing at the order layer catches that drift.
- **No stress testing / scenario analysis anywhere in the codebase.** No "what does this portfolio
  do in a 2020-style or 2008-style shock" check exists. Walk-forward and Monte Carlo permutation
  cover the statistical robustness of a single strategy's *historical* edge — they don't answer
  "what's my tail risk if three correlated positions gap down together."
- **No liquidity/capacity check.** The cost model (`vinu-simulator/engine/costs.py`) does include an
  Almgren-Chriss-style market-impact option, which is genuinely good — but there is no position
  sizing logic that caps order size as a function of average daily volume. A strategy can look
  profitable at backtest scale and be unexecutable (or self-defeating via its own market impact) at
  the size it would actually be traded.

---

## 5. Execution readiness — deliberately parked, correctly so

`vinu-live` isn't wired to real broker routes yet (calls agent-api endpoints that don't exist),
TWAP-only execution (no VWAP), no reconciliation logic. This is already known and already correctly
deferred until a paper-trading broker account exists — not re-litigated here, just noted for
completeness of the picture.

---

## 6. Summary table

| Area | Status | Severity |
|---|---|---|
| Price adjustment (splits/dividends) | Off by default, never turned on downstream | **Critical — data correctness** |
| Survivorship bias in analysis universe | 7 mega-cap survivors only | High — invisible blind spot |
| Point-in-time data discipline | Unverified | Medium — needs audit |
| Multiple-testing correction across research history | Resets per session, not cumulative per symbol | High — false confidence over time |
| Shadow-account → promotion gate | Built, never wired to run automatically | **Critical — the actual safety gate is a no-op** |
| Order-level risk checks | Solid | OK |
| Portfolio-level correlation/concentration enforcement pre-trade | Computed, not enforced at order time | Medium-High |
| Stress testing / scenario analysis | Does not exist | High |
| Liquidity/capacity-aware sizing | Does not exist | Medium |
| Execution engine (vinu-live) | Inert/parked pending broker account | Known, correctly deferred |

See [status-2-fix-plan.md](./status-2-fix-plan.md) for the prioritized plan to close these gaps.
