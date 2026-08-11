---
name: planning-implementation-index
status: synced-to-real-system
purpose: index for all 9 pillars from ../archi-think-1.md. Written before vinu-research's real, more mature storage was discovered -- this index now tracks which pillars are synced to the real system (schema/method names updated to match), which were confirmed correct as-is, and which are still live, unbuilt proposals, rather than presenting all 9 as equally "done."
---

# Pillar implementation planning — index

## Read this first: what's actually true right now

- **Real code has been built** — but it's not these 9 pillars' schemas.
  `research` team's two gaps are closed
  ([../../implementation/14-research-team-artifact-writing.md](../../implementation/14-research-team-artifact-writing.md)):
  a PASS verdict now writes a real `vinu_research.models.Artifact` via
  the real `SqliteStrategyStore` — not the `strategy_specs` store pillar
  5 originally designed. `broker/order_guard.py` and `broker/debrief.py`
  now call `vinu-research`'s real `HypothesisRegistry`/`SqliteStrategyStore`
  directly, in-process
  ([../../implementation/13-vinu-research-in-process-migration.md](../../implementation/13-vinu-research-in-process-migration.md)).
  A second real team, `risk_gatekeeper`, is now built too — it approves
  or rejects a `research`-produced artifact against the real portfolio
  and, on approval, calls the new `mark_active()` transition (row 16) to
  move it BENCHING/MONITORING → ACTIVE
  ([../../implementation/00-status.md](../../implementation/00-status.md)
  row 17; per-team detail in
  [../../agents-explanation-in-detail/05-risk-gatekeeper.md](../../agents-explanation-in-detail/05-risk-gatekeeper.md)).
- **These 9 files are design reasoning, not the current build plan.**
  Each one below is now marked with its real status: **synced** (schema
  updated to match the real system, original thinking about *how* to use
  it kept), **confirmed** (the original idea turned out to be correct
  as-is, nothing to change), or **still open** (a real, unbuilt proposal
  — not superseded by anything, just not built yet).

| Order | File | Pillar | Real status | What that means |
|---|---|---|---|---|
| 1 | [01-pillar5-schema-and-field-visibility.md](01-pillar5-schema-and-field-visibility.md) | 5 — schema/shape | **synced** | `strategy_specs`/`memory_ledger` → use `Artifact`/`Hypothesis` directly (§0 in that file maps every field). `shadow_ledger_snapshots` still open — nothing real does this. |
| 2 | [02-pillar6-immutability-and-deletion-policy.md](02-pillar6-immutability-and-deletion-policy.md) | 6 — immutability | **synced** | Real `ArtifactStatus`/`promotion.py` already does the state machine, more strictly. This file's "narrow methods, no generic update" idea is now built: `transition_status`/`mark_active`/etc. on `SqliteStrategyStore` (`upsert_artifact` itself unchanged, still generic). |
| 3 | [03-pillar7-traceability.md](03-pillar7-traceability.md) | 7 — traceability | **confirmed** | `spec_id = artifact_id` turned out to be literally true (`Artifact.artifact_id` is the real ID). Nothing to change. |
| 4 | [04-pillar9-partial-and-failed-writes.md](04-pillar9-partial-and-failed-writes.md) | 9 — partial/failed writes | **still open** | Heartbeat/`stale`-status idea not checked against real vinu-research code yet; still a live, unbuilt proposal. |
| 5 | [05-pillar8-access-control.md](05-pillar8-access-control.md) | 8 — who's allowed to touch what | **confirmed** | "Never an agent tool, always manager-level Python" is exactly the pattern `research_artifact_writer.py` uses for real. Table's specific method names are superseded (see pillar 1). |
| 6 | [06-pillar3-harness-storage.md](06-pillar3-harness-storage.md) | 3 — storage for the harness | **confirmed** | Unrelated to vinu-research; `team_runs`/`llm_calls` reconciliation still accurate as written. |
| 7 | [07-pillar1-api-design.md](07-pillar1-api-design.md) | 1 — API design | **synced** | Real methods already exist (`upsert_artifact`, `query_by_symbol`, etc. — full list in that file's sync note). The "narrow wrapper per transition" idea is now built (`transition_status`/`mark_*`). |
| 8 | [08-pillar2-uniqueness-and-dedup.md](08-pillar2-uniqueness-and-dedup.md) | 2 — uniqueness/dedup | **checked and patched** | Checked against `Artifact.create()`'s real hash-based ID scheme — the "UUID4" identity claim was wrong (deterministic, unsalted hash) and the one real write path (`research_artifact_writer.py`) had no dedup guard at all; `HypothesisRegistry` (the real `memory_ledger`) also had no lock, so concurrent writers could silently lose data, worse than the duplicate-row risk this file worried about. All three patched — see §0 in that file. Cost-avoidance dedup (`strategist`'s `request_hash` reuse window) is still an unbuilt proposal. |
| 9 | [09-pillar4-external-vs-internal-access.md](09-pillar4-external-vs-internal-access.md) | 4 — external vs. internal | **boundary moved** | 2 of 39 real `vinu-research` call sites are now in-process, not HTTP — the rest of this file's read-only-externally rule still holds for everything else. |

## The one real correction made while cross-checking (before the sync pass above)

Pillar 8's first draft classified `create_version`, every `mark_*`
status transition, and `record_lesson` as agent-callable tools declared
in specific `AGENT.md` files. Checking that against the actual specialist
prompts already drafted in
[../../agents-explanation-in-detail/](../../agents-explanation-in-detail/)
showed none of them ever call such a tool — each specialist just returns
structured text as its final answer. Fixed to match the precedent
`team_runs`/`llm_calls` already established: these writes are
manager-level Python, called after a specialist's final answer is parsed,
never reachable from any LLM's tool-calling surface at all. This
prediction was later confirmed correct by the real build — see the table
above.

## What's still genuinely open across all 9

Carried forward, not resolved by this planning pass (each noted in its
own file, collected here for visibility):

- `capital_allocator` is now built
  ([../../implementation/00-status.md](../../implementation/00-status.md)
  row 18) with a real, working, deliberately provisional method
  (fixed-fractional sizing ranked by `deflated_sharpe`) — but *which*
  allocation math is right long-term (Kelly / fixed-fraction /
  risk-parity) is still genuinely undecided; building the team didn't
  answer that question, just stopped blocking on it. See
  [06-capital-allocator.md](../../agents-explanation-in-detail/06-capital-allocator.md)§6.
- `allocation_analyst` got a real tool (`compute_allocation_candidates`)
  rather than the manager gathering history itself — resolved, not open
  anymore.
- The exact reuse window for `strategist`'s request-hash dedup — pillar
  2, a tuning parameter, not an architectural question.
- `source_run_id` (upstream traceability from `screener`/`research` into
  `strategist`) — pillar 7, deliberately left to the orchestrator's
  conversation history unless proven insufficient later.
