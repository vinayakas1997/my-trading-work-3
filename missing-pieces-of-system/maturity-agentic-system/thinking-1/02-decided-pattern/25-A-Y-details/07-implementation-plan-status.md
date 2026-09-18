# Implementation plan & status — single reference

## What this file is

`00-index.md` through `06-external-signal-cross-check.md` are the
**design spec** for all 25 analyses (A–Y). This file is the
**implementation status** — what's actually built, what's tested, what
isn't built and the real, verified reason why, and exactly where to
continue. Read this file first if you're picking this work up cold;
it's the map, the other files are the territory.

Named `07-` (not `06-`) because `06-external-signal-cross-check.md`
already owns that number — reading order in this folder is
`00` → `06` (the spec), then this file.

Status as of **2026-09-19** (update: W and H-consistency built).

---

## The plan, in one paragraph

`00-decided-pattern.md` (parent folder) lays out 9 steps: 55 existing
data points → 25 cross-package joins (A–Y, this folder) → grouped into 6
analysts (Forecast Intelligence, Regime & Risk Coverage, Execution &
Money-Flow, Decision-Process/Cognition, Governance & Freshness,
External-Signal Cross-Check) → each analyst writes `Finding`s through one
shared severity/trend pipeline (Layer 0/1) → into two tables
(`reflection_findings_history`, `reflection_beliefs`) → optionally into
Hindsight memory banks → synthesized by "the brain" (a 7th, not-yet-built
component) into one maturity narrative. `05-to-do.md` (parent folder)
originally scoped what had to be designed before any of this could be
coded; that's now fully closed. This file picks up from there — the
actual build.

## Where the code actually lives

- **Layer 0/1 (shared, cross-analyst)**: `vinu-infra/reflection.py` —
  `ReflectionStore` (3 tables), `Finding` dataclass, `classify_severity()`
  /`compute_trend()` (PSI-based), `write_finding()`/`write_findings()`.
  25 tests, `vinu-infra/tests/test_reflection.py`.
