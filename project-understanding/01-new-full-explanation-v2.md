---
name: agentic-workflow-current-architecture
status: v3 — 2026-09-11 — full rewrite against current reality, not a patch of v2.2. v2.2 (2026-09-09) described an earlier "21-gap build" (questions-answers/gaps-implementation, now removed from the repo) with its own cadences and decisions/05-12 references that no longer match the shipped code or the current tracking docs. This version replaces those with the real code (worker cadences, OrderGuard order, kill-switch mechanics — all re-verified this session, several directly via the `the-resaoning-ineffciency/scenarios-test/` scenarios) and the current tracking system (`complete-plan/00-index.md`, 81-item Stage 0-C tracker). Per-service internal step detail lives in `granularity-understanding/` — this file stays the cross-service pipeline/agent-role view, that folder is the "what actually happens inside each service" view.
purpose: how the agentic pipeline actually runs today — the roles, the loop-backs, the cross-cutting safety mechanisms, and an honest statement of what's proven vs. still unverified. Supersedes v2.2 as the current source of truth for this diagram; v1/v2.2 stay in git history as snapshots of earlier phases.
---

# Agentic workflow — current architecture (v3, 2026-09-11)

## The diagram

Structure is largely unchanged from v2.2 — the same stages, same
loop-backs — because that shape is still real, confirmed by reading the
current code (`vinu-agent/agent/scheduler_workers.py`,
`vinu-research/trade_plan_authoring.py`,
`vinu-live/trade_plan/orchestrator.py`), not assumed. What changed:
real cadences (not the 2026-09-09 fast-testing overrides), the real
Kill Switch mechanics (verified directly against the filesystem switch
in scenario 07), and one real disconnect found while writing this pass
— see the callout right after the diagram.

