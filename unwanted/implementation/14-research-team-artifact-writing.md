---
name: research-team-artifact-writing
status: done
purpose: as-built record of closing research team's two real gaps (angle-blind idea_generator, PASS verdicts with no effect on OrderGuard) instead of building strategist/strategy_lab as separate teams.
---

# research team: angle-awareness + real artifact writing

## The decision this follows

After [13-vinu-research-in-process-migration.md](13-vinu-research-in-process-migration.md)
surfaced that `research`'s underlying loop (`idea_generator` →
`backtest_runner` → `risk_critic`) already does most of what
[../new-thinking/think-1.md](../new-thinking/think-1.md)'s `strategist`/
`strategy_lab` were designed to do — generate → backtest → gate — the
call was: enhance `research`'s two real, concrete gaps instead of
standing up a second, parallel pipeline that would duplicate it. See the
conversation for the full reasoning; this file is just the as-built
record.

## Gap 1 — `idea_generator` was angle-blind

`teams/research/agents/idea_generator/AGENT.md`'s `tools:` list gained
`get_all_angles` (same tool `screener` uses). Its prompt now requires
calling it and grounding the idea in whichever angles actually have real
data (`row_count > 0`) for the symbol — same discipline `screener`'s
`angle_synthesizer` already enforces, not a new rule invented here.

## Gap 2 — a PASS verdict never touched `vinu-research`'s real storage

Before this: `research`'s manager could reach `VERDICT: PASS` and that
was the end of it — nothing wrote to `strategy_store.db`, so
`OrderGuard._check_active_artifact` (see #13) would never see it, no
matter how many times research approved a strategy for a symbol.

**Fix, in three pieces:**

1. `teams/research/manager_prompt.md`'s final-answer requirements gained
   one addition: after its existing prose summary, end with a fenced
   ` ```json ` block — `{verdict, symbol, sharpe, max_drawdown,
   strategy_code}` — real values only, never invented. Additive, not a
   replacement of the existing prose requirements.
2. New `vinu_agent/agent/research_artifact_writer.py` —
   `write_artifact_from_research_pass(content, strategy_store,
   source_run_id)`: extracts that JSON block, and on `verdict == "PASS"`
   with both `symbol` and `strategy_code` present, builds a real
   `vinu_research.models.Artifact` and calls
   `strategy_store.upsert_artifact(...)`. **Written at status
   `BENCHING`, not `ACTIVE`** — deliberate: `research`'s 3-specialist
   team is real but simpler than vinu-research's own full promotion bar
   (deflated Sharpe, out-of-sample holdout, stress test, correlation
   gate). Claiming `ACTIVE` here would overstate this team's own rigor.
   Promoting `BENCHING → ACTIVE` is a separate, later step (vinu-research's
   own promotion tooling, or a future capital-allocation team) — not done
   here, and not pretended to be done. Best-effort throughout, same
   contract as `broker/debrief.py`: any failure here is logged and
   swallowed, never raised, never breaks the research team's own primary
   result.
3. `agent/team.py::TeamManager` gained a `strategy_store` param and one
   small, explicitly-commented hook in `run()`: if `self.spec.name ==
   "research"` and the run completed, call the writer and attach
   `artifact_id` to `result_json` if one was written. **Deliberately not
   generalized into a per-team dispatch table** — there's only this one
   real case so far; a second team needing the same shape (e.g. a future
   `post_trade_review`) is the trigger to actually generalize it, not
   before.

## One real bug caught and fixed while adding this

`source_run_id` on the real `Artifact` model is an `int` (a
vinu-research backtest run id) — `vinu-agent`'s own `run_id` is a hex
string from a completely different id space (`team_runs`'s
`_new_id()`). Tried to pass it through directly at first; caught before
committing that this doesn't fit. Fix: don't force it — the real link
back to which `vinu-agent` run produced a given artifact lives in
`team_runs` (already keyed by that same `run_id`), not duplicated onto
the artifact's `source_run_id` field, which stays for vinu-research's own
backtest-run provenance only.

## `strategy_store` threaded through the same DI chain as `run_store`/`llm_call_store`

`tools/__init__.py::build_registry(strategy_store=...)` →
`tools/delegate_tool.py::DelegateToTeamTool._strategy_store` →
`agent/team.py::TeamManager(strategy_store=...)`, and
`session/service.py`/`service.py::AgentService` thread it the same way.

**One thing worth calling out explicitly**: `AgentService` builds this
via `broker/research_link.get_strategy_store()` (#13's helper) — **the
exact same real `strategy_store.db` `OrderGuard` already reads**, not a
second copy. This is the concrete payoff of the "one shared storage, not
many" principle: a `research` team PASS is now visible to the same
active-artifact check that gates real orders, because they're reading
and writing the same file, not two systems that happen to agree by
coincidence.

## Tests

- New `tests/test_research_artifact_writer.py` (6 tests): PASS writes a
  real artifact with correct fields; STOP writes nothing; missing/
  malformed JSON block doesn't raise; a store failure is swallowed, not
  raised; missing symbol/code skips the write.
- New `tests/test_team.py::TestResearchArtifactHook` (3 tests): PASS
  writes an artifact and attaches `artifact_id` to `result_json`; no
  `strategy_store` configured skips the hook without error; a
  *non*-research team's PASS-shaped content never triggers it (asserted
  via a store whose `upsert_artifact` raises if called at all).
- New `tests/test_tools_discovery.py::test_build_registry_injects_strategy_store`.
- **Self-caught mistake while editing `tests/test_team.py`**: an early
  edit's exact-match replacement accidentally dropped 3 trailing
  assertions from the pre-existing
  `test_llm_call_store_tags_manager_and_specialist_calls_distinctly` test
  (the file had more content after the point I'd assumed was EOF).
  Caught by `git diff` showing removed lines before treating the test
  suite's "still passing" count as sufficient proof nothing broke — a
  passing suite doesn't catch assertions that were deleted outright, only
  ones that would have failed. Restored via `git show HEAD:...` for the
  exact original text, then confirmed `git diff | grep '^-'` was empty
  before moving on.

`python -m pytest -q`: **404/404 passing** (was 394 before this slice).

## What's still not done

Promotion `BENCHING → ACTIVE` for these artifacts — real, deliberately
out of scope here (see Gap 2 above). Until something promotes them, a
`research`-approved strategy still won't pass `OrderGuard`'s
`require_active_artifact` check, which is honest given this team's
current rigor, but is the next real gap once someone wants a `research`
PASS to actually be tradeable end to end.
