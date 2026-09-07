---
name: agentic-workflow-current-architecture
status: current v2 — 2026-09-07 — reflects A1-B build slices (rehearsal, replace, shock batch, composition, sizing decided)
purpose: same as v1 (04-new-full-explanation.md 2026-08-17) but with "What's still not built" and open questions updated after 10 commits 3939f1a7..75025b72. Keeps v1 as snapshot.
---

# Agentic workflow — current architecture (v2 2026-09-07)

This is the pipeline as it actually runs today after the 7-stage + 2-entry + 4-cross-cutting build. Unlike `04-new-full-explanation.md` v1 (2026-08-17), the four items in its "What's still not built" are now built, and the open questions in that file are now decided/pinned (see `pending-items-to-be-implemented.md` Status 2026-09-07 and `other-our-repo-full-research-features/decisions/`). Keeps the same diagram — only dotted/built annotations moved.

## The diagram

```mermaid
flowchart TB
    RL[("vinu-initial-analysis<br/>RunLog — new run_id<br/>for this symbol?")] -.-> GATE
    WL(["Watchlist entry point"]) --> GATE

    GATE{"Changed since last Planner<br/>pass on this ticker?<br/>(cheap deterministic check,<br/>no LLM call)"}
    GATE -->|"no — advance to the<br/>NEXT ticker in the watchlist<br/>(not a retry of this one)"| WL
    GATE -->|"yes"| SA

    subgraph ENTRY2 ["Second entry point — parallel to the watchlist path above, not chained off it"]
        direction TB
        HTHEORY(["Human's own theory<br/>(idea/analogy, not code)"]) --> THGATE
        THGATE{"Near-duplicate theory,<br/>OR this ticker already at its<br/>K-candidate cap this cycle?<br/>(cheap HR + Planner-counter<br/>check, no LLM call)"}
        THGATE -->|"yes — DISCARD this<br/>submission, wait for the<br/>next one (not a retry)"| HTHEORY
        THGATE -->|"no — new enough"| TI
        SKILLDOC[/"skills/&lt;name&gt;/SKILL.md<br/>(strategy-definitions +<br/>risk-rules sections)"/] -.->|"load_skill(...)"| TI
        TI["<b>Thesis Intake</b><br/>(matches a human's theory<br/>against real evidence; writes<br/>NO code, only compares/verdicts)"]
    end
    TI -->|"worth checking"| P
    TI -.->|"reads + writes,<br/>tagged source=human<br/>(reuses HR, no new store)"| HR
    TI -.->|"reads"| TL
    THGATE -.->|"reads"| HR

    SA["<b>1. Summary Agent</b><br/>(screener / angle_synthesizer)"]
    SA --> P

    P["<b>2. Planner</b><br/>(ticker/strategy fit triage<br/>+ idea_generator)<br/><i>cheap-model tier for routine passes;<br/>checks ALL non-terminal statuses;<br/>at most K distinct candidates per<br/>ticker per cycle — ONE shared<br/>counter across BOTH entry points,<br/>watchlist and Thesis Intake alike</i>"]
    P --> RE

    RE["<b>3. Researcher / Executor</b><br/>sweep + self-verdict + paper-trade<br/><i>internal sweep-refine loop capped<br/>at N rounds; fail-closed below a<br/>completeness threshold</i>"]
    RE -->|"self-verdict: FAIL<br/>reasoning recorded"| P
    RE -->|"self-verdict: PASS"| RG

    RG["<b>4. risk_gatekeeper</b><br/>(portfolio-fit check)"]
    RG -->|"REJECTED"| P
    RG -.-> SIG
    RG -->|"APPROVED"| PEND

    PEND[("Approved, pending allocation<br/>(not mark_active yet)")]
    PEND --> CA

    CA["<b>5. capital_allocator</b><br/>(+ rebalancer/negotiator)<br/><i>runs on a cadence over the whole<br/>pending batch, not per-candidate<br/>as each arrives; rebalancer<br/>REQUESTS only, never closes;<br/>re-checks exposure snapshot<br/>right before funding; validates<br/>NEW-vs-NEW correlation within<br/>the batch; checks Kill Switch<br/>before mark_active</i>"]
    CA -->|"funded — mark_active<br/>(only if Kill Switch clear AND<br/>fresh exposure check passes)"| LS
    CA -->|"funded but Kill Switch<br/>engaged — held, not ACTIVE"| PENDBLOCK
    CA -->|"rebalance REQUEST<br/>(BLOCKED by Kill Switch too,<br/>by default — see KS below)"| MON

    PENDBLOCK[("Funded, blocked by<br/>Kill Switch (not ACTIVE —<br/>storage never lies about<br/>what's actually live)")]

    LS["<b>6. Live + Shadow</b><br/>(parallel paper twin,<br/>no LLM, continuous)"]
    LS --> MON

    MON["<b>7. Monitor</b><br/>(sole authority on live-position<br/>close/hold — absorbs post-trade<br/>review; batches + prioritizes<br/>across open positions)"]
    MON -->|"decay / drop — write<br/>outcome + reason"| P
    MON -->|"hold"| LS

    HR[("HypothesisRegistry")]
    HR -.->|"must consult before<br/>proposing again"| P
    MON -.->|"writes closed-loop outcome"| HR

    CAL[("Calibration Tracker<br/>(built, spiked 2026-09-07<br/>next wire to Summary Agent)")]
    CAL -.->|"which angles to trust<br/>right now"| SA

    SHOCK(["shock_clustering /<br/>shock_personality angles"])
    SHOCK -.->|"event-driven trigger,<br/>not just periodic poll"| MON

    KS{{"Kill Switch<br/>(hard, non-LLM, always-on gate)"}}
    KS -.->|"blocks regardless<br/>of any verdict above"| LS
    KS -.->|"also blocks mark_active —<br/>funding and execution checked<br/>against the same gate"| CA
    KS -.->|"also blocks the rebalance<br/>REQUEST path, by default —<br/>halts all order-flow-adjacent<br/>actions, not just new funding"| CA

    SIG["Significance Triage<br/>(distinct from the passive<br/>digest reader)"]
    CA -.-> SIG
    MON -.-> SIG
    SIG -.->|"flags only what's<br/>unusual, not routine"| HUMAN(["Human"])
    HUMAN -.->|"override decision<br/>recorded as evidence,<br/>same path as Monitor's"| HR

    TL[("<b>Ticker Ledger</b><br/>plain SQLite,<br/>append-only, one row per<br/>ticker-relevant event")]
    TI -.->|"theory matched,<br/>verdict recorded"| TL
    SA -.->|"summary refreshed"| TL
    P -.->|"triage + proposal"| TL
    RE -.->|"sweep result + verdict"| TL
    RG -.->|"gate verdict"| TL
    CA -.->|"funded / rebalance request"| TL
    MON -.->|"check, decay, close-out why"| TL
    HUMAN -.->|"override"| TL

    SKILLAUDIT[("Skill-edit audit log<br/>ticker-agnostic —<br/>separate from TickerLedger")]
    SKILLDOC -.->|"any edit to a<br/>risk-rules section<br/>is logged here"| SKILLAUDIT
```