```mermaid
flowchart TB
    RL[("vinu-initial-analysis<br/>RunLog — new run_id<br/>for this symbol?")] -.-> GATE
    WL(["Watchlist entry point<br/>(TickerSummaryStore.list_summaries —<br/>a ticker with a Summary Agent<br/>read already on file)"]) --> GATE

    GATE{"Changed since last Planner<br/>pass on this ticker?<br/>(cheap deterministic check,<br/>ChangeGate, no LLM call)"}
    GATE -->|"no — advance to the<br/>NEXT ticker in the watchlist"| WL
    GATE -->|"yes"| SA

    subgraph ENTRY2 ["Second entry point — parallel to the watchlist path, not chained off it"]
        direction TB
        HTHEORY(["Human's own theory<br/>(idea/analogy, not code)"]) --> THGATE
        THGATE{"Near-duplicate theory,<br/>OR ticker at K-cap this cycle?"}
        THGATE -->|"yes — discard, wait<br/>for the next one"| HTHEORY
        THGATE -->|"no"| TI
        TI["<b>Thesis Intake</b><br/>(matches a theory against real<br/>evidence; writes no code)"]
    end
    TI -->|"worth checking"| P
    TI -.->|"reads + writes,<br/>source=human"| HR

    SA["<b>1. Summary Agent</b><br/>(vinu-agent: screener /<br/>angle_synthesizer team)<br/><i>GetAllAnglesTool — surveys ALL<br/>28 vinu-initial-analysis angles,<br/>only treats row_count&gt;0 as real</i>"]
    SA --> P

    P["<b>2. Planner</b><br/>(vinu-agent: PlannerTriage +<br/>idea_generator)<br/><i>reads the Summary Agent's stored<br/>TickerSummaryStore read + what's<br/>already running, checks ALL<br/>non-terminal statuses</i>"]
    P --> RE

    RE["<b>3. Researcher / Executor</b><br/>(vinu-agent LLM team, tool-driven)<br/><i>calls vinu-research's sweep/backtest<br/>tools to gather evidence, reasons over<br/>the result, then calls trade_plan_tool<br/>-&gt; author_trade_plan -&gt; ONE LLM<br/>forecast call per plan</i>"]
    RE -->|"self-verdict: FAIL"| P
    RE -->|"self-verdict: PASS,<br/>plan frozen (CREATED)"| RG

    RG["<b>4. risk_gatekeeper</b><br/>(vinu-agent LLM team,<br/>run_risk_gatekeeper_cycle,<br/>every 15 min)<br/><i>portfolio-fit only — never<br/>re-litigates the strategy</i>"]
    RG -->|"REJECTED"| P
    RG -.-> SIG
    RG -->|"APPROVED — hook moves<br/>BENCHING/MONITORING -&gt; PEND"| PEND

    PEND[("PEND — approved,<br/>awaiting funding")]
    PEND --> CA

    CA["<b>5. capital_allocator</b><br/>(vinu-agent LLM team,<br/>run_capital_allocator_cycle,<br/>every 15 min)<br/><i>whole PEND batch in one call,<br/>consults vinu-portfolio's<br/>correlation-aware allocation</i>"]
    CA -->|"funded — PEND -&gt; ACTIVE<br/>(only if Kill Switch clear)"| LS
    CA -->|"Kill Switch engaged<br/>at fund time — held"| PENDBLOCK
    CA -->|"rebalance REQUEST<br/>(advisory only)"| MON

    PENDBLOCK[("Funded but blocked by<br/>Kill Switch — never<br/>marked ACTIVE while halted")]

    LS["<b>6. Live + Shadow</b><br/>(vinu-live: trade-plan-worker<br/>every 5 min + shadow-worker<br/>every 1h)<br/><i>real orders through OrderGuard;<br/>a paper twin runs continuously<br/>off the same feed</i>"]
    LS --> MON

    MON["<b>7. Monitor</b><br/>(vinu-live's TradePlanOrchestrator<br/>— sole authority on a live<br/>position's close/hold)<br/><i>invalidation exit, contingency<br/>rules, bracket-partial at 1R+,<br/>correlation trim — verified<br/>scenario-by-scenario, see below</i>"]
    MON -->|"decay / drop — outcome<br/>+ reason written back"| P
    MON -->|"hold"| LS

    HR[("HypothesisRegistry")]
    HR -.->|"must consult before<br/>proposing again"| P
    MON -.->|"writes closed-loop outcome<br/>(vinu-live's FeedbackLoopWorker,<br/>every 5 min)"| HR

    CAL[("Calibration Tracker<br/>(vinu-research/calibration.py)<br/>angle trust, low_trust&lt;0.45,<br/>de-prioritize never gate")]
    CAL -.->|"which angles to trust"| SA

    SHOCK(["shock_clustering /<br/>shock_personality angles"])
    SHOCK -.->|"prioritizes cycle() order;<br/>ALSO the only 2 of 28 angles<br/>author_trade_plan's own LLM<br/>forecast call actually reads —<br/>see callout below"| MON
    SHOCK -.-> RE

    KS{{"Kill Switch<br/>(real filesystem file,<br/>/tmp/vinu-trading-halt —<br/>verified directly, not mocked,<br/>scenarios-test/07)"}}
    KS -.->|"OrderGuard.check() —<br/>reduce_only exempted ONLY<br/>when VINU_LIVE_HALT_POLICY<br/>=entries_only (the default)"| LS
    KS -.->|"blocks mark_active"| CA
    KS -.->|"blocks the rebalance<br/>REQUEST path too, by default"| CA

    SIG["Significance Triage<br/>(vinu-agent/significance_triage.py,<br/>worker every 15 min)"]
    CA -.-> SIG
    MON -.-> SIG
    SIG -.->|"flags only what's<br/>unusual"| HUMAN(["Human"])
    HUMAN -.->|"override recorded<br/>as evidence"| HR

    TL[("Ticker Ledger — plain<br/>SQLite, append-only")]
    TI -.-> TL
    SA -.-> TL
    P -.-> TL
    RE -.-> TL
    RG -.-> TL
    CA -.-> TL
    MON -.-> TL
    HUMAN -.-> TL
```

## The real gap this rewrite found: two separate 28-angle stories

**Confirmed by reading both code paths directly, not assumed** (also
recorded in `granularity-understanding/vinu-research.md`): the **Summary
Agent** (step 1, `vinu-agent`) genuinely does survey all 28
`vinu-initial-analysis` angles via `GetAllAnglesTool` — that part of the
old v2.2 description is accurate. But when **Researcher/Executor** (step
3) actually calls `author_trade_plan` to freeze the real trade plan, that
function's own LLM forecast call
(`forecast_skill.py::generate_forecast`) builds its prompt from
`fetch_risk_state` (vol/VaR/CVaR/Kelly, computed fresh from raw prices —
not read from any angle) plus `fetch_personality_features`, which reads
**only 2 of the 28 angles**: `shock_personality` and `shock_clustering`.
The Summary Agent's rich, all-28-angle narrative — already computed,
already stored in `TickerSummaryStore` — is **not passed into the
trade-plan forecast prompt at all**. Two separate LLM calls, two
separate contexts; the one that actually becomes the numeric trade plan
sees a small fraction of what the pipeline already knows. Not a bug per
se — nothing crashes, nothing lies — but a real, previously-undocumented
disconnect between "what the pipeline analyzed" and "what the decision
that moves money actually looked at."

## Real worker cadences (verified against `config.py` defaults in both services, not a temporary override)

