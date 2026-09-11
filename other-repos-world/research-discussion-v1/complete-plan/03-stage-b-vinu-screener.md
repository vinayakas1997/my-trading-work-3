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
| B6 | **Done 2026-09-11.** `scan/monitor.py`'s `ScanMonitor` — poll mode only, deliberately: realtime-subscription mode "doesn't scale to 8000 symbols and isn't the right thing to build first" (the tracker's own reasoning, re-confirmed while implementing — `RealtimeScanRunner`'s coalesced-sweep pattern is noted as the reference to come back to if a small-watchlist near-real-time need ever appears, not built now). `interval_sec` floored at `MIN_INTERVAL_SEC=30` (FinceptTerminal's own floor, ported with the same rate-limit-safety reasoning) — a misconfigured rule can't hammer the upstream. `run_cycle()` is the full loop: B7 coarse-filter → per-survivor B9-timeout-guarded fetch → B3 warm-up check → B1/B2/B4/B5 evaluate → B8 edge/cooldown gate → collect fires, returning a `CycleResult` with a per-symbol status (`fired`/`no_match`/`insufficient_history`/`timeout`/`fetch_error`/`coarse_filtered`) rather than just a fired list — needed for B19's dry-run UX later (Phase B-4) without rework. 12 tests. | FinceptTerminal → `13-fincept-terminal.md` (`ScanMonitor` vs `RealtimeScanRunner`) | **done** |
| B7 | **Done 2026-09-11.** `scan/universe.py`: `CoarseFilter` (min/max price, min volume, min dollar volume — all optional, an all-`None` filter is a no-op) + `passes_coarse()`/`coarse_select()`, operating on a cheap `{symbol: {"price","volume","dollar_volume"}}` snapshot mapping rather than full OHLCV history — decoupled from *how* that snapshot is obtained. Missing/non-finite snapshot fields fail closed (same posture as B2), not "unbounded". `ScanMonitor` skips the snapshot round-trip entirely when a rule's filter is the default no-op. 11 tests. | Lean → `05-lean.md` | **done** |
| B8 | **Done 2026-09-11.** `scan/cooldown.py`: `CooldownGate.should_fire(rule_id, symbol, condition_true, cooldown_min)` — per-(rule, symbol) `FireState` tracks `prev_condition` (the edge gate: fires only on false→true) and `last_fired_at` (the cooldown: even a fresh edge is suppressed within `cooldown_min` of the last fire). `reset()` for one symbol or a whole rule (e.g. after a rule edit). Live gating state only — B17's permanent fired-watch audit table (Phase B-4) is separate. 12 tests. | FinceptTerminal → `13-fincept-terminal.md` | **done** |
| B9 | **Done 2026-09-11.** `scan/timeout_guard.py`: `call_with_timeout(fn, *args, timeout_sec, **kwargs)` — runs `fn` on a daemon thread, joins with a deadline, returns a `TimeoutResult` (`ok`/`value`/`error`/`timed_out`/`latency_ms`) rather than raising or blocking past the deadline; an abandoned slow thread finishes harmlessly in the background (Python has no safe way to kill a thread — documented as a deliberate tradeoff, not an oversight). Confirmed while building the real data-source adapter that this is load-bearing, not theoretical: `vinu-stock-price` has no bulk multi-symbol endpoint, so a scan cycle really is one HTTP call per symbol. 5 tests. | daily_stock_analysis → `04-daily_stock_analysis.md` (`source_guard.py`) | **done** |

**Also built this pass:** `scan/data_source.py` — the `SymbolDataSource` protocol B6 depends on, plus `HttpStockDataSource`, the real adapter to `vinu-stock-price`'s `GET /candles/{symbol}` (confirmed no bulk endpoint exists before designing around one-call-per-symbol; same response shape `vinu_research.tools.get_benchmark_data` already reads). 7 tests.

Phase B-2 total: **47 new tests** (142 cumulative with Phase B-1), all passing.

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