- **The worker + every analyst module**: its own service,
  `vinu-reflection/` — **not** inside vinu-agent. That was the original
  plan (`05-to-do.md` #5's first decision), reversed 2026-09-19 once
  explicitly asked for a cleaner separation; kept cheap to reverse again
  since every analyst only ever imports another service's storage
  classes in-process (mount-and-import), never vinu-agent-internal
  orchestration code — moving `vinu_reflection/reflection/` back into
  `vinu_agent/reflection/` later would be a folder move, not a rewrite.
  - `vinu_reflection/cli.py` — `ANALYSTS` registry, `run_cycle()`
    (per-analyst try/except isolation), `reflection_worker_main()` (the
    real `while True: cycle(); sleep()` loop `02-analyst-interface.md`
    only had as pseudocode before).
  - `vinu_reflection/reflection/*.py` — one module per built analysis
    (see table below).
  - `vinu_reflection/config.py` — env-resolved paths to every mounted
    service's data root.
  - Wired into `docker-compose.yml` as `reflection-worker`: no HTTP
    port, read-only mounts of vinu-agent/vinu-live/vinu-research/
    vinu-screener/vinu-portfolio's data roots, all five added as real
    Python dependencies (mount-and-import, same posture
    `vinu-agent/broker/research_link.py` already established for
    vinu-research).

## Status at a glance

**12 of 25 analyses implemented and tested. 13 not built**, each with a
real, checked reason (not "not gotten to yet") — see the table.

| Package | Tests | Status |
|---|---|---|
| `vinu-infra` | 248 | green |
| `vinu-reflection` | 57 | green |
| `vinu-agent` | 1171 | green |
| `vinu-live` | 436 | green |
| `vinu-screener` | 436 | green |
| `vinu-portfolio` | 209 | green |
| `vinu-research` | 889 | green |

Real infra bugs found and fixed along the way (both worth knowing about
regardless of this reflection work):
- `trade_audit_log.jsonl` had no `VINU_TRADE_AUDIT_LOG` set anywhere in
  `docker-compose.yml` for `live-api` — it was writing into the
  container's ephemeral `$HOME`, not its mounted `/data` volume, so the
  whole log was silently lost on every restart. Fixed.
- `reflection-worker` itself had no `VINU_RESEARCH_DATA_ROOT` set — the
  first 3 analysts built (A, plus the Decision-Process ones that read
  vinu-research) would have silently read/written nothing in a real
  deployment. Fixed.
- Same bug, third instance: `live-api` had no `VINU_CALIBRATION_LOG` set
  either — `calibration_log.jsonl` (needed for W) was also writing into
  the container's ephemeral `$HOME`, not `/data`. Fixed.
- `vinu_infra/freeze.py` (needed for H's consistency piece) turned out to
  be entirely unreachable as `vinu_infra.freeze` — it lived in an orphaned
  `vinu-infra/vinu_infra/` subdirectory never covered by the package's own
  flat `package-dir` mapping, so nothing anywhere could actually import
  it despite the module itself being real and correct. Moved to
  `vinu-infra/freeze.py` (the same flat layout every other vinu-infra
  module already uses) — fixed, not just worked around.

---

## Per-analysis status (all 25)

| # | Cluster | Analyst module | Status | File / reason |
|---|---|---|---|---|
| D | Decision-Process | `decision_process` | ✅ Built | `decision_process.py` |
| L | Decision-Process | `decision_process` | ✅ Built | `process_mining.py` |
| M | Decision-Process | `decision_process` | ✅ Built | `debate_value.py` |
| K | Decision-Process | `decision_process` | ❌ Blocked | no structured record of which memory/facts get injected into a prompt exists anywhere |
| A | Forecast Intelligence | `forecast_intelligence` | ✅ Built | `angle_trust.py` |
| Q | Forecast Intelligence | `forecast_intelligence` | ⏸ Deferred | source (`WeightsStore`) lives in the one dependency-heavy service (vinu-initial-analysis: torch/xgboost/chronos/timesfm) |
| P | Forecast Intelligence | `forecast_intelligence` | ❌ Blocked | `calibration_entries.timestamp` is never populated by any real writer |
| G | Forecast Intelligence | `forecast_intelligence` | ❌ Blocked | merges into P's row, same blocker |
| S | Forecast Intelligence | `forecast_intelligence` | 📋 Needs a spec | numeric-claim text extraction — no existing parser to build against |
| C | Execution & Money-Flow | `execution_money_flow` | ✅ Built | `loss_attribution.py` |
| U | Execution & Money-Flow | `execution_money_flow` | ❌ Blocked | `RebalanceRequestQueue.consume()` deletes each request once evaluated — no history |
| Y | Execution & Money-Flow | `execution_money_flow` | ❌ Blocked | `EventsStore.replace_kind()` deletes past events every calendar pull — no archive |
| E (pair) | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `correlation_coverage.py` |
| E (concentration) | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `concentration_coverage.py` |
| B | Regime & Risk Coverage | `regime_risk_coverage` | 🆕 Needs new scheme | no `strategy_family` categorical concept exists anywhere |
| N | Regime & Risk Coverage | `regime_risk_coverage` | ⏸ Deferred | same dependency-cost tradeoff as Q |
| V | Regime & Risk Coverage | `regime_risk_coverage` | 🔍 Needs investigation | `paper_performance` confirmed overwrite-only, no promotion timestamp found yet; also needs a new Pearson-correlation helper |
| H (governance) | Governance & Freshness | `governance_freshness` | ✅ Built | `skill_edit_governance.py` |
| H (consistency) | Governance & Freshness | `governance_freshness` | ✅ Built | `consistency_freeze.py` |
| O | Governance & Freshness | `governance_freshness` | ⏸ Deferred | rejected orders carry no `artifact_id`; "which artifact got blocked" needs a weak symbol+time-window match, not a stored key — a real decision, not a missing investigation (the "eventual performance" half is otherwise real and computable via `decay_snapshots`) |
| R | Governance & Freshness | `governance_freshness` | ❌ Blocked | `ticker_summaries` is explicitly current-state-only (its own docstring says so) |
| F | Governance & Freshness | `governance_freshness` | ❌ Blocked | `significance_flags` has no join key (not even weak) to any later trade/artifact outcome |
| W | Governance & Freshness | `governance_freshness` | ✅ Built | `threshold_calibration.py` (2 of the design doc's 3 named checkpoints — the third has no real writer) |
| I | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `screener_agreement.py` |
| X | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `screener_agreement.py` (same module as I) |
| J | External-Signal Cross-Check | `external_signal_cross_check` | ❌ Blocked | `regime_tag` is set once at artifact creation, never updated — no transition event stream |
| T | External-Signal Cross-Check | `external_signal_cross_check` | 🚧 Structurally blocked | depends on `MaturityAssessor`, which doesn't exist yet |

**Legend**: ✅ built & tested · ❌ blocked (real data doesn't support the
design as written — needs a new writer or a rescoped design) · ⏸
deferred (real tradeoff, not a gap — a decision to make, not data to
find) · 🆕 needs a new scheme invented (not just a missing writer) · 🔍
needs real investigation before it can be trusted as buildable · 🚧
structurally blocked on another not-yet-built component · 📋 needs a
written spec for something with no precedent in this codebase.

## The 6 analysts — completion by cluster

The "6 analysts" are groupings of the 25 analyses, not separate
components to build — each analyst is just `ANALYSTS` list entries
(functions) sharing a `cluster` label on their `Finding`s. There is no
per-analyst code to write beyond its member analyses' `run()` functions.

| Analyst | Analyses | Built | Blocked/deferred | Needs work |
|---|---|---|---|---|
| Decision-Process / Cognition | D, L, K, M | 3 (D, L, M) | 1 (K) | 0 |
| Forecast Intelligence | A, Q, P, G, S | 1 (A) | 3 (Q, P, G) | 1 (S) |
| Execution & Money-Flow | C, U, Y | 1 (C) | 2 (U, Y) | 0 |
| Regime & Risk Coverage | B, E, N, V | 2 (E — both pieces) | 1 (N) | 2 (B, V) |
| Governance & Freshness | O, R, F, W, H | 3 (H — both pieces, W) | 3 (O, R, F) | 0 |
| External-Signal Cross-Check | I, J, T, X | 2 (I, X) | 2 (J, T) | 0 |

**Decision-Process and Governance & Freshness are now the clusters with
every implementable analysis actually done** (Decision-Process: 3 of 4,
K's blocker is a real data gap; Governance & Freshness: 3 of 5 — H both
pieces plus W — with O/R/F all landing on real, checked blockers/
deferrals once investigated, not neglect). Regime & Risk Coverage and
Forecast Intelligence are the two clusters with real, still-open
next-wins left (V, B).

---

## How each remaining group actually gets closed

**The 6 blocked ones (K, P, G, U, Y, J, R — 7 total)** all share the same
shape: the design doc assumed a historical record exists; the real store
either overwrites, deletes-on-consume, or was never wired to persist
that field. Closing any of them needs the same two-step decision, made
per case:
1. Decide whether the missing history is worth adding a new writer for
   (e.g. an append-only audit table alongside `RebalanceRequestQueue`'s
   consume-once queue for U; archiving `EventsStore` rows instead of
   deleting them for Y; a structured injected-memory-ids record in
   `context.py` for K).
2. If yes, add that writer first (small, additive, ships inert like
   every other addition in this codebase), then the analyst itself is a
   normal one-day build, same shape as D/A/C.
2b. If the history genuinely isn't worth adding, the analysis stays
   permanently out of scope — that's a legitimate outcome too, not a
   failure to resolve.

**B (needs a new scheme)**: requires designing a `strategy_family`
taxonomy (most likely: keyword-parsing `signal_definition`, or adding a
new explicit field at artifact-creation time) before any query can be
written. This is a design decision, not an implementation task — resolve
it the same way `03-severity-and-trend.md`/`04-reference-baseline-config.md`
resolved the PSI-threshold questions: research external convention, pick
something grounded, document the reasoning, then build.

**Q and N (dependency-cost deferrals)**: both need data that currently
only exists inside vinu-initial-analysis (`WeightsStore` checkpoints for
Q, angle-result Parquet for N), the one service too dependency-heavy
(torch/xgboost/chronos-forecasting/timesfm) to mount-and-import the way
every other analyst in this service does. Real options, not yet decided
between: (a) extend the shared ticker-profile mechanism
(`vinu-infra/TICKER_PROFILE.md`) so `vinu-initial-analysis` projects the
specific fields Q/N need into the existing lightweight JSON files — this
is exactly the kind of gap that mechanism exists to close; (b) write a
narrow, torch-free reader that only opens the `.pt`/Parquet files'
metadata without importing the owning package; (c) accept the cost and
mount vinu-initial-analysis anyway if Q/N turn out to matter enough.

**T (structurally blocked)**: nothing to do until `MaturityAssessor`
itself is built — that's a separate, larger piece of work (the "brain,"
step 8 of `00-decided-pattern.md`), not part of the 25-analysis build at
all. Revisit T once that exists.

**S (needs a spec)**: needs someone to actually design the numeric-claim
extraction approach (likely: regex/number-parsing over the deterministic
fact sheet's known fields, cross-checked against the same numbers
appearing in the LLM summary's prose) before it's buildable. Nothing
else in this codebase does this kind of text-vs-structured-data
comparison to model it on.

**H-consistency and W, investigated and built 2026-09-19**: both turned
out cleaner than the design doc assumed. `freeze.py` needed no refactor
at all (it was just never wired into the installed package — fixed by
moving it into vinu-infra's own flat layout); W lost its counterfactual
ambition (no sweep helper exists anywhere) but kept a real, honestly
narrower drift-detection question, built for its 2 real checkpoints.

**O and F, investigated 2026-09-19 — real blockers found, not built**:
- **O**: the "eventual performance of a blocked artifact" half is real
  and computable (`decay_snapshots` is populated by the offline
  promotion pipeline, independent of whether live order submission was
  ever blocked). The real blocker is narrower than the design doc
  implied: `order_rejected` audit entries carry no `artifact_id` at all
  — identifying *which* artifact a rejection blocked needs a
  symbol+time-window match, not a stored key. A real decision (accept
  the weak match, or add `artifact_id` to `order_rejected` logging
  first), not a missing investigation — same shape as the K/U/Y
  new-writer decisions above.
- **F**: genuinely blocked, no real or weak join found. `significance_flags`
  has no `artifact_id`/order/trade id at all, only `ticker` — there's no
  stored key connecting a flag to any later trade or artifact outcome,
  weak or otherwise. Would need a new field added to `significance_flags`
  at flag-creation time before this is buildable at all.
- **V**: still needs a `promoted_at`-equivalent timestamp tracked down (or
  added) and a small Pearson-correlation helper written (this codebase
  only has PSI machinery today) — not reinvestigated this pass.

---

## Where to continue, ranked

1. **V investigation** — needs a `promoted_at`-equivalent timestamp
   tracked down (or added) and a small Pearson-correlation helper
   written; not yet chased down to the same certainty O/F/W just got.
2. **The new-writer decisions (K, U, Y, O)** — product/design calls, not
   implementation ones; O joined this group 2026-09-19 once investigated
   (weak symbol+time join vs. adding `artifact_id` to `order_rejected`).
   Worth a deliberate pass once someone decides whether closing any of
   them is worth the new writer/field.
3. **B's taxonomy design** — a real design task, same weight as the PSI
   threshold work already done in `03-severity-and-trend.md`.
4. **Q/N's dependency-cost decision** — likely resolved by extending the
   ticker-profile mechanism, once someone confirms Q/N's fields are
   worth adding to it.
5. **S's spec** — needs a design pass with no existing precedent to
   build from.
6. **F** — genuinely blocked until `significance_flags` gains a real join
   key at flag-creation time; not actionable without that schema change.
7. **T** — blocked until `MaturityAssessor` exists; not this file's
   scope to unblock.

Once **the reader** exists (the actual gap `02-analyst-interface.md`
still flags as open — every analyst writes, nothing reads
`reflection_beliefs` yet, because the reflection worker's *consumer*,
"the brain," doesn't exist), the 10 analyses already built become
genuinely useful, not just tested in isolation. That's arguably a higher
lever than finishing the remaining 15 — worth weighing against this
list.