| Worker | Service | Interval |
|---|---|---|
| planner-worker | vinu-agent | 1800s (30 min) |
| risk-gatekeeper-worker | vinu-agent | 900s (15 min) |
| capital-allocator-worker | vinu-agent | 900s (15 min) |
| significance-worker | vinu-agent | 900s (15 min) |
| skill-audit-worker | vinu-agent | 3600s (1h) |
| trade-plan-worker (Live) | vinu-live | 300s (5 min) |
| feedback-worker | vinu-live | 300s (5 min) |
| trade-plan-approval-worker | vinu-live | 300s (5 min) |
| shadow-worker | vinu-live | 3600s (1h) |
| drawdown-monitor | vinu-portfolio | 300s (5 min) |

v2.2's "planner 60s, risk 60s, allocator 90s" were a temporary fast
override for one operator's test session, not the shipped defaults —
worth knowing the difference between "what an operator dialed in for a
quick test" and "what actually ships."

## Per-agent detail

### 1. Summary Agent (`screener` / `angle_synthesizer`)

Calls `GetAllAnglesTool` (`get_all_angles(ticker)`), reports how many of
the 28 angles have real row-backed data, cites specific numbers from the
ones that do. Grounding discipline unchanged from v2.2 and still real:
only treats an angle as informative when `row_count > 0` — never invents
a number.

**Trigger**: `planner-worker` (every 30 min) → `RunLogTrigger.refresh_if_stale`
checks whether `vinu-initial-analysis` has a new `run_id` for this
ticker since the last Summary Agent pass; only refreshes if so.
`ChangeGate` then decides whether anything changed enough to bother the
Planner with. See `granularity-understanding/vinu-agent.md` for the full
step sequence.

### 2. Planner (triage + `idea_generator`)

Reads the Summary Agent's stored `TickerSummaryStore` read and every
non-terminal artifact status (CREATED/BENCHING/ACTIVE/MONITORING) for
that ticker, produces a fit tier + priority. Consults
`HypothesisRegistry` before proposing — what's been tried, what failed
and why.

### 2b. Thesis Intake (second entry point)

Unchanged in shape from v2.2: a human's raw theory checked against real
evidence, no code written, verdict feeds the same downstream loop as a
system-generated idea.

### 3. Researcher / Executor

**This is where v2.2's description and the direct code I read this
session diverge most, and where I'm being explicit about what's
re-verified vs. carried over**: `vinu-agent`'s research team has real
sweep/backtest tools available (`run_parameter_sweep_tool.py`,
`run_sweep_candidate_tool.py`, confirmed to exist) alongside
`trade_plan_tool.py` (which calls `author_trade_plan`). The team
presumably uses the sweep tools to gather backtest evidence before
authoring the actual plan — this matches v2.2's "sweep, self-verdict,
then author" shape. What's freshly, directly verified this session is
only the **final step** — `author_trade_plan`'s own forecast call and
what it reads (see the callout above) — not the full internal
tool-orchestration sequence the LLM team follows to get there. Treat the
sweep/PBO/triple-barrier specifics from v2.2 (vectorbt batch, hyperopt-8,
embargo periods, N=5/K=3/completeness 0.7) as **carried over from the
prior version, not re-checked in this pass** — real files
(`sweep.py`, `sweep_grid.py`, `pbo.py`, `labels.py`) do exist for all of
it, just not re-read line-by-line this time.

### 4. `risk_gatekeeper`

Every 15 min, `run_risk_gatekeeper_cycle` polls every BENCHING/MONITORING
artifact, hands each to the real LLM team
(`GetPortfolioTool` → `ComputePositionSizeTool` → verdict), the team's
own hook applies the state transition — the scheduler never mutates
state directly. See `granularity-understanding/vinu-agent.md`.

### 5. `capital_allocator`

Every 15 min, one call over the **whole PEND batch** (not per-candidate),
funds against the configured risk budget, consults `vinu-portfolio`'s
correlation-aware allocation (`build_portfolio()` — real HRP allocation,
`granularity-understanding/vinu-portfolio.md`). Checks the real Kill
Switch before `mark_active` — held in a "funded but blocked" state, never
silently marked ACTIVE while halted.

### 6. Live + Shadow

`vinu-live`'s trade-plan-worker (5 min) places real orders through
`OrderGuard`; `shadow-worker` (1h) runs `ShadowEvaluator.evaluate_all()` —
BENCHING → ACTIVE promotion against the real paper-trading track record
(`meets_promotion_bar`, `granularity-understanding/vinu-research.md`).

### 7. Monitor

`vinu-live`'s `TradePlanOrchestrator` — sole authority on a live
position's lifecycle. **This is the one stage with the deepest, most
recent direct verification in the whole pipeline** — every mechanism
below was driven through real engineered adverse scenarios, not just
read (`the-resaoning-ineffciency/scenarios-test/01-07`, all 7 closed):

