# Implementation plan — pipeline-connection safety net, then the fixes

Written 2026-10-02. A plan only; nothing here is built. Source findings:
`02-logic-audit-2026-10-02.md` (code-verified), `01-inconsistencies-v2.md` (gaps vs vision, with corrections),
`../the-new-inconstienties/inconsitencies.md` (v1, seams still open).

## Goal

Stop discovering missing pipeline connections by accident. Two parts:

1. **Edge manifest + observer** — a declared list of "what should flow where", checked statically against the
   code and recorded at runtime, so anything that does not flow is visible and dated.
2. **Fix the known gaps**, each one verified by its edge turning green.

## Principles (carried from the audit series)

- Observe before enforce. Log first, change behavior later.
- Never block a trade from the observer. It must not raise and must not add latency to the order path.
- Fail open on optional paths, but record that it happened.
- Smallest reversible change first; no new schema when an existing store can carry it.
- Anything that changes live-money behavior needs explicit go-ahead and ships opt-in, default off.
- Every fix updates the manifest, adds a test, and appends a dated note to the audit docs.
- Reimplement ideas from outside repos (Freqtrade is GPL-3.0); do not copy code.

---

## Phase 1 — Edge manifest and static check (read-only, no behavior change)

**What:** one manifest file listing each edge on the money path (about 20): producer, output, consumer, what the
consumer does with it, expected cadence, whether "empty" is legitimate (reuse the empty-meaning contract, v1 C5).

**Starting edges** (from the audit):
`portfolio.daily_allocation → live.scheduler`, `portfolio.state → live.scheduler`, `research.trade_plan(ACTIVE) →
orchestrator`, `strategy.weights → portfolio`, `screener.top → planner-worker`, `live_decision.EXECUTE → scheduler`,
`signal_evidence → registry bridge`, `maturity.status → {live limits, portfolio capital, agent context}`,
`reflection.synthesis → idea_generator`, `drawdown_status → portfolio`, `halt flag → both executors`,
`guards (spread/event/freshness/cooldown) → both executors`, `breaker inputs (book) → scheduler`.

**Static check:** a test that fails if a declared consumer never calls its producer (by route or function).
First expected failures: `daily_allocation → scheduler` (audit A1) and the missing guards on the scheduler path (A4).

**Done when:** manifest committed, static test runs in CI, and its first failures match the audit's findings.

## Phase 2 — Fixes that need no decision

Each one flips an edge in the manifest and gets a test.

| Item | Change | Source |
|---|---|---|
| Share guards across both paths | Move cooldown, data-freshness, turbulence, stale-signal into `trade_plan/guards.py` as pure functions; call from scheduler, **entries only** | audit A4 |
| Fail-closed approval | `approve_trade_plan` rejects a plan whose `expected_drawdown` and `cvar_95_limit` are both 0 (`risk_not_computed`) | audit B2 |
| Stop / age for live-decision positions | Optional `stop_pct`, `max_hold_bars` on the open-position row (default off); poller treats a breach as EXIT without the LLM | audit A3 |
| Open v1 wiring items | `code_hash` into sweep rows and the graveyard join, `param_diff` persisted, forecast and generation prompt inputs, unsized-EXECUTE queue, stuck-decision counters, degraded-run visibility | v1 A3, A4, B3, B4, C1, C2, C4 |

**Done when:** each item has tests through real stores, suite pass-count delta recorded, audit docs updated.

## Phase 3 — Runtime recorder and heartbeats

**What:** a small shared helper in `vinu_infra` called at each consumption point; writes `received | empty |
stale | missing` to one SQLite table (edge id, status, last seen, count, last change). Record state changes plus
heartbeats, not every call. An "edges not flowing" view lists any edge with no recent success.

**Reuse:** `StrategyEvaluationStore` step registry, `MaturityConsultationStore`, the empty-meaning contract.
No fourth store if one of those can hold it.

**Surface:** one read-only route (alongside `/research/evaluation-status`) and an entry in the evaluation view.

**Done when:** every Phase 1 edge reports a status; stopping a service makes its outgoing edges go stale within
their declared cadence; helper has a test proving it never raises and never blocks.

## Phase 4 — Decisions that change live behavior (need explicit go-ahead)

Opt-in flags, default off, fail open to today's behavior.

