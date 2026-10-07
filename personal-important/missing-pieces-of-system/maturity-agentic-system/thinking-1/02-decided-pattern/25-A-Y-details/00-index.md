# The 25 analyses (A–Y), in full detail — index

## Context

`../05-to-do.md` item #2 named this as the single largest remaining gap:
every analysis in `data-driven-analysis-opportunities.md` was still one
paragraph — "join X × Y × Z" — not a real, runnable spec. This folder
closes that gap for all 25, one file per analyst cluster (matching
`personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`'s grouping), each analysis broken into
four parts:

- **Source stores** — the real table/file names and real column names
  it reads, cited against `project-understanding/05-full-recorded-information/README.md`'s
  55-store catalog.
- **Fetch** — the actual join, in plain words, using only real columns.
- **Condition** — the significance rule that decides whether this
  analysis's finding gets written at all this cycle (see "On thresholds"
  below — this is a formula, not a hand-picked number).
- **Storage** — `scope_type` / `scope_key` / what `signal_json` holds /
  what counts as `evidence_count`, per the schema in
  `personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`'s Layer 0 section.
- **Manageability** — how this analysis's row count behaves as the
  watchlist grows (linear in ticker count, bounded/structural regardless
  of ticker count, or the one quadratic case).

## On thresholds — why there are no hard-coded numbers here

None of the 25 conditions below use a fixed, hand-picked constant (e.g.
"Brier score ≥ 0.05"). That would recreate exactly what analysis **W**
exists to audit — a reasoning-picked, never-measured number, the same
category of thing `calibration_log.jsonl` already exists to track down
elsewhere in this system. Instead, every condition is a **self-calibrating
relative rule**: does this cycle's raw value fall outside that same
metric's own trailing distribution for that `scope_key` (a percentile
band or a standard-deviation band), computed fresh from the real source
tables every time — never against this reflection layer's own
already-gated rows (the rule fixed in `../05-to-do.md` #3, to avoid
recreating analysis E's own "slow boil invisible to a single check"
problem one layer up). The only conditions with an absolute number are
ones with a real domain-defined bound (Brier score ∈ [0,1], correlation
∈ [-1,1]).

The specific band width (2 std devs? P10/P90? 3 consecutive checks?) is
still a provisional starting choice in each file below, same as any
other reasoning-picked number in this codebase — it should be logged
the same way `calibration_log.jsonl` logs everything else unmeasured,
so it's checkable against real outcomes later, not assumed correct
because it's written down here.

## The seven files

| File | Cluster | Owns |
|---|---|---|
| `01-forecast-intelligence.md` | Forecast Intelligence | A, Q, P, G, S |
| `02-regime-risk-coverage.md` | Regime & Risk Coverage | B, E, N, V |
| `03-execution-money-flow.md` | Execution & Money-Flow | C, U, Y |
| `04-decision-process-cognition.md` | Decision-Process / Cognition | D, L, K, M |
| `05-governance-freshness.md` | Governance & Freshness | O, R, F, W, H |
| `06-external-signal-cross-check.md` | External-Signal Cross-Check | I, J, T, X |
| `07-implementation-plan-status.md` | *(all clusters)* | Not a spec file — the implementation status/continuation doc. Read this one first if you're picking the build back up. |

## The manageability headline, restated here since it spans all six files

Only 8 of the 25 genuinely need a row per ticker (and all 8 are linear
in watchlist size, further cut by the significance gate). The other 17
are structural — scoped by angle, strategy family, regime, LLM role,
checkpoint, ranker/rule id, or system — and their row count stays flat
regardless of how many tickers are on the watchlist. The one real
scaling risk in the whole set is **E**'s pairwise-correlation piece,
mitigated by scoping pair-checks to co-held positions only, not the
full watchlist (see `02-regime-risk-coverage.md`).

## Scope note

Files `00`–`06` are a design and a specification, not an
implementation. **As of 2026-09-19, 9 of the 25 analyses described here
have actually been built and tested** (in the separate `vinu-reflection`
service) — see `07-implementation-plan-status.md` for exactly which
ones, what's still not built and why, and where to continue. The design
files themselves are kept current too: every built or investigated
analysis has a dated note in its own section recording what was found
and (where real data didn't support the original design) what changed.