- Invalidation exit reacts correctly to any size move, gradual or a
  single-bar -25% crash (scenario 01).
- A kill-switch halt blocks entries but never blocks a reduce-only exit
  in the same cycle (scenario 02) — and the actual authoritative
  enforcement (`OrderGuard.check()` against the real filesystem switch)
  makes the identical decision, independently confirmed (scenario 07).
- Tight noise never produces a spurious full exit (scenario 03).
- A real broker outage: the exit is still attempted, fails truthfully
  (never a false success), retries until the broker recovers (scenario 04).
- The correlation/concentration trim runs off real DCC/shrinkage math
  from actual price history, not a mocked number (scenario 05).
- A position closed overnight by its own resting stop is now correctly
  auto-reconciled — this was a **real, previously-live bug** (a
  confirmed-flat broker account was indistinguishable from a broker
  outage, meaning a stale position could sit forever and a later exit
  attempt could send a real sell order into an already-flat account),
  found and fixed this session (scenario 06).

Trailing-stop ratchet is bookkeeping only (never itself triggers an
exit — the actual dynamic exit logic is invalidation_conditions/
contingency_rules, evaluated fresh every cycle); bracket-partial at 1R+
scales with the R-multiple actually achieved (25% at 1R, 50% at 2R,
capped 75% — fixed this session from a flat 50%, `the-resaoning-ineffciency/00-audit.md`).

## Cross-cutting mechanisms

- **Calibration Tracker** (`vinu-research/calibration.py`) — feeds the
  Summary Agent which angles to de-prioritize (`low_trust < 0.45`, never
  a hard gate).
- **HypothesisRegistry** — the Planner's pre-proposal check, where
  Monitor's closed-loop outcomes (via `vinu-live`'s `FeedbackLoopWorker`,
  every 5 min) get written.
- **Kill Switch — real, filesystem-backed, verified directly this
  session.** `/tmp/vinu-trading-halt`, checked in `OrderGuard.check()`
  before every real order. A `reduce_only=True` order is exempted only
  when `VINU_LIVE_HALT_POLICY=entries_only` (the default) — confirmed
  against the real switch, not mocked, including that the exemption is
  genuinely policy-gated and not an unconditional bypass
  (`scenarios-test/07`). Also checked before `capital_allocator`'s
  `mark_active` and the rebalancer's request path.
- **Significance Triage** — worker every 15 min, judges routine vs.
  unusual, fed by `capital_allocator`/Monitor/`risk_gatekeeper`
  rejections.
- **Calibration log** (`vinu-infra/calibration_log.py`, new this
  session) — a plain append-only JSONL observation log for genuinely
  arbitrary threshold decisions (`bracket_partial`, `rebalance_protect`),
  gated to a confirmed real broker connection so test runs never pollute
  it. Not a decision store — nothing reads it back at runtime; it exists
  purely so these numbers leave a record checkable against what actually
  happened later.

## Where things honestly stand — 2026-09-11

Replaces v2.2's "What's still not built" with the current, directly
answerable state (see `complete-plan/00-index.md` for the full 81-item
tracker and `the-resaoning-ineffciency/` for the reasoning-audit and
scenario-test work — those are the current source of truth, not the
`questions-answers/gaps-implementation` decisions this file used to
cite):

**Proven, not just built** — the mechanical order-management pipeline
(entry, exit, risk-trim, broker-outage recovery, kill-switch enforcement)
has been driven through engineered adverse scenarios with known-correct
answers and confirmed to behave correctly, catching one real bug along
the way (`scenarios-test/01-07`, all 7 closed).

**Still genuinely untested**:
1. **The LLM decision layer itself** — everything above (Summary Agent,
   Planner, Researcher/Executor, risk_gatekeeper, capital_allocator) has
   never been run through a scenario with a known-correct answer. The
   mechanical scenarios deliberately bypass the LLM entirely.
   `llm-scenarios-test/` exists as a folder with a README stub — not
   started.
2. **`vinu-screener`** — fully decoupled from this whole pipeline
   (confirmed zero imports into `vinu-agent`/`vinu-research`/`vinu-live`),
   currently only consumed manually via Telegram `/rank`. Zero scenario
   coverage.
3. **No live track record.** Every scenario so far is synthetic,
   deterministic, offline. Nothing here has survived a real incident.
4. **The 28-vs-2-angle disconnect** documented above — not fixed, just
   now accurately described.

Two of the genuinely-arbitrary Category C thresholds from the reasoning
audit have been fixed with real reasoning (scaled by a measured
quantity instead of a flat constant, matching the pattern other
audited repos — `abu.py`, Hummingbot — already use); the remaining seven
are being observed via the new calibration log rather than re-guessed.
