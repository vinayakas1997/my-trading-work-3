# First real run in Docker (2026-10-04): what broke, what was fixed, what is still open

Written for: the person deciding what to do next with the paper run. Everything below was observed by running the stack, not by reading code. Broker is Alpaca **paper** only (`ALPACA_PAPER=true` is pinned and checked by `scripts/stack.sh check`). The models container stays dormant by design.

## What runs

11 services start and report healthy (`scripts/stack.sh up`): news, stock, screener, features, initial-analysis, quant-core (strategy + simulator), portfolio, research, agent, live, reflection. `models-api` is behind a compose profile and is never built or started by default. The local LLM is the `hindsight-llm` container (Qwen3.5-9B on host port 8092), with its hidden thinking switched off (`VINU_LLM_ENABLE_THINKING=false`).

## Defects found by running it, all fixed and committed

| # | Symptom | Cause | Fix (guard that keeps it fixed) |
|---|---|---|---|
| 1 | stock-api died at start | image lacked `vinu-tools` | Dockerfile; `test_stack_guards` scans every image for missing packages |
| 2 | quant-core, research, agent images lacked `vinu-portfolio` (and quant-core `vinu-tools`) | the simulator imports them at load | Dockerfiles; same guard |
| 3 | services could not open their databases | data folders root-owned and not writable | `scripts/stack.sh prepare` |
| 4 | `GET /strategy/strategies` returned `[]` | strategies live in the image, the service reads an empty volume | `vinu-quant-core/entrypoint.sh` seeds the volume (never overwrites edits); guard test |
| 5 | research run burned 8 minutes then reported "Sharpe 0.00" | the pipeline script seeded a class named `SmaCrossover`; research requires `UserStrategy` | route rejects a seed without `UserStrategy` up front; script fixed |
| 6 | LLM calls timed out at 120 s | the local model spends ~70% of its tokens on hidden thinking | `VINU_LLM_ENABLE_THINKING=false` (22.8 s → 6.5 s on a test call; research 475 s → 16 s) |
| 7 | research summary claimed "Sharpe 0.00, no profitable trades" for a Sharpe 0.77 attempt that failed validation | summary was fed the stored best-of-nothing values | summary uses the best attempt's real numbers; stored values unchanged (promotion reads them) |
| 8 | live loop never received a daily bar | strategies say `schedule: daily`, the stock service accepts `1d` and answered 422 | interval normalised in the bars client |
| 9 | the live-decision loop had nothing to run | none of the 6 shipped strategies defines `must_conditions` | first real one added (`trend_pullback_long`) plus a labelled smoke strategy |
| 10 | every reflection read in the agent failed (connection refused) | the reflection API was never started and no URL was set | container runs `serve` next to the worker; URL in `.env-example`; guard on every agent service URL |
| 11 | every agent decision call failed with an empty message | poller's HTTP client times out at 30 s; an agent run takes longer | 300 s for agent calls; the error now records the exception type |
| 12 | shared watchlist returned its dict keys as tickers | `{"tickers": [...]}` was returned as-is | strategy universe reads `tickers` |
| 13 | reflection worker logged 9 stack traces per cycle | stores owned by other services did not exist yet | one-line warning; real errors stay loud |

## The agent chain, observed once on real data

`paper_smoke_test` fired on AAPL's latest daily bar → state `ready_to_execute` → the live service called the agent → the agent read the live context, the strategy, past decisions, `similar_past_peaks` (4 analogous peaks), unconfirmed moves and reflection notes → the **local LLM answered SKIP**, citing `no_recorded_outcomes`, `precondition_untested` and only 4 analogous peaks ("weak context"). That is the intended cautious behaviour: it will not act on invented confidence.

## Connection panel after the run

15 of 40 connections flowing (5 before). `missing`: the two models connections (dormant by design) and `reflection.synthesis->agent.idea_generator` (recorded before the reflection API existed; clears on its next use). 21 not yet seen: nothing has run through them.

## Still open, and why

1. **No paper order has been placed yet.** The only trigger so far was the smoke strategy, which the agent rightly skipped. Forcing an order would mean injecting an EXECUTE decision into the live database and running a cycle by hand; that was **blocked by the permission layer** and left for the owner to decide (see the options in the hand-off message).
2. **Cold-start scaling makes tiny orders vanish.** With maturity gating on, a 1% position is cut to about a tenth (cold start) and then rounded down to whole shares: at $333 a share that is zero shares. Correct for a child-sized system, but it means a small account trades nothing until fractional shares or a larger weight is used.
3. **Models container is dormant**, so the FinBERT news score and the model angles show `missing` (expected).
4. **Reflection stores** owned by the agent and live services will appear once those have written; the worker's warnings should then stop. Not yet re-checked after the agent has run for a while.
5. Whether any threshold or strategy is any good is unknowable until closed paper trades exist.