Three loop-backs make this a cycle, not a one-shot funnel:

1. **Researcher/Executor fail → Planner.** The failure reasoning is what
   the next proposal on that ticker has to address.
2. **risk_gatekeeper REJECTED → Planner.** The artifact stays wherever it
   was (BENCHING/MONITORING, unchanged) but the *reason* reaches the
   Planner so it isn't blindly re-proposed.
3. **Monitor decay/drop → Planner**, via `HypothesisRegistry`. Every
   closed position's lesson becomes an input constraint on the *next*
   proposal for that ticker.

A second **entry point** sits alongside the watchlist/change-gate one: a
human can hand the pipeline a raw theory via **Thesis Intake**, which
matches it against real evidence and, if it clears the bar, feeds it into
the Planner exactly like a system-generated idea. Same downstream loop
either way — only the front door differs.

Everything drawn with a dotted line is a cross-cutting mechanism, not a
pipeline stage — it can fire from more than one place.

## Where the ticker's full story lives — `TickerLedger`

Plain SQLite, append-only, one row per ticker-relevant event: `ticker,
timestamp, stage, event_type, text, ref_id, source`. Every stage writes
exactly one entry when something happens; `ref_id` points back to the
real record in whichever specialized store owns that data (`artifact_id`,
`run_id`, hypothesis id) — the Ledger is a narrative index, not a
duplicate copy. Every stage in the pipeline has exactly one natural entry
point into it: Thesis Intake's verdict, Summary Agent refresh, Planner's
triage+proposal, Researcher/Executor's sweep result and verdict,
`risk_gatekeeper`'s verdict, `capital_allocator`'s funding/rebalance
decisions, every Monitor check plus decay/close-out narrative, and any
human override.

