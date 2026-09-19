# The maturity-agentic system: how it sits on the DB, and how many agents it actually needs

## Context

This came out of a conversation about a recurring gap noticed while
auditing what the system does and doesn't record (see
`project-understanding/05-full-recorded-information/`): almost every
calibration mechanism in this codebase (TradeScore calibration, forecast
calibration, decay health checks, the Shadow paper-trading gate) already
refuses to trust a number until real evidence backs it — but each one
computes its own private, local notion of "do I have enough evidence,"
with no shared, system-wide answer to "how mature is this system, right
now, overall." The vision for why this matters is in
`project-understanding/06-The-project-visison/project-vision.md`; this
doc is the *how*.

Three questions this doc answers, in the order they came up:

1. Where does the thing that computes "system maturity" sit, architecturally?
2. What's its relationship to the database and to Hindsight (the memory/retrieval harness planned for the narrating agent)?
3. How many agents does this actually need — is it "one maturity agent commanding analysis agents underneath it," or something else?

## 1. Where it sits: on top of the DB, not inside any existing agent

The database stores cataloged in `05-full-recorded-information/` are the
system's source of truth for everything a maturity judgment needs:

- `vinu-research/vinu_research/trade_score_calibration.py`'s history
  (`trade_score_calibration_history.jsonl`) — real per-trade outcomes
  joined to the TradeScore sub-scores that predicted them.
- `vinu-research/vinu_research/storage/strategy_store.py`'s
  `calibration_entries` / `angle_calibration_entries` tables — forecast
  accuracy (Brier score, directional correctness) per artifact and per
  angle.
- `vinu-agent/vinu_agent/broker/performance_store.py`'s
  `paper_performance` table — how many days of paper-trading returns
  exist per artifact, and how they've actually performed.
- `vinu-live`'s position book (`open_positions`/`closed_positions`/`fills`)
  — real fills, real realized P&L, the least theoretical data the system
  has.
- `vinu-infra/trade_audit_log.py`'s `trade_audit_log.jsonl` — the
  per-trade join-key log, including `slippage_stats()`'s real
  execution-quality numbers.

