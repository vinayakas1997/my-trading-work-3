# Phase 1 — Monte Carlo Foundation

Status: **not started** · Depends on: — · Blocks: Phases 2, 4, 5

> **Storage design note:** the `validation`/`symbols` SQLite columns described below are a
> minimal, direct fix. A separate investigation
> ([../02-storage-memory](../02-storage-memory/00-storage-memory-summary.md)) found that
> `vinu-stock-price`/`vinu-news` use a much stronger catalog+watermark storage pattern, and
> proposes rebuilding this phase's storage on that pattern instead
> ([phase-02 there](../02-storage-memory/phase-02-research-simulator-catalog.md)). Confirm
> which storage design to implement before starting this phase's storage work, to avoid
> building it twice.

## What it is

Fixes the Monte Carlo validation subsystem so it (a) actually gets invoked, (b) tests
robustness more rigorously than a single trade-order permutation, and (c) persists its results
somewhere queryable instead of a JSON file nobody reads. This is the foundation Stage 0 of the
pipeline (the "must validate before anything proceeds" gate) is built on — no later phase can
enforce or display a real validation result until this ships.

Today: `vinu-simulator/vinu_simulator/engine/validation.py` implements
`monte_carlo_permutation` (shuffles realized trade P&Ls 1000×, compares Sharpe distribution to
get a p-value), `bootstrap_sharpe_ci`, and `walk_forward_consistency`. All three only run when
`SimulateRequest.run_validation`/`CustomSimulateRequest.run_validation` is `True` — and no
caller anywhere in the codebase ever sets that flag. When it is enabled, the results are
written only to `run_card.json`/`run_card.md` on disk — never into the SQLite meta store
(`simulation_runs` table has no `validation` column), never returned by any API route
(`SimulateResponse`/`CustomSimulateResponse` have no `validation` field), so
`trade_plan_tool.py`'s `_fetch_validation` — the only consumer — always gets back `{}`.

Two bugs compound this: (1) the request's cache-hash computation *excludes* `run_validation`,
so a validation-required call can silently return a stale cached (unvalidated) result; (2)
`trade_plan_tool.py._fetch_validation` tries to find a run for a symbol via
`r.get("config", {}).get("symbols", [])`, but `RunSummary` never populates a `config` field at
all — so this lookup always fails, independent of the validation-persistence gap.

## Impact

**Before this phase:** Monte Carlo validation is fully coded but functionally dead. No
strategy has ever actually been gated on it. `trade_plan_tool.py` always shows "Monte Carlo
p-value: N/A."

**After this phase:** A caller can request validation, get back a `block_bootstrap` and
`price_path` resampling result (in addition to the existing trade-permutation test) alongside
a combined pass/fail verdict, and that result is durably stored and queryable by run ID or by
symbol — via SQL, not by grepping JSON files on disk. `trade_plan_tool.py`'s validation lookup
works correctly for the first time.

**What still won't work after this phase alone:** Nothing calls Phase 1's gate automatically
yet — `vinu-research`'s refinement loop still doesn't request validation by default (that's
Phase 2). Phase 1 makes the gate *usable and correct*; Phase 2 makes it *mandatory* in the
pipeline.

## Where changes occur

- `vinu-simulator/vinu_simulator/engine/validation.py`
  - Add `block_bootstrap_permutation(trade_pnls, actual_sharpe, block_size=5, ...)` — circular
    block bootstrap of trade P&Ls (preserves local dependence between consecutive trades,
    unlike full i.i.d. shuffling).
  - Add `price_path_resample(daily_returns, actual_sharpe, block_size=20, n_iterations=1000,
    periods_per_year=252.0)` — block-bootstraps the daily return series itself and recomputes
    Sharpe on each resampled path, testing robustness to price-path structure rather than just
    trade-execution order.
  - Add `compute_validation_verdict(validation: dict) -> dict` — combines all sub-results
    (`monte_carlo`, `block_bootstrap`, `price_path`, `walk_forward`) into one documented
    pass/fail (`passed: bool`, `reasons: list[str]`), e.g. `monte_carlo.p_value < 0.05 AND
    price_path.p_value < 0.10 AND walk_forward.consistency_rate >= 0.6`. This is what Phase 2
    gates on — don't leave the threshold logic ad hoc inside `vinu-research`.
  - Existing functions (`monte_carlo_permutation`, `bootstrap_sharpe_ci`,
    `walk_forward_consistency`) stay untouched — they're referenced by existing tests and by
    `_run_validation_and_attribution`.

