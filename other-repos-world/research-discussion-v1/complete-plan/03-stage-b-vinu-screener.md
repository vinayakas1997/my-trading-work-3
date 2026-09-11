# Stage B — `vinu-screener` Build (20 items)

The one genuinely new capability (see `../capability-projection.md` § 4). Unlike Stage A, these items have real build-order dependencies — you can't wire the scan loop before the condition schema exists. Grouped into 4 phases, meant to be done roughly in order; within a phase, items are independent of each other.

Status key: `pending` · `in-progress` · `done` · `skipped` (reason).

## Phase B-1 — Foundation: the condition schema and its safety guards

Nothing else in this stage can be built until this phase exists — everything downstream evaluates against this schema.

| ID | Item | Source | Status |
|---|---|---|---|
| B1 | **Done 2026-09-11.** New `vinu-screener` package. `conditions/schema.py`: `ConditionLeaf` (indicator/params/field/offset/operator/compare_mode/value|compare_indicator+params+field+offset) + `ConditionGroup` (children/logic/negate), `parse_condition()` backward-compatible with a flat legacy leaf-list (implicit top-level AND), `walk()` for depth-first leaf traversal. Ported wholesale from FinceptTerminal's schema, ~1:1. 21 tests. | FinceptTerminal → `13-fincept-terminal.md` (`ConditionEvaluator.h/.cpp`) | **done** |
| B2 | **Done 2026-09-11.** `conditions/guards.py`: `is_finite_operand()` (None/NaN/±inf all fail — the `math.isnan(inf)==False` trap FinceptTerminal's own comment documents) + `all_finite()`. Used as the one choke point in `conditions/evaluator.py` before every comparison. 6 tests. | FinceptTerminal → `13-fincept-terminal.md` | **done** |
| B3 | **Done 2026-09-11.** `conditions/lookback.py`: `required_bars(tree)` = max over every leaf of `max(own_period, compare_period) + max(offset, compare_offset) + 2`, floored at 2 — ported faithfully including the unconditional `+2` margin. `_period_of()` scans a leaf's `params` for any of a generic set of period-shaped keys (`period`/`span`/`window`/`fast`/`slow`/...) rather than a per-indicator-name table, so a new indicator with a period param is covered with no edit here. 9 tests. | FinceptTerminal → `13-fincept-terminal.md` (`required_bars()`) | **done** |
| B4 | **Done 2026-09-11.** `features/operators.py`: the Qlib-style primitives reimplemented on pandas (not taken as a dependency) — `ref`/`delta`/`pct_change`/`sma`/`ema`/`wma`/`rolling_std`/`rolling_rank`/`slope`/`rsi`/`macd`. `features/library.py`: `FeatureLibrary` — a declarative `IndicatorSpec` registry (name → input columns + compute fn + output field names) with a `compute()` cache keyed by `(symbol, indicator, frozen params)`, explicitly **per scan cycle** (`clear_cache()`, owned by B6's loop) so ten rules referencing the same `sma(20)` on one symbol compute it once. Found while re-verifying: `vinu-stock-price/query/indicators.py` already has row-list-shaped SMA/RSI/EMA/MACD/ADX for its own API responses — deliberately not reused (different shape: per-row dict vs vectorized pandas Series needed for a scan over ~8000 symbols), but confirms the indicator math itself isn't new ground. 24 tests. | Qlib → `02-qlib.md` | **done** |
| B5 | **Done 2026-09-11.** `features/factory.py`: `IndicatorFactory.broadcast(indicator, universe, params)` — one indicator declaration applied across every symbol's OHLCV frame in `{symbol: df}`, sharing one `FeatureLibrary` cache; a symbol missing a required column is skipped from the result, not raised (a partial universe result is the correct behaviour at ~8000-symbol scale, not an error). `.latest()` convenience returns one float per symbol (offset-aware, field-aware, NaN dropped). 9 tests. | VectorBT → `09-vectorbt.md` | **done** |

**Also built this pass (glue, not separately tracked):** `conditions/evaluator.py` — ties B1+B2+B4/B5 together: evaluates a parsed tree against one symbol's OHLCV frame via the `FeatureLibrary`, resolving both `>`/`<`/`>=`/`<=`, a float-tolerant level-touch `==`/`!=` (tolerance OR a sign-flip between polls — the "how do I detect a level cross with discrete polling" pattern FinceptTerminal's audit specifically called out), and the crossing/direction operators (`crosses_above`/`crosses_below`/`rising`/`falling`, auto-reading one bar back). Every operand passes through B2's guard before any decision; an unevaluable leaf (non-finite operand, insufficient history, unknown indicator) returns `False`, never raises. AND/OR groups short-circuit. 24 tests. Without this, B1-B5 would be five well-tested pieces that don't connect into anything B6's scan loop could actually call.

Phase B-1 total: **93 tests, all passing.** New package `vinu-components/vinu-screener/` (pyproject.toml, `vinu_screener/{conditions,features}/`, installed editable).

## Phase B-2 — Scan execution loop

Depends on Phase B-1 (needs a schema to evaluate). This is the part that actually runs against the ~8000-symbol universe.

| ID | Item | Source | Status |
|---|---|---|---|
| B6 | Two-tier execution — poll mode (batch, rate-limit-floored interval) as the default for ~8000 symbols, not realtime-subscription mode | FinceptTerminal → `13-fincept-terminal.md` (`ScanMonitor` vs `RealtimeScanRunner`) | pending |
| B7 | Coarse→Fine two-stage universe selection (cheap filter over all ~8000, expensive rules only on survivors) | Lean → `05-lean.md` | pending |
| B8 | Edge-gated per-symbol cooldown firing (armed bool + cooldown_min) | FinceptTerminal → `13-fincept-terminal.md` | pending |
| B9 | `call_with_timeout` daemon-thread guard for bounding flaky upstream fetch calls at ~8000-symbol scale | daily_stock_analysis → `04-daily_stock_analysis.md` (`source_guard.py`) | pending |

## Phase B-3 — The pipeline: filter → score → risk overlay → output

Depends on Phase B-2 (needs the scan loop running before there's anything to filter/score). This is the daily_stock_analysis-shaped production pipeline.

| ID | Item | Source | Status |
|---|---|---|---|
| B10 | Pipeline shape: cached snapshot → hard filter → factor score → risk overlay → concentration overlay → near-score rotation → top-N enrichment | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| B11 | `HardFilterConfig`-style dataclass as the shape of user-defined rule conditions | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| B12 | Risk-overlay-as-penalty-not-filter (bounded additive score + optional hard veto) | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| B13 | `IPairList` filter-chain pattern (each rule = class, declared param schema, `supports_backtesting` marker) | Freqtrade → `01-freqtrade.md` | pending |
| B14 | Turnover-limiting `n_drop`/`hold_thresh` pattern (avoid candidate list flip-flopping every cycle) | Qlib → `02-qlib.md` | pending |
| B15 | Keep scanner fully decoupled from order/research/news pipeline until user selects a symbol — **architecture principle, not a code item; verify it holds at every phase above, don't just check it off here** | FinceptTerminal + daily_stock_analysis (both independently confirm this boundary) | pending |

## Phase B-4 — Operational surface: notifications, audit, admin, dry-run

Depends on Phase B-3 existing (nothing to test/audit/notify about until the pipeline produces results). These can be done in any order relative to each other.

| ID | Item | Source | Status |
|---|---|---|---|
| B16 | `actions` JSON bag on each rule for per-rule notification routing | FinceptTerminal → `13-fincept-terminal.md` | pending |
| B17 | Fired-watch audit retention split (permanent history table separate from live rule state) | FinceptTerminal → `13-fincept-terminal.md` | pending |
| B18 | One-shot vs persistent mode as a per-rule config choice | FinceptTerminal → `13-fincept-terminal.md` | pending |
| B19 | Dry-run/test-rule-before-enable UX (per-target trigger/degraded/skipped counts) | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| B20 | `RemotePairList`'s bearer+TTL-cache+fail-open pattern for exposing screener output over HTTP | Freqtrade → `01-freqtrade.md` | pending |

## Notes on sequencing within this stage

- Phases are meant to gate each other — don't start B-2 until B-1 is substantially done, and so on. This is different from Stage A, where items were mostly independent.
- B15 is unusual: it's not a feature to build, it's a boundary to protect. Check it explicitly at the end of each phase, not just once at the end of the stage.
- Consider whether Stage B should even start before Stage 0's G2 is resolved — if the trade-plan pipeline question changes how `vinu-research` consumes candidates, that could affect where `vinu-screener`'s output plugs in (see `vinu-lifecycle-story.md`'s note that the screener's natural position is upstream of `ResearchService._propose_idea()`).
