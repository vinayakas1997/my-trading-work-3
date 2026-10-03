# Inconsistencies v2 — gaps against the vision, recorded, not solved

Companion to `../vision-trding-system.md` (WHAT+WHY), `../how-system-implemented.md`
(HOW+WHERE) and `../the-new-inconstienties/inconsitencies.md` (v1: seams between built parts).
Same format as v1: title, explanation, evidence, where found, solution, what it will achieve,
how it will be used. Nothing here is acted on — this is the list to work through.

**What v2 covers that v1 does not.** v1 lists places where something is built but not wired to a
decision (write-only data, prompts missing inputs, silent defaults). v2 lists things the vision
asks for, or that a mature trading stack normally has, which are **absent or only partly present**.
Items still open in v1 (A3, A4, A5, A7, A8, B3, B4, C1, C2, C3, C4, C6) are NOT repeated; see the
cross-reference index at the bottom.

**Verification status (read this first).** Written 2026-10-02 from the three docs above only,
following the standing rule to stay in the design docs during active changes. Code paths named
in "Where found" are copied from those docs (which say they were checked 2026-09-30); they were
NOT re-opened for v2. "Evidence" for an absent feature means: a keyword search of the three docs
returns nothing (terms and result stated per item). Before building any item, grep
`vinu-components/` once to confirm it is genuinely absent — an item may already exist under a
different name.

Outside reference: Freqtrade (GPL-3.0), cloned at
`personal-important/other-reference-repos/freqtrade`, second-pass notes in
`other-repos-world/comprison-other-vinu/01-freqtrade.md` (addendum 2026-10-02). Its code is a
reference for ideas only; do not copy — reimplement from the design.

---

## GROUP A — Validation gaps (nothing proves the numbers are trustworthy)

### A1. No test that a feature or signal leaks the future

- **Title:** Point-in-time is enforced at the data layer, but nothing tests a finished strategy for lookahead.
- **Explanation:** The system is strong on *preventing* leakage: `as_of` clamping on stock and news
  reads, `before_ts` walk-forward in KNN, `news_confound` limited to "≤ trigger", PBO/CSCV and
  holdout gates against overfitting. What is missing is the *detective* control: re-run a
  strategy/feature on data truncated at time T and check that the signal at T is unchanged. A
  custom strategy (`POST /simulate/custom`) or an LLM-generated one can still peek (e.g. a
  full-series `.shift(-n)`, a whole-window normalization) without tripping any current gate.
  The AST guard blocks sandbox escapes, not future-looking math. This is the single most
  relevant check for the meta-labeling feature set.
- **Evidence:** Keyword search of all three docs: `lookahead` → 0 hits, `leak` → 0 hits,
  `look-ahead` → 1 hit, and that hit is a design note on news-confound, not a test
  (`vision-trding-system.md:215`). Gates listed in the vision: hard filters, K-cap, Monte Carlo,
  holdout, PBO — all overfitting controls, none leakage controls.
- **Where found:**
  - Preventive controls (exist): `vinu-infra/point_in_time.py` `clamp_to_as_of()`;
    `vinu-strategy/.../service.py` `evaluate(..., as_of)`; `vinu-initial-analysis/.../trend_lifecycle/patterns.py:93` `find_similar(before_ts)`
  - Gap location (where a check would sit): `vinu-simulator/vinu_simulator/engine/custom_sim.py` `simulate_custom()`, `engine/ast_guard.py` `validate_code()`, and the research gate chain (`vinu-research/.../gates/`)
  - Reference design: `freqtrade/freqtrade/optimize/analysis/lookahead.py`, `lookahead_helpers.py`, docs `lookahead-analysis.md`
- **Solution:** Add a `lookahead_check` step: for a strategy/feature set, compute signals on the full
  series, then recompute on N truncated prefixes (say 5–10 cut points) and compare the signal
  at each cut point bar. Any mismatch = leakage, with the offending feature named. Run it (a) inside
  `simulate_custom` as a warning first, (b) as a research gate before promotion. Start with
  features only (cheap) before whole strategies.
