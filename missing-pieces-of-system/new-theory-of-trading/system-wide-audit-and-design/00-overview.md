# System-wide audit and design — the whole pipeline, not just the 29th angle

**This folder exists so the big picture doesn't get mixed into
`../how-to-use-29th-angle/`, which is deliberately scoped to just Track 1
and Track 2.** Everything here spans multiple components across the full
6-layer pipeline (screener → data/analysis → hypothesis/validation →
strategy execution → portfolio risk → live execution), not just the 29th
angle's own mechanism.

## Files in this folder

- `00-overview.md` — this file.
- `01-full-system-layer-map.md` — the full 6-layer system sequence, with
  real citations for what each layer does, `vinu-reflection` as a
  cross-cutting feedback loop (not a sequential step), infrastructure vs.
  pipeline stages, a mermaid diagram, and the "three disconnected
  evidence streams" pattern finding.
- `02-open-questions-strategy-and-simulation.md` — the full audit series:
  26 items covering strategy-definition design questions, a real code
  audit of every layer in the pipeline (`vinu-screener`, `vinu-stock-price`/
  `vinu-news`, `vinu-tools`, `vinu-agent`, `vinu-research`,
  `vinu-simulator`, `vinu-strategy`, `vinu-portfolio`, `vinu-live`),
  cross-service seam issues, cross-cutting patterns found by comparing
  findings against each other, a cross-check against prior recorded
  expectations (the `maturity-agentic-system` and `high-expectations`
  folders), and a final honest assessment of where the whole system's
  components are and aren't actually connected. This is the largest file
  in this folder by far and the one most likely to keep growing.
- `03-strategy-definition-full-schema.md` — the complete strategy
  definition field list: must-condition/indicator "why," a link to
  `HypothesisRegistry`, explicit risk management, precondition/
  postcondition (mirroring Track 2's PRE/POST from the 29th-angle
  folder), a two-level failure definition, a performance-record
  reference, and origin/versioning.
- `reverse-engineering/` — the one part of this folder that moved from
  audit/design into real, built, tested code (started + built
  2026-09-25/26). Reverse-engineers the live-decision loop this file's
  own audit kept circling back to (checking a strategy's precondition is
  true right now, and asking Track 1/2's own recorded evidence what
  happened the last N times this fired, before deciding) into 9 concrete
  points, designs each one's schema/API shape, then builds it end to
  end — including, along the way, the two CRITICAL item #24 fixes this
  file's own audit found (no risk-limit check on `vinu-live`'s main
  execution loop; no same-symbol netting). See its own
  `00-overview.md`/`02-implementation-status.md` for the full, kept-current
  picture of what's built vs. still open.

## How this folder relates to `../how-to-use-29th-angle/`

That folder explains one specific mechanism (the 29th angle) in full.
This folder is everything that mechanism connects to, or should connect
to, or was found not to connect to — the rest of the pipeline, the
audits of each component, and the design questions that span more than
one component at once. Cross-references between the two folders use
relative paths (`../how-to-use-29th-angle/...` and vice versa).

## Status of everything in this folder

`00-01-03` (this file, the layer map, the strategy-definition schema) and
the 26 items in `02-open-questions-strategy-and-simulation.md` remain
design records and audit findings, not implemented — verified against
real code at the time each item was written (dates given per item), kept
in full detail on purpose per standing instruction, meant to be read and
acted on, not summarized away.