- `vinu-simulator/vinu_simulator/service.py`
  - Fix the config-hash dict (used in `simulate` and `_simulate_custom_impl`) to include
    `req.run_validation`.
  - `_run_validation_and_attribution` (currently lines ~468-537): extend the returned dict to
    include `"block_bootstrap"` and `"price_path"` alongside the existing `"monte_carlo"`/
    `"bootstrap"`/`"walk_forward"` keys, plus the combined verdict.
  - Reorder so `self._meta_storage.insert_run(...)` happens *after* validation is computed (or
    add a follow-up `update_validation(run_id, validation)` call), so the validation dict is
    actually available to persist.
  - Add an optional `validation_config` field/model on `SimulateRequest`/`CustomSimulateRequest`
    (`n_iterations`, `block_size`, `methods`) defaulting to today's fixed values, threaded
    through into `_run_validation_and_attribution`.

- `vinu-simulator/vinu_simulator/storage/meta.py`
  - Add `validation TEXT` and `symbols TEXT` (JSON list) columns to `simulation_runs`, via a
    migration function mirroring the existing `_ensure_config_hash_column` pattern.
  - Extend `insert_run(...)` with `validation: dict | None = None` and
    `symbols: list[str] | None = None` params, JSON-serialized like `metrics`/`config` already
    are.

- `vinu-simulator/vinu_simulator/server/schemas.py`
  - Add `validation: dict | None = None` to `SimulateResponse`, `CustomSimulateResponse`, and
    `RunSummary`.
  - Add `symbols: list[str] = Field(default_factory=list)` to `RunSummary`.

- `vinu-simulator/vinu_simulator/server/routes_read.py`
  - `GET /results/{run_id}` returns the new `validation` field.
  - Add `GET /runs?symbol=<ticker>` (extends the existing `?strategy=` query-param pattern) so
    symbol-based lookup is a first-class server-side query.

- `vinu-agent/vinu_agent/tools/trade_plan_tool.py`
  - Simplify `_fetch_validation` to call the new `GET /runs?symbol=` endpoint directly and read
    the real `validation` field, instead of the broken client-side `config.symbols` filter.

`write_run_card()` (`vinu_simulator/engine/run_card.py`) keeps writing the human-readable
JSON/markdown artifact for audit/debugging purposes — it's no longer the *only* place
validation data lives; SQLite + the API response become the source of truth for anything
programmatic.

## How to test it

Follow existing fixture conventions in `vinu-simulator/tests/conftest.py` (`synthetic_prices`,
`synthetic_weights`, `sim_config`, `tmp_data_dir`) and `tests/test_attribution.py` (`_FakeTrade`
dataclass, class-per-function test grouping).

- `vinu-simulator/tests/test_validation.py` (new) — add `TestBlockBootstrapPermutation` and
  `TestPricePathResample` mirroring the existing minimum-data-size / "rejects random trades"
  test shapes already used for `monte_carlo_permutation`. Add
  `TestComputeValidationVerdict` covering pass/fail boundary cases explicitly (e.g. verdict
  flips exactly at the threshold).
- `vinu-simulator/tests/test_service.py` (new — no dedicated `service.py` coverage exists
  today):
  - Regression test: `config_hash` differs between `run_validation=True` and `False` requests
    with otherwise identical params.
  - `_meta_storage.insert_run` receives a non-`None` `validation` dict when
    `run_validation=True`.
  - `GET /results/{run_id}` round-trips a `validation` field.
- `vinu-simulator/tests/test_meta.py` (new or extend) — migration test: an existing
  pre-migration SQLite file gains the new `validation`/`symbols` columns without data loss,
  mirroring however `_ensure_config_hash_column` is currently tested (check for an existing
  test first).
- `vinu-agent` side — a unit test for `trade_plan_tool.py._fetch_validation` with a mocked
  HTTP client returning a `RunSummary`-shaped payload that includes `symbols`/`validation`,
  asserting it no longer falls through to `"no_matching_run"` for a symbol that is present.
