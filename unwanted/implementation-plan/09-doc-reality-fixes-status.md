---
task: 09-doc-reality-fixes.md
status: complete
---

# Status: task 09 — fix two plan docs that understate/misstate what's actually built

## The two inaccuracies, located and corrected

### 1. `unwanted/New-talk-agents/new-restructure/phases/phase-1-sweep-engine-wiring/01-plan.md`

The doc claimed the sweep tools were "not registered in `build_registry`"
and that step 1 was "add them to `build_registry`". Verified against
`vinu-agent/vinu_agent/tools/__init__.py`: **registration is automatic** —
`build_registry` calls `_discover_subclasses()`, which imports every module
in the `tools/` package and collects `BaseTool.__subclasses__()` filtered to
`tools.` modules, then registers each whose `check_available()` passes. There
is no hardcoded registration list. The only explicit wiring is a team's tool
list.

- Frontmatter `status` → `built` + a correction note at the top of the file.
- The "not registered in build_registry" claim → describes auto-discovery and
  reframes the real gap as team assignment.
- Step 1 wording → "Make the existing tools visible to the research team"
  (registration automatic; the step that matters is naming them on the team's
  tool list).

### 2. `unwanted/New-talk-agents/new-restructure/phases/phase-3-kill-switch/04-implement-test.md`

The doc said `rebalance_guard` is "a standalone function with no real caller
yet" and that "nothing calls this function yet at all". Verified:
`vinu-agent/vinu_agent/agent/capital_allocator_hook.py` **does** call
`check_rebalance_allowed(ticker)` (fail-closed to the kill switch) before
POSTing each unwind entry to vinu-live's rebalance-request intake — wired by
implementation-plan task 04.

- Both the design-deviations paragraph and the follow-ups bullet rewritten to
  state the real caller, and to say any future Phase-5 rebalancer should reuse
  the gate rather than re-derive it.

## Step 3 — re-sync `00-full-initial-explanation.md` after tasks 01-08 landed

Re-read actual code, not the plan docs, and corrected these stale markers in
`new-vision/00-full-initial-explanation.md` (then mirrored to the original
`unwanted/New-talk-agents/new-restructure/mermaid-explanation.md`, confirmed
identical both before and after):

- **`status:` frontmatter** — `proposed-not-built (except where marked built)`
  → a partially-built status listing exactly what's now real and wired
  (sweep engine + `run_parameter_sweep` + pbo/`rank_candidates`, Kill Switch,
  TickerLedger, Thesis Intake, Significance Triage + notification delivery,
  cross-angle consensus, capital-allocator/shadow-evaluator scheduling,
  rebalance gating, risk gatekeeper, walk-forward validation, LLM fallback).
- **Kill Switch** — mermaid node "(deferred stub exists)" and the prose
  "A deferred stub already exists" → real, scope-corrected, always-on gate
  (incl. `rebalance_guard` caller and the cross-process file lock).
- **Researcher/Executor** — "wired to nothing" → wired into `backtest_runner`;
  role b's "Needs one new thin wrapper `run_parameter_sweep`" → wrapper
  exists; role c's `pbo`/`rank_candidates` "(built, unused)" → wired into
  `run_sweep_grid`'s `sweep_evidence_verdict` (+ walk-forward); the
  "Fail-closed addition" (`completeness`) → built.
- **Summary Agent** — "Upgrade pending: cross-angle consensus check" → built
  and verified live (task 08).
- **`list_sweep_recipes`** "(built, unwired)" → wired into `idea_generator`'s
  recipe-first path.
- **TickerLedger / Significance Triage** "(new ...)" → built; Significance
  Triage "— new." → built.
- **`risk_gatekeeper`** "Coverage fix:" (REJECTED → Significance Triage) →
  marked landed (task 03).
- **`capital_allocator`** "Rebalancer role: new, not built anywhere" →
  unwind-request path built and gated; only the replace-not-fund decision
  math remains.
- **Live + Shadow** — "route never implemented (404s today)" → the
  `/broker/performance/{artifact_id}` endpoint is implemented, and
  `ShadowEvaluator` now runs on a schedule (task 02).

Items deliberately left as-is (still genuinely not built / not touched by this
plan): paper-trade rehearsal role (d), Planner's HypothesisRegistry
pre-proposal consultation, Calibration Tracker wiring, skill-edit audit log,
Monitor's shock-angle trigger.

## Testing

- No code changed in task 09; no test runs needed beyond the code reads that
  grounded every correction (each stale claim was verified against the real
  file/line before editing).
- `cmp` confirms `new-vision/00-full-initial-explanation.md` and
  `unwanted/.../mermaid-explanation.md` remain byte-identical.

## Acceptance criteria

- Both specific inaccuracies corrected with the real mechanism/caller in
  place. ✓
- After tasks 01-08 landed, `00-full-initial-explanation.md`'s status language
  matches the real codebase state, verified by reading code (every edit cites
  the verifying file above), not by trusting the plan docs. ✓