- **What it will achieve:** Turns "we believe nothing peeks" into a measured result per strategy;
  catches the failure that overfitting gates cannot, since a leaking backtest looks like a
  brilliant, robust edge.
- **How it will be used:** Verdict recorded in `strategy_evaluation_history` as a new step; failing
  strategies never reach the promotion gate; the result is cited in the Trade Score `regime`/`risk` narrative.

### A2. No test that a feature depends on how much history was loaded

- **Title:** Warmup sizing exists, but there is no check that a feature gives the same value on 300 bars as on 3000.
- **Explanation:** Recursive indicators (EMA, Wilder ATR/ADX, MACD signal) depend on the starting
  point. The live detector sizes its history with `warmup_bars_for_features` so live values should
  match backtest, and ADX/ATR Wilder bugs were fixed once in `vinu-tools`. But nothing *measures*
  the divergence between a short live window and the long backtest window for a given feature,
  so a mismatch is only found by accident (as the ADX/ATR bugs were). Related to the open v1 note
  that `trend_lifecycle/snapshots.py` keeps a private ~90-line RSI/MACD/ATR/ADX with real divergences.
- **Evidence:** Keyword search: `recursive` → 0 hits. Warmup handling is documented
  (`how-system-implemented.md` §4, §14: `warmup_bars_for_features`, `min_warmup_bars()`), but as a
  sizing rule, not a test.
