---
name: broker-abstraction-implement-test
status: built -- Alpaca is the only real provider, kept as the default; a second provider is now a real, contained extension point
purpose: record of what was actually touched and tested. Follow-up to component-consolidation-plan.md (raised while discussing it) -- not a container/deployment change, a code-structure one: makes "which broker" a config choice instead of AlpacaBroker() hardcoded at 6 call sites.
---

# Broker abstraction -- implementation record

Built 2026-08-11. User asked whether Alpaca could be made swappable for a
different broker later, Alpaca staying the default. Investigated first,
confirmed real (not guessed): `broker/historical_broker.py`'s
`HistoricalFillBroker` already existed as a second, "drop-in
AlpacaBroker-compatible" implementation (its own docstring's words) used
for backtest replay -- proof the shape already works, just never
formalized into a real interface + selection point.

## What was found

`AlpacaBroker` (`broker/alpaca.py`) was imported and instantiated
directly at 6 real production call sites (confirmed by grep, not
assumed): `audit/ground_truth.py`, `tools/portfolio_tool.py`,
`tools/trade_tool.py` (each already had a `_build_broker`/`_make_broker`
helper branching on `as_of` for replay vs. real -- the "real" branch was
always a bare `AlpacaBroker()`), `broker/order_guard.py` (constructor
default), `server/routes_broker.py` (twice), and `cli.py`'s `_cmd_broker`.

`AlpacaBroker`'s real public interface: `is_configured`, `get_account`,
`get_positions`, `get_orders`, `get_clock`, `submit_order`,
`cancel_order`, `replace_order`. Checked whether `replace_order` is
actually called anywhere outside `alpaca.py`'s own definition and test --
it isn't, and `HistoricalFillBroker` never implemented it either, so it's
not part of the real shared contract. Left out of the formal Protocol on
purpose rather than forcing a fake implementation onto it.

## What got built

- `broker/base.py` (new) -- `Broker`, a `@runtime_checkable` `Protocol`
  covering the 7 methods both existing implementations actually share.
- `broker/factory.py` (new) -- `get_live_broker(provider=None)`. Reads
  `VINU_AGENT_BROKER_PROVIDER` (default `"alpaca"`) against a
  `_PROVIDERS` registry dict; unknown provider raises a clear
  `ValueError` naming what's actually available, never silently falls
  back. `provider` param lets tests/callers override without touching
  env. Deliberately excludes `HistoricalFillBroker` -- that's selected by
  `as_of` being set (a replay session), independent of which real
  provider is configured; each of the three existing `_build_broker`/
  `_make_broker` helpers keeps its own `as_of` branch untouched, only the
  "real" branch now calls `get_live_broker()` instead of `AlpacaBroker()`
  directly.
- All 6 real call sites repointed to `get_live_broker()`:
  `audit/ground_truth.py`, `tools/portfolio_tool.py`,
  `tools/trade_tool.py`, `broker/order_guard.py` (also retyped its
  `broker` param from `AlpacaBroker | None` to `Broker | None`),
  `server/routes_broker.py` (both routes), `cli.py`'s `_cmd_broker`
  (also generalized its not-configured error message from "Alpaca API
  not configured" to "Broker API not configured").
- `broker/__init__.py` -- exports `Broker`/`get_live_broker` alongside
  the existing `AlpacaBroker` (kept exported, still the concrete
  implementation, not removed).
- `.env-example` -- documented (commented out) `VINU_AGENT_BROKER_
  PROVIDER`, default noted as `alpaca`.

## What a second real provider actually requires, going forward

Implement `Broker`'s 7 methods against the new broker's real API, add one
line to `factory.py`'s `_PROVIDERS` dict. No other file changes --every
call site already goes through the factory, not `AlpacaBroker` directly.
This was the actual ask ("keep Alpaca as default, make it flexible for
entering another broker") -- no second provider was built (no broker was
named, and inventing one would be exactly the kind of ungrounded
substitution this project's discipline avoids), just the real, contained
extension point for whenever one is.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-agent/vinu_agent/broker/base.py` | new | `Broker` Protocol |
| `vinu-components/vinu-agent/vinu_agent/broker/factory.py` | new | `get_live_broker()`, `_PROVIDERS` registry |
| `vinu-components/vinu-agent/vinu_agent/broker/__init__.py` | modified | exports `Broker`/`get_live_broker` |
| `vinu-components/vinu-agent/vinu_agent/audit/ground_truth.py` | modified | `_build_broker`'s real branch -> `get_live_broker()` |
| `vinu-components/vinu-agent/vinu_agent/tools/portfolio_tool.py` | modified | `_make_broker`'s real branch -> `get_live_broker()` |
| `vinu-components/vinu-agent/vinu_agent/tools/trade_tool.py` | modified | `_make_broker`'s real branch -> `get_live_broker()` |
| `vinu-components/vinu-agent/vinu_agent/broker/order_guard.py` | modified | constructor default -> `get_live_broker()`, `broker` param retyped to `Broker \| None` |
| `vinu-components/vinu-agent/vinu_agent/server/routes_broker.py` | modified | both routes -> `get_live_broker()` |
| `vinu-components/vinu-agent/vinu_agent/cli.py` | modified | `_cmd_broker` -> `get_live_broker()`, generalized error message |
| `vinu-components/.env-example` | modified | documented `VINU_AGENT_BROKER_PROVIDER` |
| `vinu-components/vinu-agent/tests/test_broker_factory.py` | new | 8 tests: default/explicit/env-var provider selection, case-insensitivity, unknown-provider error, both real implementations satisfy the Protocol |
| `vinu-components/vinu-agent/tests/test_routes_broker.py` | modified | 3 patch targets retargeted from `routes_broker.AlpacaBroker` to `routes_broker.get_live_broker` (same `return_value=mock_broker` semantics, just following the code's own new call path) |

## Test results

```
vinu-agent: 642 -> 650 passed (full suite; 8 new tests)
```

No regressions. `test_routes_broker.py`'s 3 retargeted patches, `test_alpaca_broker.py` (untouched, tests the concrete class directly), and `test_order_guard.py` all confirmed passing before the full-suite run.

## Known follow-ups (not blocking, not silently dropped)

- **No second real broker provider exists yet** -- by design, this pass
  only built the extension point. Whenever a real second broker is
  named, implementing it against `Broker` and registering it is the only
  remaining work.
- **News and stock-price provider pluggability were raised in the same
  conversation but not investigated this pass** -- explicitly deferred,
  scope not yet checked (unlike the broker case, where `AlpacaBroker`'s
  real call-site count and `HistoricalFillBroker`'s existing precedent
  were both confirmed before any code was written).