| Item | Options (recommendation first) | Source |
|---|---|---|
| Exits exempt from halts and gates on the scheduler path | Mark reducing instructions, send `reduce_only`, bypass spread / event / halt-skip for them only | audit A5 -- DONE 2026-10-03, opt-in flag |
| Executor ownership of symbols | (1) scheduler restricts `current_positions` to symbols it manages; (2) ownership registry; (3) retire one path | audit A2 -- DONE 2026-10-03, opt-in flag (ownership = open book position or ACTIVE trade_plan); new finding: held-but-untargeted positions are never priced, see status doc |
| Which allocation contract the scheduler uses | (A) call `/portfolio/daily-allocation`; (B) scale inside `build_portfolio`; (C) fetch a deployable fraction | audit A1 -- DONE 2026-10-03, opt-in flag (option A) |
| Breaker inputs | Source daily P&L and exposure from the broker account for the scheduler path; add unrealized to the daily-loss test | audit A6-- DONE 2026-10-03, opt-in flag |
| Precondition enforcement | `precondition_enforcing_enabled`: scheduler skips EXECUTE with `precondition_held=false` | v1 A8-- DONE 2026-10-03, opt-in flag |
| Live window length | Enlarge the live feature window to ~3x the longest EMA period, or stop using absolute `ema_100`/`ema_200`/`obv` levels in live must-conditions | audit A8 (found 2026-10-03)-- DONE 2026-10-03, opt-in flag (supertrend/obv levels still not comparable) |
| Confidence recalibration | Reliability map from stated confidence to realized hit-rate, minimum sample, log-only first; drop the confidence entry from the confluence ledger | audit B1 -- DONE 2026-10-03 (log-only on; in-EV and confluence flags off) |
| Capital fallback | Use the `fallback_portfolio_value` placeholder only when the broker reports `configured: false`; abort the cycle on an error or non-200 from a configured broker | audit A7 (found 2026-10-03) -- DONE 2026-10-03, opt-in flag |

**Before any real money:** A5, A2, A1, A6 and A7 must be decided and done. (Done as opt-in flags: A5, A2, A1, A6, A7; the flags must also be switched on.)

## Phase 5 — New safeguards from the gap list

Order by value for effort. Reference design from Freqtrade where noted.

1. **Lookahead test (v2 A1):** re-run signals on truncated prefixes at several cut points and flag any change;
   features first, then whole strategies. Runs inside `simulate_custom` as a warning, then as a research gate.
   *(Freqtrade: `optimize/analysis/lookahead.py`.)*
2. **Warmup-drift test (v2 A2):** compute each registered indicator at the same bar from windows of increasing
   length; fail past tolerance at the declared warmup. Include the private `trend_lifecycle/snapshots.py` copy.
   *(Freqtrade: `optimize/analysis/recursive.py`.)*
3. **Uncertainty object (v2 B2):** one read-only `UncertaintyAssessment{level, reasons[], missing_inputs[]}` built
   from existing inputs plus the recorder's missing-input list. Log-only first.
4. **Input-novelty check (v2 B1):** distance of the live feature vector from the calibration data; cap the tier
   one level when high. *(FreqAI: Dissimilarity Index.)*
5. **Backtest-vs-paper parity report (v2 A3):** expected vs realized return, hit rate, slippage, trade frequency **DONE 2026-10-03 (read-only report; paper = code replay, so stability not execution parity)** Execution-parity data **DONE 2026-10-03** (scheduler order ledger with fill price and slippage; a consumer comparing it with the backtest cost model waits for paper data)
   over a matched window; advisory field in decision context; later an input to the `mature` tier (v1 A7).
6. **Per-symbol loss lockout with expiry (v2 C1):** on top of the existing portfolio-wide cooldown, with
   `RejectionRecord` and `reduce_only` exemption. *(Freqtrade: `plugins/protections/`.)*

## Phase 6 — Enforcement, once data exists

- Turn recorder gaps into behavior: three or more missing inputs → treat as one tier colder (v1 C6).
- Bucket table, REDUCE for the live-decision path, `mature` requiring proven live fraction. All wait on accumulated
  live rows; review by row count, not by date (v2 D1).
- Crypto path (exchange layer, futures-aware simulator, crypto universe filters) only after a market decision (v2 D3).

---

## Verification standard (every phase)

1. Verify the claim in code before building (audits go stale).
2. Test through real SQLite / JSON stores via `tmp_path`; mock only HTTP, LLM, other processes.
3. Record exact before/after test counts for the affected file and the full service suite; if a suite has known
   failures, confirm the failing names are unchanged.
4. Append a dated UPDATE to the relevant audit doc; keep history, never rewrite it.
5. Update the edge manifest so the change is reflected as a flowing edge.

## Open questions for you (answer before Phase 4)

1. Do trade-plan symbols and portfolio-strategy symbols ever overlap on the same account in your deployment?
2. Which allocation contract do you prefer for the scheduler (A, B or C)?
3. Is a paper-to-real-money date set? That decides whether Phase 4 can wait.

## Not covered by this plan (not yet audited)

`vinu-stock-price`, `vinu-news`, `vinu-tools` indicator numerics, `vinu-screener`, the 30 analysis angles,
`vinu-agent` prompts and teams, most reflection analysts, `vinu-ui`. A further audit pass on those is a separate task.
