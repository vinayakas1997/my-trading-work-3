---
name: vinu-components-shortcomings
status: findings from direct code audit of /home/somic_cps/Vina/my-trading-work-3/vinu-components (2026-08-17)
purpose: concrete, code-verified gaps in the current implementation — not doc-guessed, not stale. Cross-checked against the plan docs at New-talk-agents/new-restructure/phases/ by tracing real call sites, not trusting "done" claims.
---

# Shortcomings found in vinu-components

Context: `New-talk-agents/new-restructure/mermaid-explanation.md` (now copied into
this folder) describes the pipeline as `proposed-not-built` in most places.
A direct code audit found that's stale — most of what the doc calls unbuilt
(TickerLedger, Thesis Intake, Significance Triage, cross-angle consensus,
sweep-engine wiring, kill switch) is actually real, wired, and tested. The
list below is what's still genuinely missing or broken, confirmed by tracing
actual call chains in the code, not by reading plan docs.

## 1. `capital_allocator` has no schedule

Fully wired and correct when invoked — `team.py`'s dispatch branch calls
`apply_capital_allocator_decision`, `allocation_tool.py` filters PEND
artifacts and POSTs to `/portfolio/evaluate-batch` (a real route in
`vinu-portfolio/vinu_portfolio/server/app.py`). But nothing calls this team
on an interval. Grep across the whole tree found no cron/loop invoking
`delegate_to_team("capital_allocator", ...)`. Approved candidates can sit in
the PEND state indefinitely unless something else happens to trigger that
team branch.

**Fix shape:** same pattern already used for six other workers in
`vinu-agent/entrypoint.sh` (`planner-worker`, `significance-worker`, etc.) —
add a `capital-allocator-worker` process on a fixed cadence.

## 2. `ShadowEvaluator.evaluate_all()` has no schedule

Same shape of gap. `vinu-live/vinu_live/cli.py` and
`server/app.py:59-64` both expose a way to call it, but only manually (CLI)
or via an HTTP route that has to be hit externally. No automatic trigger
exists anywhere. Shadow-vs-backtest comparisons only happen if something
outside the codebase calls them.

**Fix shape:** add `shadow-worker` (or extend the existing `shadow-worker`
process referenced in `entrypoint.sh` line 23, if it exists but doesn't
actually call `evaluate_all()` on its own timer — confirm this before
assuming it's already covered).

## 3. Monitor's rebalance-request path has no cross-process HTTP route

`orchestrator.py`'s `submit_rebalance_request` works in-process.
`capital_allocator_hook.py`'s unwind-request flow does call
`rebalance_guard.check_rebalance_allowed` (this is real — better than the
Phase 3 plan doc itself claims, see item 6 below), but the durable
cross-service channel from `capital_allocator` into the live orchestrator
isn't there yet. Self-reported as a known follow-up in Phase 5's own doc,
confirmed still true by direct code read.

## 4. Significance Triage delivery is inert

The code path is live and correct — `notify_channels.py`,
`build_channel_targets`, three real pattern detectors in
`significance_triage.py` (`detect_repeated_rejection_pattern`,
`detect_large_funding_pattern`, `detect_thesis_contradiction_pattern`). But
no Telegram/Discord credentials are configured in `.env`, so triage
detections currently fire into a void. This is the cheapest fix on this
list — it's operational/config, not a code gap.

## 5. No live-LLM validation anywhere

Two specific places are tested only against mocks, never against a real
model call:

- **Phase 1**: whether `idea_generator` actually follows the "try a sweep
  recipe first, raw code generation only as exception" instruction in
  practice — untested against a live LLM.
- **Phase 8**: whether the cross-angle consensus section added to
  `angle_synthesizer/prompt.md` actually produces sensible
  agree/diverge/insufficient_data verdicts when a real model reads it.

Both are legitimate "looks right on paper, unconfirmed in practice" gaps —
worth a real-LLM smoke test before leaning on either behavior.

## 6. Doc/reality mismatches (not code bugs, but worth fixing in the docs)

- Phase 1's plan doc describes explicit tool registration; the actual
  mechanism is `tools/__init__.py`'s automatic `BaseTool.__subclasses__()`
  discovery. Functionally correct, but anyone reading the plan doc expecting
  an explicit list will be confused.
- Phase 3's plan doc says `rebalance_guard` has "no real caller yet" — false;
  `capital_allocator_hook.py` calls `check_rebalance_allowed` for unwind
  requests. The doc understates what's actually built.

## 7. No position-sizing formula in `risk_gatekeeper`

Confirmed by comparison against the two reference repos (see
`02-reference-repos-core-logic.md`): `risk_gatekeeper` checks portfolio
*fit* (correlation, sizing vs. account) but has no actual sizing formula
(Kelly, ATR-based, or otherwise) deciding *how much* to put into an approved
candidate. This is a real capability gap, not just a nice-to-have.

## 8. No walk-forward validation next to PBO

Researcher/Executor's role c has `pbo.py` (overfitting probability) but
nothing that tests parameter stability across rolling time windows. PBO and
walk-forward catch different failure modes — this is a genuine complementary
gap, not redundant coverage.

## 9. Unconfirmed: LLM provider fallback

Not directly checked in the audit — worth verifying whether the Planner and
Researcher/Executor have any fallback if their primary LLM provider is down,
or whether a single-provider outage stalls the whole pipeline.

---

**Priority read:** items 1–2 share one root cause — real logic sitting
behind a manual/on-demand trigger instead of a scheduled one, the same gap
`entrypoint.sh` already solved for six other workers. Closing those two is
the highest-leverage next step. Item 4 (notification credentials) is the
cheapest fix on the list. Items 7–8 are the two genuine capability gaps
worth porting logic in for — see the companion file.