A new module — call it `MaturityAssessor` — reads across these
(in-process where colocated, over HTTP where cross-service, the same
pattern `vinu-portfolio/research_link.py` already uses to read
vinu-research's strategy store) and produces one thing: **a maturity tier
and the evidence behind it.** It does not own any of this data, does not
duplicate it into a new store, and does not write anything back to these
tables — it's a read-model, the same relationship `vinu-portfolio`'s
correlation/allocation logic already has to raw price data.

**Why not build this as a new SQLite store of its own?** Because the
underlying facts (trade counts, calibration accuracy, live-vs-paper
split) are already durably recorded in the tables above. A maturity tier
computed from them is a *derived value*, recomputable at any time from
the source data — persisting it separately would create exactly the kind
of two-copies-of-the-truth risk the whole DB-as-source-of-truth
architecture (see below) exists to avoid. If querying live turns out to
be too slow in practice, the fix is a cache with a short TTL, not a new
authoritative store.

## 2. Relationship to the DB and to Hindsight

This was worked out directly in conversation and is worth stating
precisely, since it's easy to get backwards:

```
        ┌─────────────────────────────────────────┐
        │   Real DB stores (source of truth)       │
        │   trade_score_calibration_history.jsonl, │
        │   calibration_entries, paper_performance, │
        │   position book, trade_audit_log.jsonl…   │
        └───────────────┬───────────────┬──────────┘
                         │               │
              reads      │               │  retain() copies
                         ▼               ▼
        ┌────────────────────┐   ┌──────────────────────┐
        │  MaturityAssessor   │   │  Hindsight-ai        │
        │  (deterministic,    │   │  (retrieval tool —    │
        │   no LLM, computes  │   │   retain/recall/      │
        │   the tier + why)   │   │   reflect over a      │
        └─────────┬───────────┘   │   copy of DB facts)   │
                   │              └──────────┬────────────┘
                   │   tier is itself         │
                   │   one more fact an       │
                   │   agent can retain()     │
                   │   into Hindsight ────────┘
                   ▼
        ┌─────────────────────────────────────────┐
        │  Existing agents consult the tier as one  │
        │  more input: Planner, risk_gatekeeper,    │
        │  capital_allocator, trade-plan authoring, │
        │  the future narrating agent.              │
        └─────────────────────────────────────────┘
```

Two things this fixes, both confirmed explicitly earlier in the
conversation:

- **The DB stays the one source of truth.** `MaturityAssessor` reads it
  directly; it does not go through Hindsight to get there, and nothing
  is ever written to Hindsight-only storage that isn't also in a DB
  table. This keeps the memory harness swappable — Hindsight could be
  replaced later without losing anything, because it never held anything
  exclusively.
- **Hindsight's job stays retrieval, not computation.** It is the tool an
  agent calls to pull back *relevant chunks* (semantically/temporally
  ranked) when reasoning — including, once retained, the maturity tier
  itself as one more fact. It does not compute the tier; it only ever
  serves it back alongside other retained context.

## 3. How many agents: one deterministic module, zero-to-one LLM calls, no hierarchy

This is the part worth being direct about, because the natural instinct
("a maturity agent, with different analysis agents underneath it doing
different kinds of assessment") is over-engineering for what this job
actually is.

**What maturity assessment actually requires is arithmetic on real
tables** — how many real trades exist, what fraction of predictions were
directionally correct, how many paper-trading days have accumulated, what
fraction of the sample is live vs. paper, which market regimes are
actually represented in the sample. None of that needs an LLM to decide;
it needs the exact same "count real rows, check against a minimum sample
size, compute a ratio" logic `trade_score_calibration.py` and
`calibration.py` already implement. Building "sub-agents" to each analyze
one of these signals would mean paying LLM latency/cost to do something a
plain function does more reliably and instantly.

So the actual shape is:

### Layer 1 — `MaturityAssessor` (no LLM, does the real work)

A single deterministic module, same category as `CalibrationGate` and
`trade_score_calibration.py`'s calibration functions — not an "agent" in
the LLM-team sense at all. It:

- Reads the DB stores listed in §1.
- Computes a small set of real signals: `n_real_trades`,
  `n_paper_trading_days`, `directional_accuracy`, `brier_score`,
  `live_trade_fraction`, `regime_coverage` (which regimes, per
  `vinu-research`'s regime tagging, are actually represented in the
  sample).
- Maps those signals to a **tier** via the same bounded, sample-gated
  logic every other calibration mechanism in this codebase already uses
  — e.g. (illustrative, not final):
  - `cold_start` — zero or near-zero real trades. Lean entirely on
    backtest/theoretical priors; position sizing capped hard; agents
    should explicitly hedge language ("based on backtest only, unproven
    live") rather than state confidence.
  - `paper_only` — real paper-trading history exists (`min_paper_days`
    territory, same bar Shadow's gate already uses) but no/minimal live
    capital risked yet.
  - `early_live` — some real live trades exist, but below the minimum
    sample size `trade_score_calibration.py` already requires before it
    lets calibration nudge thresholds. Calibration signal exists but is
    still narrow — regime coverage likely incomplete.
  - `mature` — enough real live samples, broad enough regime coverage,
    that the system's calibration mechanisms are actively adjusting
    thresholds based on live outcomes rather than sitting at defaults.
- Returns the tier **plus the evidence for it** (the raw numbers above,
  not just a label) — so any consumer, human or agent, can see *why* the
  system thinks it's at a given tier, not just the verdict.

This is a library function / service call, not a "reasoning agent." It
should be exposed the same way `vinu-portfolio`'s allocation logic is —
in-process where the caller is colocated, over a small HTTP endpoint
(e.g. `GET /maturity/status`) for cross-service callers like vinu-agent's
teams.

### Layer 2 — optional single LLM synthesis call (zero or one agent, not a team)

If a *qualitative* read is wanted on top of the raw tier — e.g. "we have
12 real trades, but 9 of them are from one low-volatility regime, so
confidence outside that regime is still effectively cold_start-level even
though the raw count looks like early_live" — that's **one** lightweight
LLM call, the same shape as `forecast_skill.generate_forecast`: one
prompt, the `MaturityAssessor` numbers as structured input, one
synthesized judgment out. Not a team, not sub-agents per signal type —
one agent reading numbers a deterministic layer already computed, adding
narrative nuance, nothing more. This mirrors the "single agent, not
multi-agent" decision already made for the narrating agent in
`missing-pieces-of-system/narating-agents/narrating-agent-explanation.md`
— the same reasoning applies here: this is one coherent judgment over one
input set, not an adversarial or decomposable task that would benefit
from a debate pattern like `investment_committee`.

### Layer 3 — existing agents consult it, unchanged in count or structure

No new agent *team* is needed, and no existing team gets restructured
"underneath" a maturity agent. Each of the following reads the current
tier (Layer 1's output, or Layer 2's narrative if built) as **one more
input**, the same way they already read `GetPortfolioTool` or a
calibration threshold today:

- **Planner / trade-plan authoring** — at `cold_start`/`paper_only`,
  weight backtest/theoretical evidence more heavily in the forecast
  prompt; at `mature`, weight live calibration more heavily. This is a
  prompt-context change, not a structural one — the same slot
  `angle_digest` already fills in `forecast_skill`'s prompt.
- **risk_gatekeeper** — at lower tiers, apply a stricter portfolio-fit
  bar (smaller max position size, lower concentration cap) than at
  `mature`, where the existing `max_per_strategy_weight`/
  `max_correlated_cluster_weight` caps can be trusted closer to their
  configured limits.
- **capital_allocator** — the reserve-fraction concept from the
  narrating-agent vision (hold back capital) is naturally tier-scaled:
  hold back *more* at `cold_start`, less as the system earns `mature`
  status. `vinu-portfolio/vinu_portfolio/config.py`'s `reserve_fraction`
  (already built this session) is the exact mechanical lever this would
  drive.
- **The future narrating agent** — as stated in the vision doc, this is
  the clearest consumer: an agent reasoning about "how aggressively
  should I trade this ticker today" needs to know not just what it knows
  about the ticker, but how much the *system itself* currently knows in
  general.

None of these agents change in number or get restructured into a
hierarchy. They each gain one new input.

## Summary answer to "how many agents"

- **Zero to one LLM agents**, not a team, not a hierarchy.
- The actual computation is a deterministic module sitting on top of the
  DB — the same architectural role as every other calibration mechanism
  already in this codebase, just generalized across all of them instead
  of siloed per-mechanism.
- Every *existing* agent (Planner, risk_gatekeeper, capital_allocator,
  the future narrator) consults its output as one more input. None of
  them are subordinate to it, and it is not subordinate to any of them —
  it's a shared service, like `GetPortfolioTool`, not a manager.

## Scope note

This is a design doc; steps (1)–(3) below are now built (2026-09-20).
The concrete next steps, in order: (1) define
the exact tier thresholds and signal formulas (mirroring
`trade_score_calibration.py`'s existing sample-gating conventions), (2)
build `MaturityAssessor` as a plain module reading the DB stores in §1,
(3) wire its output into trade-plan authoring's prompt first (highest
leverage, lowest risk — it's the earliest decision point), then
`risk_gatekeeper`/`capital_allocator`, then finally into the narrating
agent once that's built. The optional Layer 2 LLM synthesis call is a
nice-to-have, not a prerequisite for the tier logic itself to be useful.

**Status update, 2026-09-20**: (1) and (2) built twice, deliberately not
shared — `vinu-reflection/vinu_reflection/reflection/_maturity_assessor.py`
(analysis T's consumer, reads vinu-agent's `PaperPerformanceStore` class
directly, since vinu-reflection already mount-and-imports vinu-agent as a
service) and `vinu-research/vinu_research/maturity_assessor.py` (this
step-3 consumer's own copy, reads vinu-agent's `paper_performance.db` via
a minimal raw `sqlite3` query instead, since vinu-research importing
vinu-agent's package would be a new, circular reverse dependency —
vinu-agent already depends on vinu-research, not the other way). Same
tier logic, same grounded thresholds, genuinely different data-access
constraints per caller — documented in each module's own docstring
rather than forced into one shared module across a dependency direction
that doesn't exist.

(3) wired into `vinu_research/trade_plan_authoring.py`'s `author_trade_plan()`,
opt-in via `maturity_tier_enabled` (off by default, same cautious-rollout
posture as `regime_analogue_enabled`/`options_iv_enabled` above it in
`config.py`) — a new "=== System Maturity ===" block in
`forecast_skill._build_forecast_prompt()`, alongside (not inside)
`summary_context`'s existing "=== Angle Digest ===" block, carrying the
tier + the real evidence behind it (`n_real_trades`,
`n_paper_trading_days`, `directional_accuracy`, `regime_coverage`) plus
one line telling the LLM how to weight it (backtest-heavy at
cold_start/paper_only, live-calibration-heavy at mature). Fails open on
any error, matching every other optional prompt-context addition in that
function (`fetch_options_context`, `fetch_debate_signal`).

**A real asymmetry, documented, not hidden**: `author_trade_plan()` runs
on two real paths — in-process on `agent-api` (the primary path,
`trade_plan_tool.py`'s `_author_and_freeze_trade_plan_in_process`) and
over HTTP fallback on `research-api` (only if the in-process call
raises). Only `agent-api` has `paper_performance.db` visible
(`VINU_RESEARCH_AGENT_DATA_ROOT=/data`, its own already-mounted vinu-agent
root — no new mount needed); `research-api` has no such mount, so on that
path only `cold_start`/`early_live`/`mature` are distinguishable, never
`paper_only` (paper history is invisible there). This mirrors the exact
tradeoff analysis J already accepted for `regime_analogue_enabled`
(sparser evidence on one path, real data on the other, rather than
blocking on making both paths perfectly symmetric on day one).

`risk_gatekeeper`/`capital_allocator` wiring and the narrating-agent
consumer are still not started — real, separate future steps, each its
own decision point per this doc's own step 3 phasing.