Live + Shadow's bookkeeping is continuous, not event-shaped — it doesn't
write a row every tick. Only Monitor's periodic comparisons (reading the
shadow twin's current state) produce Ledger entries; the shadow ledger
itself stays a separate, high-frequency store the Ledger references.

Plain SQLite over a vector DB / memory layer on purpose: the real query
pattern is "every event for AAPL, in exact order" — exact-match plus
sort, which SQL does natively. This project leans on exact traceability
(`artifact_id`, `run_id`, never-invent-a-number grounding) as a core
discipline, and a system built to reinterpret/consolidate memories works
against that. A vector layer on top of the Ledger for fuzzy cross-ticker
analogical search is a real, later capability — not scoped now.

**Taxonomy pinned 2026-09-07** (pending Row 10): `stage` `watchlist_gate | thesis_intake | summary_agent | planner_triage | planner_idea | sweep_execute | sweep_verdict | risk_gatekeeper | capital_allocator | live_shadow | monitor | kill_switch_gate | significance_triage`; `event_type` `changed | unchanged | summary_refreshed | triage | proposal | sweep_complete | verdict_PASS | verdict_FAIL | APPROVED | REJECTED | PEND | PENDBLOCK | funded | rebalance_requested | rebalance_blocked | hold | decay | close_out | halt | resume | flag_created`; `source` `watchlist | human | human_override | system`; `ref_id` points to real row. Retention 90d / 1M rows then dated export — see `other-our-repo-full-research-features/decisions/10-ledger-decision.md`.

## Per-agent detail

### 1. Summary Agent (`screener` / `angle_synthesizer`)

Calls `get_all_angles(ticker)` once, reports how many of the ~31 angles
have real data, cites specific numbers from the ones that do, states what
to check next. Includes a cross-angle agreement/divergence check
(agree/diverge/insufficient) — do independent angles (e.g. `arima` vs
`chronos` forecast direction, `regime_analysis` vs `trend_lifecycle`)
actually agree. Verified live against a real model.

**Grounding discipline:** only treats an angle as informative if
`row_count > 0` — never invents a number. This is why it stays useful
even when most angles have no data yet: it says so plainly instead of
padding a confident summary.

**Trigger:** watches `vinu-initial-analysis`'s `RunLog` for a new
`run_id` per symbol — only then does the Summary Agent refresh, and only
then does the downstream change-gate have anything new to compare
against.

### 2. Planner (triage + `idea_generator`)

Two jobs in one role.

- **Triage:** for each watchlist ticker, reads the Summary Agent's stored
  read (`TickerSummaryStore`) and what's already running on it
  (`SqliteStrategyStore.list_artifacts_for_symbol`) — produces a fit tier
  (best/medium/least) and a priority informed by what's already ACTIVE.
  The status check spans every non-terminal state (CREATED, BENCHING,
  ACTIVE, MONITORING), not ACTIVE alone.
