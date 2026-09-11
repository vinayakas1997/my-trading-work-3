# Granularity understanding

Internal, step-by-step pipeline detail for every Vina service — not "what
the service is for" (that's `project-understanding/04-new-full-explanation-v2.md`,
the agent-workflow-level view), but the actual real function/endpoint/cadence
level: what runs, in what order, on what schedule, with real names pulled
from the code (not paraphrased). Built so future scenario testing
(`the-resaoning-ineffciency/scenarios-test/`, `llm-scenarios-test/`, or
anything else) has a precise checkpoint to point at instead of a vague
"the analysis step."

One file per service, same format throughout:
- **What it is** — one line.
- **Trigger / cadence** — what starts it (a schedule, an HTTP call, another
  service), and how often.
- **Pipeline** — numbered, in real execution order, each step naming the
  actual function/file/endpoint, not a paraphrase.
- **Storage** — what it persists, where.
- **Talks to** — real inbound/outbound calls to other Vina services.

## Status

| # | Service | What it does | Status |
|---|---|---|---|
| 1 | [vinu-stock-price](vinu-stock-price.md) | Price/candle data ingest + serving (Alpaca + fallback providers) | done |
| 2 | [vinu-news](vinu-news.md) | News ingest + serving | done |
| 3 | [vinu-initial-analysis](vinu-initial-analysis.md) | Per-ticker analysis pipeline (the "28 analyses" layer) | done |
| 4 | [vinu-research](vinu-research.md) | Trade-plan authoring, artifact lifecycle, promotion gates | done |
| 5 | [vinu-screener](vinu-screener.md) | Rule-based screening + ranking | done |
| 6 | [vinu-agent](vinu-agent.md) | LLM agent loop, OrderGuard, broker execution, Telegram | done |
| 7 | [vinu-live](vinu-live.md) | Automated trade-plan execution cycle | done |
| 8 | [vinu-portfolio](vinu-portfolio.md) | Allocation, correlation/risk monitoring | done |
| 9 | [vinu-simulator](vinu-simulator.md) | Backtest/paper-rehearsal engine | done |
| 10 | [vinu-infra](vinu-infra.md) | Shared runtime utilities (calibration log, server helpers, secrets) | done |

All 10 done.

## End-to-end flow (combined view)

The real path from raw data to a live order, with the real cadence at
each hop:

1. **vinu-stock-price** ingests 1-minute bars from Alpaca (+ fallback
   providers) every 60s; **vinu-news** ingests RSS every 10 min +
   provider APIs every 5 min, FinBERT-scores async every 60s.
2. **vinu-initial-analysis** runs all 28 angles per watchlist ticker
   every hour, reading price data from (1) and news from (1).
3. **vinu-research**'s trade-plan authoring (on-demand, not scheduled)
   reads risk state computed fresh from raw prices, plus **only 2 of
   the 28 angles** (`shock_personality`/`shock_clustering`) from (2),
   makes one LLM call, freezes a `CREATED` trade-plan artifact.
4. **vinu-agent**'s planner-worker (every 30 min) is the thing that
   actually notices new/changed research and hands off to the LLM
   research team; its risk-gatekeeper-worker (15 min) and
   capital-allocator-worker (15 min) move an approved plan from
   BENCHING → PEND → ACTIVE, consulting **vinu-portfolio** (correlation-
   aware allocation) along the way.
5. **vinu-live**'s trade-plan-worker (every 5 min) is what actually
   executes: reads ACTIVE plans from (3), prices from (1), shock scores
   from (2), places real orders through **vinu-agent**'s `OrderGuard` →
   Alpaca, and manages every open position's invalidation/trailing-stop/
   bracket/correlation-trim logic every cycle.
6. **vinu-live**'s feedback-worker (5 min) and shadow-worker (1h) close
   the loop back to (3) — realized outcomes feed calibration, and
   paper-trading performance feeds the promotion gate.
7. **vinu-portfolio**'s drawdown monitor (5 min) and **vinu-agent**'s
   real filesystem kill switch are the two independent safety nets that
   can halt everything in (5) regardless of what any of the above
   decided — verified directly, not assumed, in
   `the-resaoning-ineffciency/scenarios-test/06` and `/07`.
8. **vinu-simulator** and **vinu-screener** sit outside this live loop
   entirely — the former is only invoked on-demand for backtesting
   (feeds the promotion-bar math in (3)), the latter is fully decoupled
   (confirmed: zero imports from any of the above) and currently only
   consumed manually via `vinu-agent`'s Telegram `/rank` command, not
   wired into any automated decision.

Built incrementally, one service at a time — see each file for its own
detail.
