# Full critique trail: the 6-analyst plan, and how the Hindsight memory problem got resolved

## Context

This doc is the record of the critical pass that followed
`agents-implementation-plan.md` (same folder) — every real problem found
in that plan, in the order they were found, what each one implied, and
exactly how the final Hindsight memory design in that plan's revision
was arrived at. It exists so the reasoning isn't lost — the *why*
behind the final design, not just the final design itself.

Four source docs feed this one: `data-driven-analysis-opportunities.md`
(the 21 analyses), `agents-implementation-plan.md` (the 6-analyst + 1-brain
org chart), `../maturity-agentic-system-explanation.md` (the original
`MaturityAssessor` design), and `../hindsight-memory-harness-explanation.md`
(Hindsight's real API, verified against its client source in an earlier
session). This doc adds one more layer of verification on top: a live
web search against Hindsight's current docs and open GitHub issues,
done specifically to resolve the memory-growth problem below rather than
guess at it.

---

## Critique 1 — the original schema had no ticker dimension

The first version of `agents-implementation-plan.md`'s `reflection_findings`
table was: `finding_id, analyst_name, cluster, computed_at, signal_json,
evidence_count, severity, narrative`. No `scope_key`.

That's a real defect, not a stylistic gap: of the 21 analyses in
`data-driven-analysis-opportunities.md`, most are genuinely per-ticker
(A, B, C, G, P, Q, R, S — angle trust, regime fit, loss-cause,
provenance, ingest health, weight staleness, freshness, fact-sheet
divergence), a few are genuinely system-wide (D, K, M, N, F — LLM
call-quality, memory-retrieval effectiveness, debate value, kill-switch
retrospective, human-override effectiveness), and a couple are
pair/cluster-scoped rather than single-ticker (E — correlation risk
between two symbols; J — churn as a market-wide regime signal). A flat
schema with no scope dimension would have forced every finding into one
undifferentiated bucket, throwing away exactly the "which ticker,
specifically" precision that was the whole point of moving past a
single global maturity scalar in the first place.

**Resolution**: add `scope_type ENUM(system, ticker, ticker_pair,
regime, strategy_family, angle)` + `scope_key` to the schema. Each
analyst emits however many rows its own join naturally supports that
day — not a fixed one-row-per-analyst-per-day shape.

## Critique 2 — the storage design had no growth/retention plan

The original schema was pure append-only, no retention policy. Real
arithmetic: even three per-ticker analysts on a ~50–200-symbol watchlist,
daily cadence, is hundreds of new rows a day and tens of thousands a
year — not a disk-space problem for SQLite, but a *signal quality*
problem: a brain reading "latest N raw rows" a year in is reading noise
mixed with durable signal, exactly the failure mode
`hindsight-memory-harness-explanation.md` already named as the reason
Hindsight was chosen over a flatter store like mem0 in the first place
— and the new design was about to recreate that same flaw by hand in
plain SQLite.

**Resolution**: split into two tables — `reflection_findings_history`
(raw, append-only, pruned the same way `vinu-initial-analysis`'s
`tier3` angle results already are — `cleanup_max_runs`-style, keep last
N per `scope_key`) and `reflection_beliefs` (current consolidated state
per `(analyst, scope_type, scope_key)`, overwritten not appended — the
same dual-table pattern already proven in this codebase by
`ticker_summaries` (current) + `ticker_daily_snapshots` (history)).

## Critique 3 — "six analysts" was about to mean six separate builds

