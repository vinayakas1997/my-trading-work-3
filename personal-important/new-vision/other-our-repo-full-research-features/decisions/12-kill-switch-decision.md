# Decision — Row 12 Kill Switch rebalance policy (decided 2026-09-07)

> `04:416` whether kill switch lets risk-reducing rebalance through.

## Decision

- Default remains **block everything** (including risk-reducing `rebalance REQUEST`) `broker/kill_switch.py` file-lock + `rebalance_guard.check_rebalance_allowed` + `capital_allocator_hook.py` `PENDBLOCK`. Safer default per `04:416-418`.
- Revisit only if halt must allow de-risking unwind — requires explicit operator override, not code change, and logged as `human_override`.

## Dated

- 2026-09-07 — decided block-all.
