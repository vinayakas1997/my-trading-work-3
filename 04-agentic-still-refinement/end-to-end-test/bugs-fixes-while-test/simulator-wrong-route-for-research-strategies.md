---
name: simulator-wrong-route-for-research-strategies
status: fixed-in-docs
severity: documented-workflow-cannot-work-structurally
---

# Gap: `03`'s documented simulate step uses the wrong `vinu-simulator` route for a research-promoted strategy

## What was wrong

`03-strategy-research-and-simulation.md` step 4 documents
`POST /simulator/simulate` with `{"strategy_name": "<artifact strategy name
from step 3a>", ...}`. Running it against `AAPL_4` (the real artifact name
from this run's approved research) failed:

```
{"detail":"No weight data found for strategy 'AAPL_4' in range 2022-01-01 to 2026-06-30","error":"validation_error"}
```

Root cause: `POST /simulator/simulate`'s `strategy_name` path calls
`StrategyClient.get_weights()` (`vinu_simulator/clients/strategy_client.py`)
— an HTTP call to **`vinu-strategy`'s** `GET /weights?strategy=...`, not
anything `vinu-research` produces. This is the exact same structural gap
[`understanding-project/a-new-strategy-added.md`](../../understanding-project/a-new-strategy-added.md)
already documented: *"`vinu-strategy` never sees it, ever... zero
references to `artifact` anywhere in its codebase."* `vinu-strategy` is a
YAML rule engine with its own `strategies/` directory — it has no path by
which a research-generated artifact name like `AAPL_4` could ever have
weight data registered against it. This isn't a race condition or a
missing sync step; there is no code path that would ever make it work.

## Why it mattered

Followed exactly as `03` describes, step 4 cannot succeed for **any**
research-promoted strategy, ever — not "sometimes fails," structurally
never works. Anyone running this checklist would be debugging the wrong
service (`vinu-strategy`/`vinu-simulator` weight sync) for what's actually
a route-choice mistake in the checklist itself.

## What actually works — `POST /simulator/simulate/custom`

`vinu-simulator` exposes a second route
(`CustomSimulateRequest`/`simulate_custom`) that takes the strategy's
**raw Python code** directly — `strategy_code` (the `class UserStrategy(BaseStrategy)`
body `vinu-research`'s approved run already returns verbatim in its
`strategy_code` field) plus `class_name: "UserStrategy"` and `symbols`,
with no dependency on `vinu-strategy` at all. Confirmed working for all 3
tickers with real, fully populated metrics (Sharpe, VaR/CVaR, Monte Carlo
validation, ~1,123–1,124 equity points matching the full 2022–2026 range)
using each ticker's actual approved `strategy_code`.

## What was fixed

Documentation only — `03-strategy-research-and-simulation.md` should be
updated to use `POST /simulator/simulate/custom` with the approved run's
`strategy_code`/`class_name`, not `POST /simulator/simulate` with
`strategy_name`, for any strategy that came from `vinu-research` rather
than `vinu-strategy`'s own YAML files. (Left as a follow-up edit to `03`
itself, tracked here as the source of truth for what the correct call
shape is — not re-solved independently in two places.)

## What was achieved

Confirmed a real, working path to simulate a research-generated strategy
end to end, and confirmed precisely why the documented path can never
work — a structural gap already known project-wide, now concretely hit and
routed around in this specific step.