- **Where found:**
  - `vinu-tools/vinu_tools/compute/registry.py:330` `warmup_bars_for_features()`, `:346` `apply_indicators()`
  - `vinu-live/vinu_live/live_decision/detector.py` `compute_live_snapshot`, `min_warmup_bars()`
  - `vinu-initial-analysis/.../trend_lifecycle/snapshots.py` (private copy, deliberate non-fix per v1 pattern #2)
  - Reference design: `freqtrade/freqtrade/optimize/analysis/recursive.py`, docs `recursive-analysis.md`
- **Solution:** A pure-function test harness over `apply_indicators`: compute each registered indicator
  at the same target bar using startup windows of increasing length (e.g. 100/200/500/2000 bars) and
  report the drift. Fail the indicator if drift at `warmup_bars_for_features` length exceeds a
  tolerance. Run as a test over the whole registry, not a runtime gate. Include the `snapshots.py`
  copy so its divergence is quantified before any migration decision.
- **What it will achieve:** Proves (or disproves) that the warmup rule actually delivers
  live-equals-backtest numbers; gives the `snapshots.py` migration decision a number instead of a worry.
- **How it will be used:** Registry-wide test in CI; any new indicator must pass before it is
  blessed; the drift table feeds the "migrate / version-tag / freeze" decision recorded as deferred.

### A3. No backtest-vs-paper/live parity check

- **Title:** Results are produced in backtest and in paper, but nothing compares them to measure the gap.
- **Explanation:** The vision's #12 asks for backtest → walk-forward → paper → small-live → scaling,
  and the maturity tier is driven by paper days and trade counts. But the docs record no step that
  takes the same strategy's backtest expectation (return, hit rate, slippage, trade count) and
  compares it with what paper/live actually produced over the same window. `decay.py` watches
  degradation over time and `consistency_freeze` (analysis H) checks live-vs-backtest consistency,
  per the reflection analyst list, but the parity result is not a consumed signal for sizing,
  tier, or promotion.
- **Evidence:** Keyword search: `parity` → 0 hits. `consistency_freeze` appears only as an analyst
  name in the 24-analyst list (`how-system-implemented.md` §17). `paper_live_correlation` also
  appears as an analyst name only. Whether either feeds a decision is not stated in the docs.
- **Where found:**
  - `vinu-reflection/vinu_reflection/reflection/consistency_freeze.py`, `paper_live_correlation.py` (names per §17; contents not re-read)
  - `vinu-research/.../maturity_assessor.py` `assess()` (uses accuracy and paper days, not backtest-vs-actual deltas)
  - `vinu-research/vinu_research/decay.py`
- **Solution:** First confirm what `consistency_freeze` and `paper_live_correlation` actually compute
  (read both). Then define one `parity_report` per strategy: expected vs realized for return/bar,
  hit rate, slippage bps, trade frequency, over a matched window. Write it as a belief row and a
  `strategy_evaluation_history` step; surface it in `get_live_decision_context` as an advisory field.
- **What it will achieve:** The point of paper trading becomes measurable — "paper matches backtest
  within X" is what should unlock `early_live`, not just a day count.
- **How it will be used:** Tier rule (see v1 A7) can require a parity pass for `mature`; promotion
  and capital gating cite it; a large parity gap is a decay and data-quality alarm.

---

## GROUP B — Uncertainty and abstention (the "I don't know" path)

### B1. No input-novelty (out-of-distribution) check on the model/score path

- **Title:** OOD exists as a regime-level kill-switch trigger, not as a per-prediction "this input is unlike training" abstain.
- **Explanation:** The vision lists "OOD-regime" among kill-switch triggers (A18) and the system
  has regime classification and `regime_drift` analysis. What the docs do not describe is a
  per-input novelty measure on the scoring path: when the current feature vector is far from the
  data a calibrated threshold or model was fitted on, the Trade Score and any ML component should
  abstain or shrink, instead of scoring with full confidence. This is the concrete mechanism behind
  the partially-built "I don't know" item (vision A5) and a natural input to the missing single
  uncertainty score (B2 below).
- **Evidence:** Keyword search: `outlier` → 0, `out-of-distribution` → 0; `OOD` → 1 hit, the
  kill-switch trigger list (`vision-trding-system.md:160`). Vision A5 itself states: "no single
  confidence abstraction. Left open honestly."
- **Where found:**
  - `vinu-research/vinu_research/trade_score_calibration.py` and `gates/trade_score_gate.py` `compute_trade_score()` (scoring path, no novelty input per docs)
  - `vinu-live/vinu_live/live_decision/detector.py` `compute_live_snapshot` (51 live features — the vector to measure)
  - Reference design: `freqtrade/freqtrade/freqai/data_kitchen.py`, `freqai_interface.py`; docs `freqai-feature-engineering.md` § Outlier detection (Dissimilarity Index, one-class SVM, DBSCAN)
- **Solution:** Implement the simplest member first — Dissimilarity-Index-style: for a live feature
  vector, mean distance to its nearest training points, compared with the training set's own average
  nearest-neighbor distance. Store the training reference with each calibrated threshold set
  (`trade_score_calibration.json`). Output a `novelty` value in the live snapshot; above a
  configured ratio, Trade Score tier is capped one level and the decision context carries
  `novelty_high`. Log-only first, enforce later (same policy as v1 C6).
- **What it will achieve:** A real, measurable reason to say WAIT ("this looks unlike anything we have
  evidence for") rather than scoring every input confidently.
- **How it will be used:** Feeds the single uncertainty score (B2), the live-decision prompt, the
  `evaluation-status` view, and reflection's `regime_drift` analyst.

### B2. No single uncertainty / confidence abstraction

- **Title:** Uncertainty is spread across gates and fail-open defaults; no one value says "how much do we not know".
- **Explanation:** Already acknowledged as partial in the vision and `already-built.md`. Pieces that
  would feed one score exist or are filed: trade-score tier, correlation gate, calibration gate,
  `StrategyEvaluationStore` status, maturity tier, evidence confidence (Laplace), and — if built —
  novelty (B1), parity (A3) and v1's `confidence_gaps[]` (C6). They are never combined, so the
  system cannot state a single "uncertainty" level in its audit or sizing.
- **Evidence:** Vision A5 verbatim: "expressed indirectly via independent gates ... no single
  confidence abstraction." v1 C6 records six independent fail-opens with "no combined flag exists."
- **Where found:**
  - `vision-trding-system.md` A5; `already-built.md` "Partially built"
  - Inputs: `vinu-infra/strategy_evaluation.py`, `maturity_consultation.py`, `evidence_confidence.py`; `trade_score_gate.py`
  - v1 cross-reference: `the-new-inconstienties/inconsitencies.md` C6
- **Solution:** Define one small read-only object, `UncertaintyAssessment{level: low|medium|high,
  reasons[], missing_inputs[]}`, computed from the inputs above by a pure function, with no new
  gate. Attach it to the decision context, the evaluation status, and the audit log. Level may only
  *lower* size or add wording once log-only data shows it behaves; never override a risk limit.
- **What it will achieve:** Closes vision A5 with a concrete, queryable artifact; makes "I don't know
  because inputs were missing" distinguishable from "I know and I am neutral".
- **How it will be used:** Prompt line for the live-decision and forecast agents; sizing scaler
  input after a log-only period; reflection tracks the share of high-uncertainty periods.

---

## GROUP C — Control-path gaps (the system cannot act on what it already knows)

### C1. No per-symbol loss lockout with expiry

- **Title:** Portfolio-level kill switch and breakers exist; a repeatedly-losing single symbol is not locked out.
- **Explanation:** The system has a hard kill switch (`_halt_trading`), a drawdown ladder
  (ok/halve/flat/halt), daily-loss/VaR/cluster/leverage limits, and K-cap on idea intake. None of the
  documented controls says: "N stop-outs on this symbol within W bars → no new entries on it until T".
  A symbol the strategy keeps re-entering after stops would only be slowed indirectly via decay
  or the Trade Score calibration. A lock needs an expiry and a reason so it is auditable and
  reversible, and must never block risk-reducing orders (`reduce_only` exemption, a stated strength).
- **Evidence:** Keyword search: `lockout` → 0, `cooldown` → 0. Existing controls listed:
  `vision-trding-system.md` A6/A18, `how-system-implemented.md` §12, §13, §19.
- **Where found:**
  - `vinu-live/vinu_live/breaker/engine.py:139` `check_limits()` and `breaker/limits.py` `DEFAULT_LIMITS`
  - `vinu-live/vinu_live/live_decision/state_tracker.py` (stage lifecycle: `expired` exists, no symbol lock)
  - `vinu-portfolio/vinu_portfolio/circuit_breakers.py`
  - Reference design: `freqtrade/freqtrade/plugins/protections/` (`stoploss_guard.py`, `low_profit_pairs.py`, `cooldown_period.py`, `iprotection.py`), `protectionmanager.py`
- **Solution:** A small lock store keyed `(symbol, scope)` with `(reason, locked_at, until)`, written by a
  pure `evaluate_protections(trade_history)` that counts recent losing exits per symbol. The live
  scheduler consults it before sizing; locked symbols contribute no new-entry weight but still allow
  reduces and exits. Record every lock/unlock to the audit log and `rejection_log`
  (`RejectionRecord`, `rejection_category=symbol_locked`). Already adopted in principle as the
  `IProtection` item in `01-freqtrade.md`; this entry is the concrete Vinu-side spec.
- **What it will achieve:** Stops a strategy from repeatedly bleeding on one name, with a visible
  reason; reuses the existing rejection-log shape instead of a new mechanism.
- **How it will be used:** Scheduler pre-order check; shown in `evaluation-status/by-ticker`; counted
  by reflection (`mandate_limit_friction` analyst).

### C2. REDUCE and ADD are not available to the live loop

- **Title:** The vision's four live actions are HOLD/ADD/REDUCE/EXIT; only two are implemented.
- **Explanation:** Deliberately not built because no mechanism exists to size a *change* to an open
  position: `live_decision_position_size` is one flat number per strategy, and open positions are
  re-emitted from stored size every cycle. Consequence: a decaying thesis (Trade Score 82→63) can
  only HOLD or fully EXIT, so the vision's graduated response ("reduce on decay") is lost. v1 notes
  it as deferred, not as a defect; v2 records it because it blocks the vision's thesis-decay story.
- **Evidence:** `how-system-implemented.md` §14: "REDUCE/ADD not built"; vision A9: "deliberately
  not built — no sizing mechanism exists"; vision B13 lists it under deferred decisions.
- **Where found:**
  - `vinu-live/vinu_live/live_decision/poller.py` `_trigger_position_review` (HOLD keeps / EXIT closes)
  - `vinu-live/vinu_live/live_decision/storage.py` `live_decision_open_positions` (one stored size per position)
  - `vinu-live/vinu_live/scheduler.py` (re-emits stored size each cycle)
- **Solution:** Do not add ADD yet (risk-increasing, needs full sizing). Add REDUCE only: a review
  response may carry `reduce_to_fraction` in (0,1); the open-positions row updates its stored size by
  that fraction; the scheduler already re-emits the stored size so the sell happens via the existing
  not-targeted/lower-target path. REDUCE is risk-reducing, so it can reuse existing exemptions.
  Evidence for when to reduce comes from thesis-score decay once the bucket table (D1) has rows.
- **What it will achieve:** The graduated exit the vision describes, without any new order path.
- **How it will be used:** Review mode returns REDUCE; audit row records old and new size; reflection
  compares reduce-vs-hold outcomes later.

---

## GROUP D — Waiting on data or a decision (recorded so they are not forgotten)

### D1. Bucket table (Layer-4 trust number) not designed

- **Title:** The probabilistic trust number for a setup needs accumulated rows that do not exist yet.
- **Explanation:** The agent reasons from raw counts plus a qualitative `confidence_note`. The
  bucket table would turn "34 triggers, 58% positive" into a calibrated probability for a setup
  bucket, and give the reviewer unrealized P&L and confidence. Deferred on the rule "revisit on data
  volume, not date". It also gates item C2 (when to reduce) and part of B2.
- **Evidence:** `how-system-implemented.md` §12 point 9 and the "still honestly open" list;
  vision B12.9, B13.
- **Where found:** `vinu-research/.../storage/signal_evidence_store.py`; `vinu-infra/evidence_confidence.py` `summarize_by_regime`; design only in `reverse-engineering/07-bucket-table-deferred.md`.
- **Solution:** No build. Add a data-volume check (row counts per candidate bucket) to the
  reflection brain so it reports "N of M buckets have ≥ min_sample rows" and the decision to start is
  made from that number, not a date.
- **What it will achieve:** Removes guesswork about when the table can be built.
- **How it will be used:** Review milestone for D1, C2 and the uncertainty score's trust inputs.

### D2. Hindsight client unwired

- **Title:** The reflection brain reads Layer-0 beliefs only; the long-term memory server has no client.
- **Explanation:** `hindsight-llm` is a local LLM server but nothing calls it. The brain's step-8
  synthesis was built "narrower than vision" (Layer-0 only) by design.
- **Evidence:** `vision-trding-system.md` B1, B9 Q4: "no Hindsight client exists anywhere".
- **Where found:** `hindsight-llm/` (server); `vinu-reflection/.../reflection/brain.py`.
- **Solution:** Leave unbuilt until Layer-0 synthesis shows a measurable limit; then add a read-only
  client behind a flag, fail-open like every other consultation.
- **What it will achieve / How it will be used:** Longer-horizon memory for the brain once there is
  something Layer-0 cannot answer; not before.

### D3. Crypto execution layer, order-book depth, on-chain data

- **Title:** Three capabilities deferred for an external reason (market scope, paid tier, no consumer).
- **Explanation:** The system executes equities through Alpaca only. Order-book depth is behind a
  paid tier. On-chain ingestion has no consumer until crypto is traded. If crypto becomes a target,
  these arrive together with an exchange layer, futures realism (funding, liquidation, leverage) in
  the simulator, and a crypto pairlist filter set.
- **Evidence:** Vision A14, B13; `already-built.md` "Explicitly deferred".
- **Where found:** `vinu-live` (Alpaca broker path); Reference design: `freqtrade/freqtrade/exchange/`, `freqtrade/leverage/`, `plugins/pairlist/` (spread, delist, volume filters).
- **Solution:** Decision first, code second: choose crypto yes/no and venue, then spec the broker
  abstraction, the simulator's perp-cost model, and the universe filters as one design. Reimplement,
  do not copy (GPL-3.0).
- **What it will achieve / How it will be used:** Prevents building any of the three piecemeal
  with no consumer.

---

## Index — what to do first

- **Highest value, low risk:** A1 (lookahead test), A2 (warmup-drift test), B2 (read-only
  uncertainty object, log-only).
- **Needs a read of existing code first:** A3 (what `consistency_freeze` and `paper_live_correlation`
  already compute), B1 (where calibrated thresholds are stored, to attach a training reference).
- **Needs your go-ahead (touches live behavior):** C1 (new lock can stop entries), C2 (REDUCE
  changes live size).
- **Waiting on data or a decision, nothing to build now:** D1, D2, D3.

### Cross-reference — v1 items still open (not repeated here)

A3 sweep winners/`param_diff` not persisted · A4 `code_hash` never queried · A5 single-angle
snapshots · A7 maturity `brier_mean`/`live_fraction` ignored · A8 `precondition_held` never blocks
(live money, needs go-ahead) · B3 forecast prompt inputs · B4 generation/refinement prompt inputs ·
C1 stuck unrecognized live decisions · C2 unsized EXECUTE forgotten · C3 fail-open/closed matrix
undocumented · C4 degraded runs / unfunded sleeves hard to find · C6 stacked fail-opens.
Closed 2026-09-30 in v1: A1, A2, A6, B1, B2, B5, B6, C5.

Interactions worth noting when ordering work: v1 C6 `confidence_gaps[]` and v2 B1 novelty both feed
v2 B2; v2 A3 parity is the natural input to v1 A7 (`mature` requires proven live behavior); v2 C2
REDUCE needs v2 D1 data to decide *when*, but not to exist.

---

## UPDATE (2026-10-02, after reading the code) — corrections to items above

v2 was written from the docs only. A code read the same day (`02-logic-audit-2026-10-02.md`) found four items overstated.
Original text above is left as written; read it together with these notes.

- **C1 — partly wrong.** A portfolio-wide consecutive-loss cooldown exists in `vinu-live/trade_plan/orchestrator.py:99-145`
  (`VINU_LIVE_COOLDOWN_LOSSES=2`, `..._HOURS=24`, entries only, exits never blocked, fails open). It is **not** per-symbol and
  runs only on the trade-plan path, not the scheduler path. The per-symbol lock with expiry and reason is still absent.
- **C2 — wrong for the orchestrator.** REDUCE exists there (contingency `reduce_position`, rebalance honoring, runtime
  correlation trim, `reduce_only` exits) and ADD exists as TWAP entry slices (`_ACTION_CLASS_MAP`, `orchestrator.py:550-610`).
  Still true only for the live-decision path (`HOLD`/`EXIT` only).
- **B1 — partly wrong.** A dormant (`VINU_LIVE_OOD_DETECTOR=off`) 4-signal book-level OOD detector with a Mahalanobis
  turbulence signal exists (`orchestrator.py:507-533`), plus an active per-symbol 14-day-vol entry pause. Per-prediction
  feature-novelty on the scoring path is still absent.
- **A3 — evidence corrected.** `consistency_freeze` hashes environment variables and data-root files (drift check); it is not
  a live-vs-backtest comparison. `paper_live_correlation` checks whether paper return predicts live return. A backtest-expectation
  vs realized comparison is still absent.
- **A1, A2, B2, D1-D3 — unchanged.** (A1: the simulator already prevents look-ahead with a one-bar shift
  (`simulator.py:131-145`); the missing piece remains a detective test.)