- **Idea shaping:** picks a recipe (`list_sweep_recipes`, wired into
  `idea_generator`'s recipe-first path) and a coarse parameter search
  space, tied to the angle characteristics that motivated it. Raw code
  generation is the exception path, not the default.

Consults `HypothesisRegistry` before proposing on a ticker — what's been
tried before, what failed and why. Only runs when the change-gate says
something actually changed, on a cheap/fast model tier by default; a
stronger model is reserved for tickers that flip to "needs a real look."

Caps itself at K distinct candidates per ticker per cycle — a shared
counter with Thesis Intake, so a human submitting many genuinely distinct
theories on one ticker can't push past the same budget from the other
door. **K=3 shared 2026-09-07** (`pending Row 7`, `VINU_AGENT_PLANNER_INTERVAL 1800s`).

### 2b. Thesis Intake (second entry point, alongside the Planner)

Takes a human's own theory — an idea or analogy, not code — and checks it
against the real evidence already gathered for that ticker
(`TickerLedger`, `HypothesisRegistry`, the Summary Agent's stored read).
Reads a strategy-definitions section (what shapes of strategy exist to
test a theory like this) and a risk-rules section (what would disqualify
it outright) via the skill pattern. If the theory holds up, it produces a
verdict — "worth checking" — and the theory enters the same Planner →
Researcher/Executor loop as a system-generated idea. If not, it says so
with the contradicting evidence.

Writes **no code, ever** — purely reads, compares, verdicts. The human's
theory is written into `HypothesisRegistry` tagged `source="human"` — no
separate store.

A cheap, deterministic check runs ahead of any LLM call: has a
near-duplicate theory already been evaluated for this ticker recently,
or is this ticker already at the shared K-cap this cycle? Only "no"
reaches an LLM.

Placeholder `skills/thesis-intake/SKILL.md` with `strategy-definitions` + `risk-rules` now exists (pending Row 11 `decisions/11-thesis-intake-decision.md`). Any edit to the risk-rules skill section is written to a ticker-agnostic
skill-edit audit log, separate from `TickerLedger`.

### 3. Researcher / Executor (one team, three roles, loops internally)

**Role a — receive the plan.** Takes the Planner's recipe + search space
and its reasoning.

**Role b — execute + back-propagate.** Runs the grid via
`run_sweep_candidate` (`vinu-research/sweep.py`, AST-based parameter
substitution) — deterministic Python, never LLM-authored code per
attempt. `run_parameter_sweep` (`vinu-agent/tools/run_parameter_sweep_tool.py`)
loops the grid internally and returns a ranked table via `comparison.py`'s
`rank_candidates` in one call instead of N LLM round-trips. Capped at N
rounds, same `max_iterations` pattern the `research` team's manager loop
already enforces. **N=5 `max_iterations` 2026-09-07** (Row 7, `VINU_RESEARCH_MAX_ITERATIONS`).

**Role c — self-verdict.** Reads the ranked table plus `pbo.py`'s
overfitting probability and the walk-forward stability verdict (both
folded into `sweep_evidence_verdict`) and decides PASS/FAIL. Treats
below-threshold `completeness` (N of M grid points actually succeeded, fail-closed <0.7) as
automatic FAIL, never a ranked PASS off partial data.

**Role d — paper-trade rehearsal. BUILT 2026-09-07.** Runs the winning
candidate through a trailing historical window (default 7 calendar days ≈5 trading days) bar-by-bar via the same `vinu-simulator/engine/simulator.py:32` `WeightSimulator` (T+1 + Almgren-Chriss `engine/costs.py:73` cost model) and stores `PaperRehearsalResult` before `risk_gatekeeper`. See `vinu-research/models.py:PaperRehearsalResult`, `config.py:paper_rehearsal_enabled`, `loop.py:_run_paper_rehearsal` `c3d94756`. Degradation >50% vs in-sample Sharpe (or negative rehearsal Sharpe) is a rehearsal fail, never blocks on no-data.

**Defining characteristic:** the LLM chooses which region of parameter
space to explore and interprets whether an improvement is real or noise
— it never computes the numbers itself.

**Accepted simplification 2026-09-07:** self-verdict is one voice, not
a bull/bear adversarial debate — kept for cost, mitigated by rehearsal + holdout 20% + 3-window walk-forward + PBO (see `decisions/06-verdict-decision.md`). Revisit if PASS + holdout fail >20%.

### 4. `risk_gatekeeper`

One spec in, one verdict out. Checks the already-approved candidate
against the real current portfolio — position sizing vs. account size,
correlation to what's already open — via `get_portfolio`. Position sizing is `fractional_kelly` quarter-Kelly `vinu-agent/agent/position_sizing.py:52` `full_kelly_fraction = (p*b - q)/b` ×0.25 with `fixed_fractional`/`atr_stop` fallback (`VINU_AGENT_POSITION_SIZING_METHOD`, `KELLY_FRACTION 0.25`, `RISK_PER_TRADE 0.02`, `ATR 2.0`) — **decided 2026-09-07** `decisions/05-sizing-decision.md`, not provisional. On `APPROVED`,
a manager-level Python hook moves the artifact into an "approved, pending
allocation" holding state instead of calling `mark_active` directly —
funding is `capital_allocator`'s decision, made across a batch.

Answers exactly one question — "does this fit current exposure" —
deliberately never re-litigates whether the strategy itself is sound.

REJECTED verdicts feed Significance Triage as well as the Planner loop-back
— a pattern of repeated exposure-driven rejections is signal a human
should see.

### 5. `capital_allocator` (+ rebalancer/negotiator role)

Ranks currently-ACTIVE artifacts by `deflated_sharpe`, funds
highest-ranked first, each capped at `approved_size` (risk_gatekeeper) and portfolio risk-parity weight × budget (`vinu-portfolio/service.py:210` `allocate_risk_parity` + `vinu-portfolio/evaluate-batch`), until
the budget runs out. Portfolio weighting adds bounded regime/outcome tilts (`compute_daily_allocation`) + vol-target 15% `sizing.py:14` — **decided 2026-09-07** `decisions/05-sizing-decision.md`.

Runs on a fixed cadence over the whole "approved, pending allocation"
batch since its last pass (`VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL 900s` `04:410` decided), not per-candidate as each clears
`risk_gatekeeper` — avoids first-come-first-served funding. Re-runs a
cheap exposure snapshot check immediately before funding, since an
approval can sit waiting for the next cadence run. Validates
NEW-vs-NEW correlation within the funded batch, not just each candidate
against the existing book.

The rebalancer role's unwind-request path is built and gated
(`capital_allocator_hook` → `rebalance_guard.check_rebalance_allowed` →
vinu-live's rebalance-request intake) — it never closes a position
itself, only sends Monitor a request. Monitor, as sole authority over
live-position close/hold, folds that request into its own judgment. **The "replace, not just fund" decision math — whether an existing, weaker ACTIVE strategy should be unwound to make room for a demonstrably better new one — is BUILT 2026-09-07:** `allocation_tool.py` emits `replace_recommendations` when best `PEND deflated_sharpe >= worst ACTIVE +0.8`, `capital_allocator_hook.py` deterministically emits the same `REQUEST` even when the LLM emits no `unwind` (same threshold), still via `RebalanceRequestQueue` → Monitor authority (`0c7cbb19`).

Checks the Kill Switch before calling `mark_active`; if engaged, the
artifact goes to a "funded, blocked by Kill Switch" holding state instead
— storage never claims a strategy is ACTIVE when the Kill Switch is
actually preventing it from executing. The Kill Switch also blocks the
rebalancer's request path by default (decided `block-all` `decisions/12-kill-switch-decision.md`).

Every funding decision reports a traceable reason per candidate — never a
black-box allocation. Composition gaps are now observable: `composition_view` `{gaps, suggestions}` on concentration >40%, max corr >0.8 (~ BUILT `7e4a0fe6`).

### 6. Live + Shadow (parallel execution)

`vinu-live/shadow_evaluator.py`'s `ShadowEvaluator` compares a BENCHING
artifact's paper-trading Sharpe against its backtest Sharpe and
auto-promotes to ACTIVE within tolerance. Runs on a real schedule
(`evaluate_all()` wired into a vinu-live worker); the
`/agent/broker/performance/{artifact_id}` endpoint it reads is live
(`routes_broker.py`, backed by `broker/performance_store.py`).

Once funded, the live position runs for real while an untouched paper
twin of the *original* plan runs in parallel, continuously, off the same
price feed. Pure deterministic bookkeeping — no LLM, no judgment.

At any moment, "what would this position be doing right now if left
alone" is a computed answer, not a guess. Pre-trade risk gateway now adds message throttle `10 orders/sec` `vinu-agent/broker/order_guard.py` `8325e893` (B20) and data lineage via `vinu_infra/freeze.py` `freeze_manifest()` `44e7e034` (B21) — tick wallet still spiked.

### 7. Monitor (decay-watch + post-trade review)

`vinu-live/trade_plan/orchestrator.py`'s `TradePlanOrchestrator` owns
entry, invalidation-exit, and contingency actions every cycle — sole
authority over a live position's lifecycle. Periodically **and on-event** (shock trigger) compares the live position
against its shadow twin, decides hold / flag / suggest-drop, and — when a
position actually closes — writes the "why" narrative using the shadow
twin's full path. Shock trigger is now **built:** `cycle_shock_batch(max_batch=5)` scores open positions by `shock_clustering` correlation + `shock_personality` `shock_score`, sorts descending, and runs `on_shock_event` debounced 60s per symbol for the top batch (`d4c338ea`, pending Row 3).

`capital_allocator`'s rebalancer can only request a close, never perform
one itself — Monitor is the sole authority.

Never places, modifies, or cancels a real order itself — only recommends
and records. Batching/prioritization is now built via `cycle_shock_batch`; plain periodic poll remains fallback.

## Cross-cutting mechanisms (not pipeline stages)

- **Calibration Tracker** (`vinu-research/calibration.py`, built, spiked 2026-09-07 next wire to Summary Agent) — would feed the Summary Agent which angles to actually trust right now, based on their own historical forecast accuracy. See `decisions/08-calibration-decision.md`. Different question from cross-angle agreement: "has this method been right *over time*" vs. "do the methods agree *right now*."
- **HypothesisRegistry** — the Planner's pre-proposal check, where
  Monitor's closed-loop outcomes get written, and where Thesis Intake
  reads/writes human-submitted theories (tagged `source="human"`).
- **Kill Switch — real, always-on.** Checked before every real order at
  Live + Shadow (`OrderGuard` now also throttles `10/sec` `8325e893`), before `capital_allocator` calls
  `mark_active`, and before the rebalancer's unwind request path
  (`rebalance_guard.check_rebalance_allowed`) — halting all
  order-flow-adjacent actions by default, not just new funding
  (`block-all` decided `decisions/12-kill-switch-decision.md`).
  `broker/kill_switch.py` has a cross-process file lock closing the
  check-then-act race.
- **Significance Triage** — distinct from `audit/research_digest.py`
  (real but purely passive). Actively judges which autonomous decisions
  are routine (skip) vs. unusual enough to surface to a human now. Fed by
  `capital_allocator`, Monitor, and `risk_gatekeeper`'s REJECTED
  verdicts. Closes the loop back: a human's decision is written through
  `HypothesisRegistry.add_evidence(...)` tagged `source="human_override"`.
  **Delivery to Telegram/Discord is code-complete but needs real
  credentials from the operator before it actually sends anything** — see
  `03-how-to-start.md` step 3/optional and `decisions/09-triage-delivery-decision.md` manual gate.
- **Skill-edit audit log** — ticker-agnostic. Any edit to a risk-rules
  skill section Thesis Intake reads gets logged as a visible event. `skills/thesis-intake/SKILL.md` placeholder now exists (`decisions/11-thesis-intake-decision.md`).
- **Freeze Manifest** (`vinu_infra/freeze.py` built `44e7e034`) — hashes `VINU_*` env + file hashes under `*_DATA_ROOT` for lineage + `contamination_check` drift between research and live.
- **Message Throttle** (`vinu_agent/broker/order_guard.py` deque `10/sec` built `8325e893`) — blocks runaway loop, the #1 live blow-up per `quantmemo`.

## What's still not built

Kept separate from the "as built" sections above so it's not mistaken for
done (now much shorter after A1-B):

1. **Significance Triage live delivery** — code path is real, needs
   operator-supplied Telegram/Discord credentials to actually fire (manual gate, `decisions/09`).
2. **Task 01's capital-allocator-worker test gap** — the worker itself
   runs correctly in practice, but its test only exercises the cycle
   function, not the actual scheduling loop (acknowledged `decisions/16`, 5 `test_capital_allocator_worker` pass).
3. **Tick-level wallet dry-run** — `ShadowEvaluator` is Sharpe-only `daily_returns`; wallet-level fill reconciliation still spiked (B24 `decisions/B-adoptable-decision.md`).
4. **Ticker paper wallet** — same tick-wallet spike.

## Open questions — now decided / pinned 2026-09-07

Former open questions from v1 are now pinned; see `pending-items-to-be-implemented.md` Status and `other-our-repo-full-research-features/decisions/`:

- Single-voice self-verdict — **accepted** single voice with rehearsal+PBO mitigation (`decisions/06`).
- `capital_allocator` allocation math — **decided** `fractional_kelly 0.25` + risk-parity+tilts+vol-target (`decisions/05`).
- `risk_gatekeeper` / rebalancer interactive vs non-interactive — needs both, still open as before (no change).
- N/K/completeness/interval — **decided provisional** `N=5 K=3 completeness 0.7 allocator 900s` etc. (`decisions/07`).
- Allocation cadence — **900s** decided (`decisions/07`).
- `TickerLedger` retention/taxonomy — **pinned** `stage/event_type/source` + 90d/1M (`decisions/10`).
- Thesis Intake reference sections — **placeholder** `skills/thesis-intake/SKILL.md` (`decisions/11`).
- Kill Switch risk-reducing rebalance — **decided block-all** (`decisions/12`).
- Jarvis-like watcher-agent — still explicitly deferred, not scoped.

Tuning against real cost/latency/data-reliability numbers (the caps, Monitor thresholds, completeness tolerance, `VINU_STAGE1_START_DATE 2022-01-01` determinism) remains continuous — all are env knobs, not code changes.