The original framing treated each analyst as its own subsystem: its own
scheduler entry, its own storage, its own prompt logic. Verified against
the real code this session (`vinu-infra/sqlite.py`'s `SQLiteBackend`,
`vinu-agent/vinu_agent/cli.py`'s worker loops — every existing worker
is the identical `resolve_worker_interval(...)` →
`while True: cycle(); time.sleep(interval)` shape — and
`vinu-research/vinu_research/forecast_skill.py`'s `_build_forecast_prompt`),
six of anything sharing that much identical plumbing should not be six
separate things.

**Resolution**: one shared framework — one `reflection_worker_main`
following the exact real worker shape, one registry of analyst plug-in
functions (`(data_root_paths) -> list[Finding]`, nothing more — the
interface stays deliberately thin so it doesn't try to unify the actual
query logic, which genuinely differs per cluster), one shared
`upsert_many`-based write path, one shared brain-prompt template modeled
directly on `_build_forecast_prompt`'s real `=== Section ===` /
flattened-dict shape. Explicit requirement carried forward: each
registry entry needs its own try/except inside the shared cycle loop
(fail-open, logged, skipped) — same discipline `AuditLogger.log()`
already uses — so one analyst's bug can't silently take down the
others' cycle.

## Critique 4 — "one mixed bank" for everything non-ticker was too coarse

Once Hindsight banks entered the design (per-ticker banks, proposed by
the user, plus a catch-all "mixed" bank for cross-cutting findings), a
real problem surfaced: correlation/portfolio facts (E) and
process/governance facts (D, M, N) are not the same narrative. Hindsight's
whole value is that a bank's content is thematically coherent enough for
`retain → consolidate` to produce meaningful Observations — dumping both
kinds of fact into one undifferentiated bank would muddy the
consolidation of both.

**Resolution**: split "mixed" into two — a **portfolio/correlation
bank** (E, J, and portfolio-level parts of U) and a **system-process
bank** (D, K, L, M, N, F, O) — three bank *types* total (N per-ticker
banks + 1 portfolio bank + 1 system-process bank), with routing driven
mechanically by each finding's `scope_type`, not by which analyst wrote
it. Concretely: a single Regime & Risk Coverage cycle can write to a
ticker's own bank (its per-ticker regime fit), the portfolio bank (a
flagged correlation pair), and the system-process bank (a kill-switch
retrospective) in the same run — bank membership follows the fact, not
the analyst.

One hard rule fell out of this: a pair-level fact (e.g. AAPL↔MSFT
correlation) must be written to the portfolio bank **once**, referenced
by both tickers when queried — never duplicated into both tickers' own
banks. Two independent copies of the same fact, each subject to that
bank's own consolidation pass, risks the two banks drifting toward
different "beliefs" about the identical correlation over time — the
same two-copies-of-the-truth risk already flagged for the DB itself in
`maturity-agentic-system-explanation.md`, just recreated inside
Hindsight instead of avoided.

## Critique 5 — the real memory-growth problem, and what research actually resolved it

This is the critique that took the most work to close honestly, so it's
recorded in full.

**The worry, stated plainly**: a bank per ticker (potentially 50–200+ of
them on a real watchlist), each one accumulating raw retained facts
every day, forever — does this become unmanageable? The proposal on the
table was: create ephemeral per-ticker banks scoped to one day, extract
the useful pattern at end-of-day, discard the rest — store *experience*,
not *every experience*.

**What a live search against Hindsight's real docs and open GitHub
issues found** (done specifically to check this rather than assume an
answer — see Sources below):

- Hindsight **deliberately never prunes or evicts raw retained facts**.
  The docs state this outright: raw facts are "always preserved,"
  stored "permanently alongside observations." There is no
  delete-the-raw-layer-but-keep-the-distillate operation. A literal
  "ephemeral daily bank, discard after extraction" plan doesn't map to
  any real Hindsight capability — the closest real primitive is
  deleting an entire bank, which cascades and deletes its observations
  too, discarding the distillate along with the raw layer.
- What the ephemeral-bank idea was actually reaching for — a
  minimalistic, continuously-updated, evidence-backed belief, not a
  pile of raw events — **already exists in Hindsight**, as the
  Observation network, organized by **tags**, not by time-boxed banks.
  Each `retain()` call can carry tags (`date`, `regime`,
  `source_analyst`); `observation_scopes` controls whether observations
  form per-tag-combination or roll up into one shared, untagged belief
  (`observation_scopes: "shared"`); each observation carries a
  `proof_count` (how much evidence backs it) and freshness metadata,
  and is *refined, not overwritten*, as new evidence arrives.
- That `proof_count` + freshness pairing is, functionally, the same
  thing `reflection_beliefs`' `evidence_count` + trend was hand-designed
  to be in Critique 2's resolution — Hindsight already models it
  natively, for free, at the Observation layer.