**The exceptions**: `reverse-engineering/` took one specific, end-to-end
slice of this audit — the live-decision loop — from design into real,
built, tested code, and along the way closed all three of item #24's
findings. Several direct passes back through this file's own audit
items then did the same for real code outside that folder's own
9-point scope, same "go connect this to real code, not just note it"
discipline each time:
- **Item #13** (`vinu-simulator`): finding #1, a genuine sandbox-escape
  gap in `engine/ast_guard.py` (the AST-based guard only ever checked
  `ast.Call` nodes, so reflection-based escapes reaching `os`/
  `subprocess` through plain attribute access were never blocked),
  fixed — the one real security gap found anywhere in this audit series
  so far, prioritized ahead of the same item's efficiency findings.
  Finding #2 (redundant `meta.json`, plus its own dead `load_meta()`
  reader) also fixed, along with a slice of finding #6 (this file's own
  missing test coverage — 9 new tests). Finding #5 (dead `MetricRow`/
  `SimulateDryRunResponse` schema classes, zero references anywhere)
  also removed, and the rest of finding #6 closed for `clients/base.py`
  (turned out already thread-local per-client, not the shared-lock bug
  item #22 had — confirmed with a test, not assumed) and
  `clients/price_client.py` (thread-pool fan-out and both `ValueError`
  paths, 15 new tests total). Finding #3 (unindexed symbol queries) now
  fixed too — a normalized, indexed `simulation_run_symbols(run_id,
  symbol)` join table, backfilled once from the existing JSON column,
  replacing the old full-table-decode-then-filter-in-Python query.
  Finding #4 (no caching) also fixed — a bounded per-instance LRU cache
  on `PriceClient`/`FeaturesClient`, safe because `service.py` constructs
  exactly one long-lived instance of each, with symbol-order and
  case-sensitivity handled deliberately differently between the two
  cache keys rather than copy-pasted (`get_ohclv`'s dict return tolerates
  sorted keys; `_fetch_price_data`'s ordered-column return can't).
  35 new tests total across both findings. **Finding #6 now fully
  closed too**: new `tests/test_service.py` covers the OHLCV cache's
  TTL/eviction, config-hash determinism, benchmark-metric computation,
  every read/delete method, `close()`, a real end-to-end `simulate()`
  run, and `simulate_custom()`'s validation paths — this 701-line
  orchestration file had zero coverage before. Found and fixed a real
  bug while writing these: `simulate()`'s `dry_run=True` branch
  constructed `SimulationResult` missing 3 required fields the dataclass
  had grown since this call site was last touched — any real
  `dry_run=True` request would have crashed with a `TypeError` (nothing
  caught it; there are zero real callers of that flag today either). 31
  new tests. **Item #13 is now fully closed** — every numbered finding
  (#1-6) fixed.
- **Item #23** (`vinu-portfolio`): all 4 process/logic findings now fully
  closed. Finding #1's net/keep-separate/block policy question — the one
  thing this item explicitly left as "the user's call, not a default to
  assume" — is decided: **net**, matching what `vinu-live`'s
  `SignalTranslator._net_by_symbol` (item #24 finding #2) already does
  correctly, since it's the only realizable option for a single
  brokerage account (no sub-accounts) that doesn't leave a stale
  position sitting on disagreement. Not re-implemented a second time in
  `vinu-portfolio` on purpose (would corrupt its strategy-keyed tilt
  pipeline for a purely duplicate computation); `_detect_symbol_
  conflicts` gained `severity`/`gross_weight` so a conflict's size is
  visible, and severe cases now escalate to a real alert (new
  `/notify/symbol-conflict` on `vinu-agent`'s shared front door) instead
  of just a WARNING log line. Findings #2-4 were already fixed (halve/
  flat now consumed, the risk-tiering system now consumed, agent-API-
  unreachable now escalates). **Code-level finding #5 now also fixed —
  this item is fully closed.** `allocation_history.py` now records why a
  candidate wasn't funded (`target_weight` rounding to ~0 after the tilt
  stack), using the same `RejectionRecord` shape item #18 finding #3
  already used for the screener's own instance of this pattern — reused
  the tilt values the response already computes (regime/outcome/
  confidence-gradient/risk-budget multipliers) rather than inventing new
  attribution logic, documented explicitly as a heuristic over those
  numbers, not a definitive single cause. Finding #6 was checked and
  found genuinely fine, no fix needed.
- **Item #24** (`vinu-live`): all 3 findings fixed (risk-limit check,
  same-symbol netting, reconciliation-drift alerting).
- **Item #20** (`vinu-tools`): the two real ADX/ATR formula bugs fixed
  (findings #1/#2, real Wilder smoothing instead of two different wrong
  conventions), tested (finding #3), and one of the 4 confirmed
  duplication instances partly de-duplicated (finding #7,
  `trend_lifecycle`). Finding #4 (duplicated `_macd()` helper) turned
  out already fixed elsewhere, unrelated to this audit series -- caught
  by re-checking the claim against current code, not assumed. Finding
  #6 (no enforced blessed import path) fixed: `apply_indicators()`
  already existed and did what the finding asked for, just wasn't
  documented -- now named in `vinu-tools/AGENTS.md`'s "How To Use"
  section as the one blessed entry point. Finding #5 (unvectorized
  loops) now has a concrete deferred plan rather than staying an
  unscoped "someday": 18 of the ~28 indicator modules actually use a
  Python loop (not just the finding's own named `mfi.py` example),
  split into a lower-risk rolling-window bucket and a higher-risk
  path-dependent-smoothing bucket that needs a persisted-comparability
  check (item #21 pattern #2) before any rewrite — deliberately not
  implemented yet, per explicit instruction to plan it for later.
- **Item #22** (`vinu-strategy`): finding #1 (silent degraded weights on
  upstream failure, the most serious finding in that item), finding #2
  (a real NaN/inf/allow_short sanity gate, method-agnostic), finding #5
  (a false "unknown risk method" warning), finding #6 (non-atomic
  registry reload, now a single atomic swap), finding #7 (`clients/
  base.py`'s lock serializing every concurrent fetch through the
  10-worker executor regardless — dropped, since `httpx.Client` is
  documented thread-safe for concurrent requests), and finding #8 (zero
  test coverage for `engine/timing.py`, now 10 tests) fixed. Only
  finding #3 (upstream design question) and finding #4 (schema-to-
  dispatcher wiring, a bigger implementation decision) remain open.
- **Item #19** (`vinu-news`): the news finding #1 fixed — the single
  most serious point-in-time finding in this whole audit series, a
  silent look-ahead-bias risk baked into the data layer itself
  (`ArticleRecord`'s `sort_ts` silently conflated real publish time with
  ingestion time, with no flag when a fallback substitution happened).
  Now built exactly to the finding's own concrete schema spec:
  `published_at`/`ingested_at`/`publish_time_is_estimated`, threaded
  through the dataclass, the SQLite schema/migration columns, and
  `enrich_article()`'s one real call site, confirmed with a real
  insert-then-read-back round-trip test, not just at the dataclass
  level. Its own finding #2 (no server-side as-of/cutoff enforcement) is
  also fixed, built as one shared `vinu-infra` piece together with
  `vinu-stock-price`'s sibling finding #1, not two separate patches.
  `vinu-stock-price`'s finding #4 (`yfinance` had no retry/backoff,
  unlike every other provider in the directory) now fixed too, same
  pattern item #11 finding #3 already established for `vinu-agent`'s
  `fundamentals_tool.py` — a plain retry-after-sleep loop, not
  `vinu_infra.retry`'s HTTP helper, since yfinance's failure modes
  aren't reliably `requests`-typed. 8 new tests (this provider had zero
  coverage before). Findings #2 and #5 also fixed: `/candles/{symbol}`
  now surfaces a live-detected session gap count
  (`X-Session-Gap-Count`, 1m-only) and indicator-cache staleness
  (`X-Cache-Age-Seconds`) as response headers, the same convention
  `X-Clamped-To-As-Of`/`X-Data-Empty` already established on this same
  route — not a new response shape. Found and fixed a real, previously-
  invisible test-isolation gap along the way: `query/engine.py`'s frame
  cache is keyed by symbol only with a 30s blind-trust cooldown, so
  reused-symbol tests across the file could silently read each other's
  cached data; existing tests never caught it because their assertions
  were shape-invariant. 12 new tests. Only vinu-stock-price's finding #3
  (indicator duplication) remains open on this side.
- **Item #17** (cross-service seams): findings #1 and #3, the two
  halves of this item's own named compound retry-storm risk, fixed.
  `ResilientClient.get`/`post` (`vinu-infra`) gained an opt-in
  `raise_on_error` so `vinu-research`'s `run_backtest()` can finally
  reach its own already-written (but previously dead) `HTTPStatusError`
  handler instead of every failure collapsing into a generic message.
  `research_tool.py` and `run_sweep_candidate_tool.py` (`vinu-agent`)
  both had their blanket `except Exception` narrowed to `ImportError` —
  the one legitimate reason for the HTTP fallback per
  `research_link.py`'s own docstring — so a real `InfrastructureError`
  now surfaces as an error instead of silently triggering a duplicate,
  expensive run over HTTP. `run_sweep_candidate_tool.py` was the file
  where the compound risk was actually concrete (nothing in
  `vinu_research.sweep.run_sweep_candidate()` catches
  `InfrastructureError` the way `loop.py` does for `run_research()`).
  Finding #2 also fixed — `ResearchResult.outcome_status`
  (`"infra_failure"|"no_strategy_found"|"passed"`), named to avoid
  colliding with `service.py`'s existing, unrelated `status` key, and
  traced all the way to `research_tool.py`'s response so a scheduler can
  actually read it without parsing prose. **Finding #4 now also fixed —
  this item is fully closed.** Computed the real worst case rather than
  guessing: `run_sweep_candidate_tool.py`'s HTTP fallback wraps exactly
  one call into `run_backtest()`'s simulator client (`timeout=120.0,
  max_retries=3`), whose own worst case (3 attempts + backoff) is 365.0s
  against the old hardcoded 180 — replaced with a computed
  `_SWEEP_CANDIDATE_TIMEOUT_SEC` (worst case + a 35s margin), not a
  bigger guess. The ack-then-poll alternative this finding also offered
  was not needed for a mismatch this precisely bounded. Also closed one
  of the item's two unnumbered "confirmed gaps, not new items": a real
  contract test now exists between all three services (two files, one
  per hop — agent→research validated against vinu-research's own real
  pydantic request models, research→simulator validated against
  vinu-simulator's own real schema), catching schema drift instead of
  trusting hand-copied assumptions on either side. The other confirmed
  gap (no `policy_version` field threading through the chain) remains a
  separate, real design decision.
  **UPDATE (2026-09-28)**: built for the research↔simulator hop (see
  `02-open-questions-strategy-and-simulation.md`'s own item #17 UPDATE)
  -- a deterministic schema-hash, not the same thing as
  `vinu_infra.model_policy.policy_version()` despite the name overlap.
  The agent↔research hop is the identical pattern, not yet done.
- **Item #18** (`vinu-screener`): finding #1 fixed — a
  `min_history_bars` field on `HardFilterConfig`, enforced in
  `RankerRunner.run()` before factor computation/scoring, so a
  thinly-traded or recently-listed symbol can no longer reach a ranker's
  top-N with fewer bars than Track 1's `signal_evidence` actually needs
  (`min_observations=70`) — the same "gate before the expensive work"
  point the condition-tree path's own `required_bars`/
  `insufficient_history` already made, now built for the ranker path
  too. Finding #2 addressed as a documented recommendation, not a
  changed class default (flipping it would silently change already-
  configured rankers' live behavior) — `HardFilterConfig`'s docstring
  now points to `rankers/seed.py`'s own already-chosen numbers
  (`min_price=5.0, min_dollar_volume=1_000_000.0`). Finding #4 (the
  screener's own hand-rolled `sma`/`ema`/`rsi`/`macd`/`wma`/`std`) checked
  function-by-function rather than fixed in bulk: `sma`/`ema`/`macd`
  already compute the same formula as `vinu-tools` (duplicated code, not
  a numeric risk), `wma` has no `vinu-tools` counterpart, and `std`
  measures a different feature than `vinu-tools`'s "volatility_20d"
  (price-level std vs. std of returns) — not actually a duplicate.
  `rsi()` was the one real divergence (a wrong Wilder-seeding convention
  that could rank tickers on different numbers than Track 1 sees) and is
  now fixed to match `vinu-tools`'s `_rsi()` exactly, verified
  index-for-index. Full delegation to `vinu-tools` was not done —
  `vinu-screener` has no existing dependency on that package, and its
  row-based `compute()` shape doesn't compose with this module's
  pandas-`Series` Qlib-style operators. **Finding #3 now also fixed —
  this item is fully closed.** Built as item #21 pattern #3's own
  recommended shared piece: new `vinu_infra/rejection_log.py`
  (`RejectionRecord`/`record_rejection()`), wired into `FilterChain`
  (which diffs each stage's before/after candidate sets to collect a
  bounded per-stage sample of what got dropped and why) through to
  `PipelineResult.rejected_samples`. Found and fixed a second, deeper
  gap along the way: `HardFilterRule.apply()` computed the specific
  drop reason and never attached it to the candidate at all (unlike
  `RiskVetoRule`, which already did) — fixed by reusing the existing
  `veto_reason` field for both stages. Also found and fixed a fully
  independent bug while tracing this to the real HTTP consumer:
  `RankerSnapshot.to_dict()` — the method both `/rank` and `/latest`
  serialize through — never included `trace` at all, despite it already
  reaching the store; stranded one method call from the API response
  since whenever that column was added.
- **Item #11** (`vinu-agent` tool-calling layer): finding #1 (duplicated,
  already-inconsistent `date_to_epoch`/`iso_to_epoch` date helpers) and
  the most important part of finding #2 (zero test coverage on the as-of
  look-ahead-bias clamp, the item's own top-priority pick) both fixed —
  in the order this item's own "suggested priority if/when acted on"
  note recommended. New shared `tools/_date_utils.py` fixed the actual
  inconsistency while deduplicating it (the old `date_to_epoch` was
  local-timezone-dependent via `time.mktime`, compared directly against
  the already-UTC-aware `iso_to_epoch` in every affected tool's own
  as-of clamp check), not just relocated it. 22 new tests across
  `stock_price_tool.py`/`news_tool.py`/`correlation_tool.py`/the new
  date-utils module. Finding #3 (`fundamentals_tool.py`'s missing
  yfinance retry/backoff) also fixed — a plain retry-after-sleep loop,
  6 new tests (this file had zero coverage before). Finding #5
  (`options_tool.py`'s retryable/permanent error conflation) also fixed
  — a new `RetryableOptionsError` reaches both of `fetch_chain`'s real
  consumers (`OptionsGreeksTool` and `routes_options.py`'s own HTTP
  front door for vinu-research), and closed a second gap the finding
  didn't name (403 wasn't grouped with 401 as a permanent failure). 21
  new tests (this file had zero coverage before). Four more of finding
  #2's zero-coverage files now closed: `portfolio_tool.py` (10 tests —
  found and fixed a real bug along the way: one requested section
  failing used to discard every other section already fetched in the
  same call, now each is independent and only becomes a true error when
  all requested sections fail), `remember_tool.py` (7 tests — found and
  fixed a second real bug: re-remembering the same name silently reset
  `created_at` with no signal anything was overwritten, now preserved
  and flagged), `query_memory_tool.py` (7 tests), `web_search_tool.py`
  (6 tests, and a real limitation flagged rather than fixed: this only
  calls DuckDuckGo's Instant Answer API, not real web search, so most
  real queries silently come back `status: ok, results: []`). 9 files
  from finding #2's original list remain open (`trade_plan_tool.py` —
  highest remaining value, but 1330 lines/~26 methods — plus 5 lower-
  value introspection/bookkeeping files and `angle_clusters.py`).
  Finding #4 (no per-turn caching) also remains open.
- **Item #12** (`vinu-research` inefficiency audit): finding #3
  (`pbo.py`'s CSCV overfitting math, previously unverified despite
  feeding the promotion gate's severe-overfitting check) now has 14
  direct unit tests — the degenerate fallback, a dominant-strategy
  exact-zero case, a systematically-reversing high-PBO case, a real
  embargo differential, the env-var fallback, Monte-Carlo sampling, and
  `_logit()`'s own clamping. Finding #2 (dead `diverse_top_n()`)
  investigated and deliberately left open: the loop's own call sites
  never select a top-N at all (`ranked[0]` only), so wiring it in would
  mean changing the generation strategy itself, a real design decision,
  not a wiring gap. Finding #1's own
  "smallest first" fix built — `trade_score_calibration._write_state`'s
  plain, non-atomic `path.write_text()` (a crash mid-write could corrupt
  the live trade-score-threshold state) replaced with the same
  tmp+`os.replace` trick `hypothesis_registry.py`'s own `_write` already
  uses. 4 new tests, including one proving a failure mid-write leaves
  the previously-committed state untouched rather than corrupted.
  Finding #1's "full fix" also done — `judgment_store.py` (no lock at
  all around its actual file write, despite concurrent writers) migrated
  onto `SQLiteBackend`, the same base its siblings already used; `path=None`
  now maps to real SQLite `:memory:` instead of a second hand-rolled
  in-memory mechanism. Confirmed zero real callers of this class exist
  yet anywhere — the risk is dormant, not exploited, but the fix is the
  same either way. **Finding #4 now also fixed** — the walk-forward
  result nested in the same discarded `SweepGridResult` as item #3 is
  persisted on the same `sweep_runs` row item #3's own fix builds (see
  next bullet), not as a separate mechanism. **Finding #2 now also
  built**, on explicit instruction to accept the added backtest cost:
  `_default_quant_coder` used to rank drafted candidates once on a
  pre-backtest heuristic alone and discard the rest on a guess; new
  `_backtest_and_rank_candidates()` uses the previously-dead
  `diverse_top_n()` to select a diverse subset, backtests each for real,
  and re-ranks by actual performance (`rank_candidates`'s own
  `backtest_results` param existed from the start but nothing had ever
  called it with real data). LLM-call cost is unchanged — the candidates
  were already drafted in one generation call either way. A per-candidate
  backtest failure doesn't abort the round; only every candidate failing
  re-raises. 4 new tests plus 8 existing ones retrofitted with a
  `_run_backtest` mock (they'd never triggered a real backtest during
  generation before). **This item is now fully closed.**
- **Item #3** (sweep/search comparisons computed then discarded): fixed,
  built to the exact table shape this item's own text already
  specified. New `vinu_research/sweep_store.py`'s `SweepGridStore` — one
  `sweep_runs` header row per search round (`sweep_id`, completeness,
  PBO, walk-forward verdict) plus one `sweep_grid_points` row per grid
  point tried, winner and losers alike, with the loser's own real
  failure reason preserved, not discarded. `run_sweep_grid()` generates
  a real `sweep_id` and persists by default; the one real decision this
  needed — `walk_forward.py`'s own inner per-window grids must NOT each
  persist as if they were independent top-level search rounds — was
  made explicitly (`persist=False` on that one inner call site) rather
  than defaulted. Wired all the way to the real HTTP layer: `POST
  /research/sweep/grid`'s response now carries a real `sweep_id`, and
  new `GET /research/sweep/grid/{sweep_id}` / `GET /research/sweep/grid?
  symbol=...` let a future strategy-writer actually read a past search
  round back, not just know it exists on disk. Caught and fixed a real
  test-hygiene risk before it landed: defaulting to always-persist meant
  several existing tests and route fixtures would have started writing
  real SQLite files under this repo's working directory on every test
  run — fixed by making every non-persistence-focused test explicit
  about `persist=False`/a `tmp_path`-scoped config, not by weakening the
  default itself.
- **Item #14** (senior-quant recommendation): part B's
  `param_diff_from_winner` field built — a pure diff function
  (`vinu_research/sweep_grid.py`) wired all the way through to
  `POST /sweep/grid`'s real HTTP response (`routes_sweep.py`'s
  `_serialize_grid`), not left computed-but-stranded. Chosen because
  this item's own "checked directly" note confirmed it needs no new data
  collection, unlike everything else in the item. **Part A now built,
  two of the four named factors**: new `CompositeSizer`
  (`vinu-simulator/engine/sizing.py`) multiplies vol-target sizing with
  correlation-aware shrinkage, reusing the exact DCC-GARCH/Gerber math
  this item's own "checked directly: this one genuinely is a drop-in"
  note pointed at — relocated from `vinu-portfolio/shock_correlation.py`
  to `vinu_tools` first so both services share one implementation, not
  two. GARCH refitting is cached (every 20 rows, not every rebalance
  day) so this doesn't make backtests using it prohibitively slow. 24
  new tests across `vinu-simulator`/`vinu-tools`, zero regressions in
  either or in `vinu-portfolio`. Evidence-confidence and drawdown-aware
  sizing (this item's own claim that evidence-confidence was "already
  sketched" turned out not to hold up on a fresh grep — corrected, not
  silently carried forward) and part B's `rejection_reason`
  categorization remain open, as does item #3's own persistence table
  these fields are ultimately meant to live in.
- **Item #15** (incremental/rolling backfill gap): option (a), "a
  deliberately small, low-risk first step," built — `days_stale`, added
  to `ticker_coverage.py`'s per-angle coverage dict, computed fresh at
  read time from each angle's own `analysis_until`, never stored. Already
  reaches the real HTTP coverage route with no extra wiring (it returns
  this function's dict directly). Option (b) — the actual orchestrator
  change that would auto-request the gap, not just surface it — remains
  a separate, larger decision, not made here.
- **Item #21 pattern #1 / item #19's vinu-stock-price finding #1 and
  vinu-news finding #2** (no service anywhere had server-side
  point-in-time enforcement): fixed as one shared piece in
  `vinu-infra/point_in_time.py` (`clamp_to_as_of()`), not two separate
  per-service patches — the first of item #21's three recurring
  cross-cutting patterns to get the shared-infra-level fix it
  recommends, rather than another one-off. Wired into
  `vinu-stock-price`'s `/candles/{symbol}` and `vinu-news`'s
  `/ticker/{symbol}` — the two routes in each service already shaped
  closely enough to fit directly. Every other read route in both
  services is a relative `days`/`hours`-back-from-now window with no
  absolute end param at all; extending `as_of` there needs a real design
  decision about how it interacts with each route's own semantics, not
  made here. Pattern #2 (indicator duplication) in item #21 still has no
  shared fix, but its remaining `trend_lifecycle/compute.py` gap (the
  true-range formula still computed inline after finding #7's own
  smoothing fix) is now closed — switched to `vinu-tools`' own shared
  `true_range()`, verified index-for-index identical first. Tracing
  "same definition as snapshots" (that file's own comment) turned up a
  6th, more serious instance: `trend_lifecycle/snapshots.py`'s entirely
  separate ~90-line hand-rolled indicator library (its own RSI/MACD/ATR/
  ADX), with real confirmed formula divergences from `vinu-tools`
  (plain-SMA/wrong-seed smoothing, the same bug class findings #1/#2
  already fixed once). Deliberately NOT fixed: unlike every other
  instance in this pattern, this one's output (`rsi_14`/`atr_pct`) is
  persisted into a KNN pattern-matching feature library this file's own
  docstring says must stay "directly comparable forever" — changing the
  formula would silently break comparability between already-stored
  historical patterns and every new one going forward. A real migration
  decision (recompute and accept a one-time break, version-tag old vs.
  new rows, or keep the current formulas as the permanent definition),
  not a wiring gap, and left explicitly open rather than guessed at.
- **Item #21 pattern #3** (silent rejection-reason discard): also now
  has its shared-infra piece — `vinu_infra/rejection_log.py`
  (`RejectionRecord`/`record_rejection()`), built to the exact shape
  this section's own text specified. All three of the original instances
  named in this pattern's own text are now fixed using it: item #18.3
  (screener, first consumer, found two extra bugs along the way), item
  #23.5 (portfolio's `allocation_history.py` — reused the tilt values
  the response already computed rather than inventing new attribution),
  and item #16.2 (generation-time candidate scoring — the one instance
  with genuinely no existing persistence surface to extend, so a new
  `generation_candidate_store.py` was built for it, with the opposite
  default-persistence decision from item #3's own `run_sweep_grid()` —
  see item #16's own entry for why). Item #3's sweep comparison itself
  was fixed too, to the same table shape it had already specified,
  independently of this shared shape (it's a comparison/ranking table,
  not a rejection log — a different concept that happens to persist
  losers alongside a winner the same way). The 4th instance found while
  building `reverse-engineering/` keeps its own already-working
  `LiveDecisionRecord`, deliberately not retrofitted onto this shape for
  a purely stylistic consistency win. **Pattern #3 is now fully
  addressed across every instance it named** — only pattern #2
  (indicator duplication) in item #21 still has no shared fix.
- **Items #1 and #7** (Track 1's must-condition evidence never reached
  `HypothesisRegistry`): built, after a real design discussion that
  surfaced something the audit itself hadn't — `add_evidence()`'s
  auto-promotion math is Sharpe-specific, so naively feeding Track 1's
  outcome data through it would have silently corrupted `best_sharpe`.
  Decided design: **evidence-trail only** (a new `Evidence.metric_kind`
  field keeps this new evidence kind out of the Sharpe-specific
  promotion path entirely — no auto-validate, no auto-reject) and
  **strict match only** (an exact `signal_definition` match, no
  fuzzy-matching, no auto-creating a hypothesis when nothing matches).
  New `vinu_research/signal_evidence_bridge.py` summarizes Track 1's
  resolved triggers per symbol/condition and appends one evidence entry
  per call; wired into `vinu-agent`'s existing `planner-worker` cycle
  (not a new schedule) via the same in-process `research_link.py`
  bridges already used elsewhere. **Item #16 finding #1 is now fully
  closed too**: `loop.py` already pulled recent hypothesis evidence into
  the generation prompt, pre-dating this finding — the real, narrower
  gap was that its formatting dropped `reasoning` (where a signal-
  evidence entry's actual content lives), fixed by branching the
  existing formatting line on `metric_kind`. **Finding #2 also now
  fixed** — new `generation_candidate_store.py` records every candidate
  `LlmStrategyGenerator.generate()`/`.refine()` drafts, winner included,
  right at the point the heuristic complexity-penalty ranking already
  discards the other 2 — wired to a real HTTP surface
  (`GET /research/generation-rounds`) too, not left store-only. **Finding
  #4 investigated, a correction recorded, then built** on explicit
  instruction to invent a real replacement rather than leave the design
  call open. Its own text ("item #1's structured `indicators_used`
  schema would dedup far more reliably") turned out not to carry over —
  `_match_score` ran on the incoming free-text idea string *before* any
  research determines that idea's indicators, so that structured field
  doesn't exist yet at dedup time. Replaced instead with two tiers: TF-IDF
  cosine similarity (new `idea_similarity.py`, the same algorithm
  `vinu-news`'s own `cosine_dedup` already uses for this class of
  problem, reimplemented independently) as a cheap screen, then a new
  `ResearchLlmClient.check_duplicate_idea()` LLM call (one call covering
  every candidate that passed the screen, not one per candidate) for the
  real semantic judgment a bare score can't make — "SMA crossover" and
  "moving-average crossover" share almost no literal tokens but are the
  same idea. The LLM's explicit "not a duplicate" is trusted, not
  second-guessed by the similarity score; the similarity threshold is
  only used as a fallback when the LLM is unavailable or the call fails.
  19 new tests (10 for the new similarity module, 9 for the new matching
  method), the old `_match_score`/`TestMatchScore` removed as genuinely
  dead code rather than left behind. Findings #3/#5 (the unified
  candidate graveyard across all death points, seed-and-forget ticker
  discovery) remain untouched.
- **Item #6** (regime tagging): Track 1's half built, using this item's
  own already-worked-out reasoning (same-service call, no cross-layer
  dependency inversion) rather than a new decision. Turned out more
  involved than the item's own framing suggested: `session`/`day_of_week`
  (the fields `regime` was meant to sit "alongside") don't exist in the
  real payload at all — added as one more key in the existing, already-
  flexible `indicators` dict instead of a new schema field.
  `regime_analysis/compute.py`'s private per-bar regime series made
  public and reused directly (no new formula), looked up by `bar_ts` —
  not positional index, a real misalignment trap caught before it
  became a bug, since the reused function drops warmup rows and
  re-indexes from 0. Track 2's half untouched (Track 2 itself is still a
  design, not real code, so there's nothing to wire this into yet).
- **Item #2** (a "universal strategy" runnable inside the 29th angle) —
  **proven as a working proof-of-concept, not the full generalization**
  this item's own text calls "probably the biggest single piece of work
  in this list." Checked the "reduce, don't rebuild" question first and
  it resolved to "no": `vinu-strategy/engine/rules_engine.py` evaluates
  one live snapshot with no memory of the prior bar, so it has no
  concept of a *crossing* and can't scan historical bars — the
  already-existing `_find_crossings` stayed the one crossing primitive,
  reused for both a threshold-cross kind (new) and the original
  two-series-cross kind, not reinvented. New `MustCondition` dataclass +
  `series_by_key` lookup in `signal_evidence/compute.py`; `None`
  (every existing caller) preserves the exact old hardcoded SMA(5)/
  SMA(50) behavior byte-for-byte. Proved real with a genuinely different
  must-condition kind — RSI(14) crosses above 30, mean-reversion rather
  than trend-following — running through the exact same indicator-
  snapshot/outcome-path/idempotent-storage pipeline, full supporting-
  indicator snapshot included. Deliberately does NOT build a config/HTTP
  surface for supplying a custom condition in production yet — `runner.py`
  already has the extension point (`inspect.signature()`-based optional
  kwargs, the same mechanism `price_client` already uses), just no config
  source feeding it yet — that remains real, separate, undecided work.
- **Item #9** (news-confound flagging): Track 1's half built — its own
  named precondition (item #19's `published_at`/`publish_time_is_estimated`
  fix) was already satisfied, so this wasn't actually blocked. Found a
  real wiring gap better than this item's own suggested design:
  `runner.py` already fetches and caches each run's news once and hands
  it to every angle's `compute()`, `signal_evidence/compute.py` just
  never read it — no new HTTP call needed at all. New
  `news_confound: {occurred, minutes_before, article_id}` (only articles
  at or before the trigger count — no look-ahead) added as one more key
  in the same flexible `indicators` dict `regime` (item #6) already
  extended. `NEWS_CONFOUND_WINDOW_MINUTES` (default 60) is a guessed
  starting constant, same posture as `FORWARD_HORIZON_BARS`. Track 2's
  half untouched (Track 2 itself still isn't real code).
- **Item #8** (cross-strategy indicator pooling): built. Its own stated
  blocker ("depends on #1's schema existing first") was stale — item
  #1's wiring landed 2026-09-26. New
  `HypothesisRegistry.pool_evidence_by_indicator()`, a read-time query
  (no new table) grouping every hypothesis's `Evidence` by each entry in
  its `indicators_used`, exposed via `GET /research/indicators/pool`.
  Grouped by `(indicator, metric_kind)`, not indicator alone — avoids
  re-mixing Sharpe-flavored and signal-evidence-flavored averages under
  one number, the same distinction item #1's own fix established.
  8 new tests, 51 passed together with existing hypothesis/introspect
  route tests.
- **Item #25** (cross-check against prior recorded expectations): a
  fresh, checklist-style re-read of `high-expectations/chatgpt-version/`'s
  two source docs found most of the senior-quant expectation list
  already built (bull/bear/risk debate, self-calibrating Trade Score,
  a real kill switch, VWAP/TWAP execution, KNN market-memory matching,
  the `live_decision` re-evaluation loop) — and closed the real gaps:
  composite position sizing (see item #14 above), a new HTTP surface for
  `StrategyEvaluationStore`'s already-existing "why isn't this trading"
  view (3 new routes), a system-wide maturity-tier capital multiplier in
  `vinu-portfolio` (opt-in, fails open), and a new `search_trends` angle
  (`pytrends`, no API key needed — the one alt-data source with no
  paid-tier or missing-consumer blocker; order-book/on-chain data were
  checked and explicitly deferred). Also corrected a wrong claim before
  building on it: a hard risk:reward floor already existed
  (`trade_score_gate.py`'s `_reward_risk_ratio()`), not a gap. 30+ new
  tests across 6 services, zero regressions everywhere confirmed
  runnable; `vinu-initial-analysis`'s own full suite still can't run
  end-to-end here (pre-existing torch-dependency collection errors,
  confirmed via `git stash` to predate this change) — a targeted sweep
  of every non-ML test file plus the new angle's own tests passed
  instead, same honest scope this file already uses for that component.
  **Follow-up (2026-09-27)**: built the two maturity-tier consultation
  points the reverse-engineering doc's own step-3 phasing had marked
  "still not started" — risk_gatekeeper (`vinu-live`'s `_check_breaker()`
  now scales `BreakerLimits` by tier, opt-in) and live_decision (wired
  into `vinu-agent`'s `get_live_decision_context_tool.py`, the real
  deciding agent's own context source, not `vinu-live` — corrected mid-
  build once the reverse-engineering doc's point 8 confirmed where the
  deciding agent actually lives). One new shared
  `MaturityConsultationStore` (`vinu-infra`) logs every consultation
  across both consumers. 20 new tests (15 `vinu-live`, 5 `vinu-agent`),
  zero regressions in either service (`vinu-agent`'s full-suite failures
  are pre-existing environmental gaps — `openai`/`vinu_live` not
  installed in this venv — confirmed via direct traceback, not caused by
  this pass). The exit-mechanism gap for `live_decision`-opened positions
  (no way for one to ever close) was investigated and confirmed real but
  deliberately not built yet, pending explicit confirmation given
  live-money stakes.
  **Follow-up (2026-09-27)**: built step 8 ("the brain," points #4/#5 —
  confirmed to be one combined agent, not two, per the design's own
  words) with an honestly narrower v1 scope than the full design: reads
  Layer 0 (`reflection_beliefs`) only since Hindsight has no real client
  anywhere in this codebase yet; produces a 6-axis maturity profile (one
  per analyst cluster) plus an optional bounded suggestion via one LLM
  call, gated by its own opt-in knob; self-trust tracking is mechanical
  (checked against real subsequent belief state), not a second LLM call
  grading the first. New `reflection_synthesis_outcomes` table
  (`vinu-infra`, the design's own 12-column spec, exactly). Never places
  an order or touches the kill switch. Step 9 (wiring a real consumer to
  act on the brain's output) deliberately not built — checked first that
  every named consumer (Planner/risk_gatekeeper/capital_allocator) is
  already a dependency *of* `vinu-reflection`, so any of them reading it
  back in-process would be a real circular package dependency; an HTTP
  surface is structurally required and is real, separate, correctly
  scoped follow-up work. 24 new tests, zero regressions
  (`vinu-infra` 327 passed; `vinu-reflection`'s own full suite can't run
  in this environment at all — confirmed pre-existing via direct
  traceback on untouched sibling files, same `vinu_agent`/`vinu_live`
  install gap as elsewhere this pass — but every file this pass touched
  runs clean in isolation: 18 passed).

This does not mean the rest of this folder's findings are resolved —
items #4, #5, #10, #16, and real pieces of
#11/#14/#15/#19/#20/#21/#22/#25/#26 are still open, each
one marked honestly inline with a dated UPDATE where something has
actually changed, not silently assumed fixed. Item #3 is now fully
fixed (previously grouped with #2/#4/#5 as "not yet acted on" — it no
longer is, they still are). Item #12 (`vinu-research` inefficiency
audit) is now also fully closed — all 4 findings fixed. Item #13
(`vinu-simulator`) is now also
fully closed — every one of its 6 numbered findings fixed. Item #23's
own 6 findings are also now all either fixed or confirmed fine — no
numbered gap left open there. Item
#17's own 4 numbered
findings are now all closed, but its write-up also named two unnumbered
"confirmed gaps, not new items" (no contract/schema test between
agent↔research↔simulator, no `policy_version` field threading through
that chain) that remain genuinely unaddressed — real, just never given
finding numbers, so they don't show as an open finding count anywhere.
Item #18's own 4 numbered findings are also all closed now, with only
finding #4's optional full-delegation-to-vinu-tools alternative left on
the table (explicitly optional per that finding's own text). Check
`reverse-engineering/02-implementation-status.md` for the live-decision
loop's own up-to-date picture, and each item's own UPDATE notes in
`02-open-questions-strategy-and-simulation.md` for everything
else.
