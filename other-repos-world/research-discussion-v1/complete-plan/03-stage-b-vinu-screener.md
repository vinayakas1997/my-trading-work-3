# Stage B — `vinu-screener` Build (20 items)

The one genuinely new capability (see `../capability-projection.md` § 4). Unlike Stage A, these items have real build-order dependencies — you can't wire the scan loop before the condition schema exists. Grouped into 4 phases, meant to be done roughly in order; within a phase, items are independent of each other.

Status key: `pending` · `in-progress` · `done` · `skipped` (reason).

## Phase B-1 — Foundation: the condition schema and its safety guards

Nothing else in this stage can be built until this phase exists — everything downstream evaluates against this schema.

| ID | Item | Source | Status |
|---|---|---|---|
| B1 | Condition JSON schema (leaf: indicator/params/field/offset/operator/compare_mode; group: children/logic/negate) | FinceptTerminal → `13-fincept-terminal.md` (`ConditionEvaluator.h/.cpp`) | pending |
| B2 | Non-finite-value guard as a single choke point before any comparison | FinceptTerminal → `13-fincept-terminal.md` | pending |
| B3 | Auto-computed required lookback from the condition tree (warm-up buffer sizing) | FinceptTerminal → `13-fincept-terminal.md` (`required_bars()`) | pending |
| B4 | Rolling-operator expression engine as shared, cached feature library (Rank/Slope/Std/WMA/EMA etc.) | Qlib → `02-qlib.md` | pending |
| B5 | `IndicatorFactory` broadcasting pattern (one calc fn + declared inputs/params, broadcast across all columns) | VectorBT → `09-vectorbt.md` | pending |

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