**The actual fix, given raw facts can never be pruned**: control growth
at the *input* side, not the storage side. This system already has a
proven mechanism for exactly this kind of filtering — Significance
Triage, whose entire job is separating "routine" from "worth
recording." Reuse that discipline as the gate before anything reaches
Hindsight at all: **only `retain()` a finding when it crosses a real
threshold** — new, materially changed, or degraded — not the full daily
output of every analyst for every ticker. Most days, most tickers
produce nothing retain-worthy; that's the correct outcome, not a gap to
fill. This prevents the bloat from accumulating in the first place,
which is a strictly better position than accumulating it and trying to
extract the useful part afterward, given Hindsight offers no "afterward
cleanup" primitive to rely on.

**Revised design**: one *permanent* bank per ticker (not one per day),
retain() gated by significance, tagged by date/regime/source-analyst,
Observations providing the continuous distillation automatically — no
manual end-of-day extraction step required.

### Two reliability caveats surfaced by this same search, carried forward as open risks

1. `reflect()` — the operation the brain would use to synthesize across
   a ticker's bank, the portfolio bank, and the system-process bank in
   one query — has an open, reproducible GitHub issue reporting it
   returns a false "I don't have information" on roughly half of real
   calls (versions 0.9.2/0.10.0, already flagged once before in
   `hindsight-memory-harness-explanation.md`). With the brain now
   needing up to three bank queries per synthesis (ticker + portfolio +
   system-process), the compounded risk is real: roughly a one-in-two
   chance per query of silently losing a third of intended context.
2. **New this pass**: a separate open issue
   (`vectorize-io/hindsight#996`) reports the self-hosted `hindsight-api`
   process growing unbounded in memory — roughly 1GB within under an
   hour, in a container — a live operational risk for a deployment that
   would run 50–200+ banks continuously.

Both reinforce the same already-standing rule, now with concrete
evidence behind it rather than a general caution: **the SQLite
`reflection_beliefs` table stays the brain's hard, always-available
source of truth.** Hindsight is enrichment the brain reaches for when
available, never something its actual functioning structurally depends
on succeeding.

---

## Where this leaves the design, end to end

- **Schema**: `reflection_findings_history` (raw, pruned) +
  `reflection_beliefs` (current state, overwritten) — both
  `scope_type`/`scope_key` dimensioned.
- **Compute**: one shared worker/registry framework, six analyst
  plug-ins, thin interface, isolated failure per analyst.
- **Long-term memory**: one permanent Hindsight bank per ticker + one
  portfolio/correlation bank + one system-process bank, `retain()` gated
  by significance (not a full daily dump), tag-scoped Observations doing
  the distillation continuously.
- **Synthesis**: one brain, reading `reflection_beliefs` as hard truth
  and Hindsight banks as soft enrichment, prompt built the same
  structured-section way `forecast_skill._build_forecast_prompt` already
  proves out in production.
- **Two verified, open reliability risks to check against the current
  Hindsight release before committing further**: `reflect()`'s ~50%
  false-negative rate, and unbounded self-hosted memory growth
  (`#996`).

## Scope note

Like the docs it follows, this is a record of reasoning and a design,
not an implementation. Nothing here has been built. The next concrete
step, per `agents-implementation-plan.md`'s build order, is still Layer
0 + the Decision-Process analyst alone, proving the SQLite half of this
pipeline end to end before any Hindsight integration is attempted at
all — the Hindsight design above should be treated as validated-on-paper,
not validated-in-practice, until the two open reliability risks are
re-checked against whatever Hindsight release is current at build time.

## Sources

- [Observations: Knowledge Consolidation | Hindsight](https://hindsight.vectorize.io/developer/observations)
- [The Consolidation Problem in Agent Memory | Hindsight](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation)
- [Ingest Data | Hindsight - Vectorize](https://hindsight.vectorize.io/developer/api/retain)
- [hindsight-api Python process memory grows unbounded in container (~1GB in <1 hour) · Issue #996](https://github.com/vectorize-io/hindsight/issues/996)
- [Issue #4378 — reflect()/knowledge-page refresh false negatives](https://github.com/vectorize-io/hindsight/issues/4378) (carried over from `../hindsight-memory-harness-explanation.md`)
