---
name: AGENTS
status: living-document
purpose: mandatory progress log — every agent that touches a step must update this file
---

# AGENTS.md — Execution Log for the Steps-to-Implement Plan

This file is not a plan document — `00-overview.md` and the 10 step files
are the plan. This file is the **record of what actually happened** when
someone executed a step: which files were touched, what was tested, what
the result was. If `00-overview.md` answers "what should we do and why,"
this file answers "what has actually been done so far, by whom, and does
it work."

Any agent picking up this project cold should read `00-overview.md` first
for context, then read this file to know the *real* current state —
because a step file's own `status:` frontmatter can drift out of date if
someone forgets to update it in two places. Treat this file as the
source of truth for "is X actually done," over memory, over assumption,
over the step file's frontmatter alone.

## Rules

1. **Update this file in the same turn you finish (or pause) work on a
   step.** Not "later," not "next session." If you did the work and didn't
   log it here, the next agent has no way to know it happened.
2. **One entry per work session per step**, appended under that step's
   section below — do not overwrite or delete a previous entry. This file
   is a log, not a snapshot. If a step is touched five times before it's
   done, there are five entries.
3. **Every entry states, at minimum:** date, status after this session,
   files touched (exact paths), tests/checks actually run (command +
   result, not "should work"), and anything the next agent needs to know
   (blockers, surprises, decisions made).
4. **"Tested" means you ran something and saw the output**, not that the
   code looks correct. If nothing was runnable yet (e.g. pure design/doc
   work), say `No test applicable — design/doc only` explicitly rather
   than leaving the field blank. A blank field is indistinguishable from
   "forgot to fill it in."
5. **Update the status table below AND the step's own frontmatter AND
   `00-overview.md`'s phase table.** All three must agree. This file's
   table is the fast-scan summary; the entries below it are the evidence
   for why the table says what it says.
6. **Never mark a step `Completed` unless its Definition of Done checklist
   (in that step's own file) is fully checked.** If most of it is done but
   not all, the status is `In Progress`, not `Completed`. Partial credit
   goes in the entry's notes, not in the status column.
7. **If you discover a step file's plan was wrong or incomplete once you
   actually did the work** (a common occurrence per this plan's own
   history — see `00-overview.md`'s "core discovery" section), record that
   under that entry's notes and update the step file itself. Do not silently
   diverge from the written plan without leaving a trace of why.

## Status values

- `Not Started` — nothing done yet.
- `In Progress` — actively being worked; see latest entry for what's left.
- `Blocked` — see latest entry for what it's blocked on and which step.
- `Completed` — Definition of Done checklist fully checked, verified in an
  entry below, not just claimed.

## Status table

| Step | Code | Status | Last updated | Files touched (this run) |
|---|---|---|---|---|
| [01-verification-pass](01-verification-pass.md) | V0 | Completed | 2026-07-30 | 01-verification-pass.md, 03-gatekeepers-skill.md, 08-governor.md, 09-live-safety-doc.md, 00-overview.md |
| [02-tool-wiring](02-tool-wiring.md) | A2 | Completed | 2026-07-30 | 4 new vinu-agent tools, 4 new tests, routes_introspect.py, app.py, research_tool.py (bugfix), 02-tool-wiring.md, 00-overview.md |
| [03-gatekeepers-skill](03-gatekeepers-skill.md) | B1 | Completed | 2026-07-30 | gatekeepers/SKILL.md, gatekeepers/rules.yaml, 03-gatekeepers-skill.md, 00-overview.md |
| [04-strategy-tag-layer](04-strategy-tag-layer.md) | B2 | Completed | 2026-07-31 | strategy-tags/SKILL.md, strategy-tags/tags.yaml, 04-strategy-tag-layer.md, 00-overview.md |
| [05-tool-catalog](05-tool-catalog.md) | B3 | Completed | 2026-07-31 | generate_tool_catalog.py, vinu-tools-catalog/SKILL.md, vinu-tools-catalog/tools.yaml, test_generate_tool_catalog.py, 05-tool-catalog.md, 00-overview.md |
| [06-parameter-sweep-engine](06-parameter-sweep-engine.md) | A1 | Completed | 2026-07-31 | sweep.py, routes_sweep.py, app.py, run_sweep_candidate_tool.py, test_sweep.py, test_run_sweep_candidate_tool.py, 06-parameter-sweep-engine.md, 00-overview.md |
| [07-optimizer-rules-skill](07-optimizer-rules-skill.md) | B4 | Completed | 2026-07-31 | optimizer-rules/SKILL.md, optimizer-rules/rules.yaml, routes_hypothesis.py, app.py, hypothesis_write_tools.py, test_routes_hypothesis.py, test_hypothesis_write_tools.py, 07-optimizer-rules-skill.md, 00-overview.md |
| [08-governor](08-governor.md) | B6 | Completed | 2026-07-31 | governor/SKILL.md, governor/rules.yaml, 08-governor.md, 00-overview.md |
| [09-live-safety-doc](09-live-safety-doc.md) | B5 | Completed | 2026-07-31 | live-safety/SKILL.md, 09-live-safety-doc.md, 10-focus3-portfolio-intelligence.md, 00-overview.md |
| [10-focus3-portfolio-intelligence](10-focus3-portfolio-intelligence.md) | A3 | In Progress | 2026-07-31 | vinu_portfolio/regime.py (new), service.py, config.py, cli.py, server/app.py, routes_trade_plan.py (vinu-research), daily-allocation/SKILL.md (new), 4 new/extended test files |

*(Keep this table's "Last updated" and "Files touched" columns short —
one line, most recent session only. Full history lives in the per-step
entries below.)*

---

## Entries

*(Append new entries under the matching step's heading. Do not delete old
entries. Newest entry at the top of each step's section.)*

### 01-verification-pass (V0)

#### [2026-07-30] Completed

- **Files touched:**
  - `01-verification-pass.md` — all 5 Findings filled in with file/line citations, status flipped to Done.
  - `03-gatekeepers-skill.md` — added resolved note reconciling `_default_risk_critic` (loop.py) vs. `compute_validation_verdict`/PBO/promotion (they gate different moments, not redundant); removed the now-stale "carries forward Step 01's open question" risk line.
  - `08-governor.md` — added resolved note: `_is_improving()` (loop.py:934-939) is the existing single-round progress heuristic to extend, not replace; checkpoints are write-only today (no resume logic exists anywhere); expectancy heuristic confirmed genuinely new. Updated substeps 1-3 and the open-risks line accordingly.
  - `09-live-safety-doc.md` — added resolved note: `routes_broker.py`/`OrderGuard` claim confirmed accurate by direct read; **new finding** — `vinu_live/shadow_evaluator.py::ShadowEvaluator` is real, working BENCHING→ACTIVE paper-trading promotion logic that nothing currently calls (grepped every `vinu-*` service). Changed the doc's target shape from a two-stage to a three-stage diagram (promotion bar → ShadowEvaluator [built, dormant] → circuit breaker) and reframed the gap as a wiring task, not a design-and-build task.
  - `00-overview.md` — phase table row for Step 01 flipped to `Done`.
- **Tests/checks run:**
  - `Grep` for `_build_risk_critic_prompt` in vinu-research — confirmed it's a prompt formatter only (llm.py:32-96); real critic is `loop.py::_default_risk_critic` (read in full, loop.py:1622-1659) plus `_rule_based_check` (loop.py:1336-1418) and `_merge_feedback` (loop.py:1554-1576).
  - `Read` of `loop.py` in full (1770 lines, two passes due to truncation) — enumerated every break/stop path in the `run()` iteration loop; grepped the file for `resume`/`checkpoint` — only the `save_checkpoint` call exists, no read-back.
  - `Read` of `vinu_agent/server/routes_broker.py` in full — confirmed `/broker/halt`/`/broker/resume`/`/broker/status`/`/broker/order` and the `OrderGuard` reuse claim.
  - `Glob` of `vinu-live/vinu_live/**` and `Read` of `shadow_evaluator.py` in full — found `ShadowEvaluator`; `Grep` across all of `vinu-components` for `ShadowEvaluator`/`shadow_evaluator` — confirmed it's referenced only in its own file plus one comment in `feedback_loop.py`, never invoked.
  - `Glob` of `vinu-news/vinu_news/**/*.py` (source only, excluding `.venv`) — full module map; `Read` of `server/routes_read.py` — confirmed read-only HTTP routes (`/latest`, `/ticker/{symbol}`, `/watchlist/news`, `/search`).
  - `Grep` for `fts5|FTS5|fts4|virtual table` (case-insensitive) in `vinu_research/storage/sqlite_backend.py` — zero matches, confirmed absent.
- **Definition of Done progress:** both checklist items in `01-verification-pass.md` are checked — all 5 findings answered with citations, and corrections propagated into 03/08/09.
- **Notes for next agent:** two findings meaningfully change downstream premises beyond what their step files originally assumed — (1) `_is_improving()` already exists as a single-round progress heuristic, so Step 08 is an *extension*, not a fresh design; (2) the live-safety gap in Step 09 is "built but not scheduled" (`ShadowEvaluator`), not "doesn't exist" — this is a smaller, different task (wire up a call) than originally scoped. Step 02 is next in line (no dependencies, unlocks 03/08) — when writing its tools, note the open question left in Step 01 Findings §3 about whether to also expose vinu-news's raw article routes alongside the already-flowing angle summary.

### 02-tool-wiring (A2)

#### [2026-07-30] Completed

- **Files touched:**
  - `vinu-components/vinu-research/vinu_research/server/routes_introspect.py` (new) — `GET /research/hypotheses`, `GET /research/hypotheses/{id}`, `GET /research/symbols/{symbol}/state`, `GET /research/runs/{run_id}/checkpoints`.
  - `vinu-components/vinu-research/vinu_research/server/app.py` — registered `routes_introspect` router.
  - `vinu-components/vinu-agent/vinu_agent/tools/query_hypotheses_tool.py` (new)
  - `vinu-components/vinu-agent/vinu_agent/tools/symbol_research_state_tool.py` (new)
  - `vinu-components/vinu-agent/vinu_agent/tools/run_checkpoints_tool.py` (new)
  - `vinu-components/vinu-agent/vinu_agent/tools/backtest_validation_tool.py` (new)
  - `vinu-components/vinu-agent/vinu_agent/tools/research_tool.py` — one-line bugfix, see below.
  - `vinu-components/vinu-agent/tests/test_query_hypotheses_tool.py`,
    `test_symbol_research_state_tool.py`, `test_run_checkpoints_tool.py`,
    `test_backtest_validation_tool.py` (all new).
  - `02-tool-wiring.md` — added "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 02 → Done.
- **Tests/checks run:**
  - `pytest tests/test_research_tool.py tests/test_query_hypotheses_tool.py tests/test_symbol_research_state_tool.py tests/test_run_checkpoints_tool.py tests/test_backtest_validation_tool.py tests/test_tools_discovery.py -q` → 25 passed.
  - `pytest tests/test_hypothesis_registry.py -q` (vinu-research, regression check) → 23 passed.
  - `build_registry(services_config={})` — confirmed all 4 new tools auto-discovered by name.
  - `create_app()` route introspection — confirmed all 4 new routes mount at the expected `/research/...` paths.
  - End-to-end smoke test via FastAPI `TestClient` against a real `HypothesisRegistry` (temp-file backed, real `create`/`query_by_symbol` calls) plus a mocked `ResearchService.storage` — all 3 new `vinu-research` routes returned correctly-shaped real data (see transcript for exact output).
  - `get_backtest_validation` verified via unit test only (mocked `httpx.get`) — **not yet exercised against a live `vinu-simulator` instance.**
- **Definition of Done progress:** all 3 checklist items checked, with one caveat noted above (backtest_validation tool untested against a live simulator).
- **Notes for next agent:**
  - Found and fixed a real, pre-existing bug: `research_tool.py` was calling `{url}/run` instead of `{url}/research/run` — its own test suite already expected the correct path and was failing (`2 failed, 4 passed` before fix, `6 passed` after). This confirms every `vinu-*` service mounts its routes under `/{service_name}` via `route_prefix` in `create_app()` — remember this convention for any future tool that talks HTTP to a `vinu-*` service.
  - **Not fixed, flagged only:** `trade_plan_tool.py` and `portfolio_comparison_tool.py` build URLs against 6 different services and were not individually audited for the same prefix bug. Worth a dedicated pass before those tools are trusted in a live run.
  - **Deliberately not built:** a `query_judgment_history` tool. `JudgmentStore` is real code but is never instantiated anywhere outside its own test — wiring its write-path into `loop.py` is a behavior change belonging to Step 07/08, not this step. Don't build a query tool for it until that write-path exists, or it'll silently return empty and look broken.
  - Step 03 (gatekeepers skill) and Step 08 (governor) are now both unblocked — both were waiting on this step plus Step 01.

### 03-gatekeepers-skill (B1)

#### [2026-07-30] Completed

- **Files touched:**
  - `project-understanding/skills/gatekeepers/SKILL.md` — full rewrite.
  - `project-understanding/skills/gatekeepers/rules.yaml` — full rewrite, split into `candidate_evaluation` and `promotion_evaluation` sections.
  - `03-gatekeepers-skill.md` — added "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 03 → Done.
- **Tests/checks run:** No test applicable — design/doc only (skill files, not executable code). Every field name referenced was verified by directly reading the source function/dataclass it comes from (`compute_validation_verdict`, `probability_of_backtest_overfitting`, `CorrelationVerdict`, `meets_promotion_bar`/`PromotionVerdict`, plus `backtest-diagnose/SKILL.md` and `loop.py::_rule_based_check` for the reconciliation) — not guessed from the earlier discussion transcript.
- **Definition of Done progress:** all 4 checklist items checked.
- **Notes for next agent:**
  - Two new gaps surfaced (not fixed, out of scope for this step): PBO is computed per research run but never persisted (no `pbo` column in `research_runs`) — only visible in that run's live response, not retrievable later; and there's no dedicated read-only route to preview promotion eligibility without risking the mutating `/promote` call (documented an approximation via `GET /research/artifacts`'s existing fields, which can't cover the correlation piece).
  - One real, pre-existing inconsistency between two live pieces of code was found and deliberately left unresolved rather than silently decided: `backtest-diagnose/SKILL.md` calls OOS Sharpe > 0.7 a hard gate; `loop.py::_rule_based_check` (the actual running risk critic) only treats Sharpe < 0.5 as a soft suggestion. Both are documented in `rules.yaml`'s `is_oos_sharpe_floor` entry — if Step 07 or anyone else hits this tension in practice, surface it rather than assume one side is right.
  - Step 07 (optimizer-rules skill) is now one dependency closer to unblocked — still needs Step 06 (parameter sweep engine) and Step 04 (strategy tag layer) before it can start.

### 04-strategy-tag-layer (B2)

#### [2026-07-31] Completed

- **Files touched:**
  - `project-understanding/skills/strategy-tags/SKILL.md` (new)
  - `project-understanding/skills/strategy-tags/tags.yaml` (new)
  - `04-strategy-tag-layer.md` — "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 04 → Done.
- **Tests/checks run:** No test applicable — design/doc only. Verification was reading every one of the 4 real strategy YAMLs (`vinu-strategy/strategies/*.yaml`) in full and deriving tags from their actual `features_required`/`pipeline`/`angles_required` content, plus reading `vinu_strategy/api.py` and `vinu_strategy/server/routes_read.py`/`service.py` to confirm the `metadata`-field-visibility gap before choosing companion-file over extend-in-place. Sanity-checked the alignment-matching rule by hand against all 4 real strategies (see step file for the specific pairings).
- **Definition of Done progress:** all 3 checklist items checked.
- **Notes for next agent:**
  - Found a real, pre-existing architectural inconsistency in `vinu-strategy` (not fixed, out of scope): `GET /strategies` (list) reads from a separate SQLite `strategy_registry` table, while `GET /strategies/{name}` (detail) reads the actual YAML-based `StrategyRegistry`. These two routes can drift out of sync with each other. Worth its own investigation if anyone relies on the list route expecting YAML-registry accuracy.
  - `project-understanding/skills/` is a staging area, not the live `vinu-agent/skills/` directory the running agent actually reads via `load_skill_tool.py` — same convention already established by `gatekeepers/` and `optimizer-rules/` before this session. Moving staged skills into the live folder is not something any step so far has done; flag this as a likely need before Step 07's skill is actually usable by a running agent.
  - Step 07 (optimizer-rules skill) is now fully unblocked — all of 01, 02, 03, 04, and 06 are Done.

### Cross-cutting: codebase-wide route-prefix sweep (not tied to one step)

#### [2026-07-31] Fixed a systemic missing-route-prefix bug across the entire codebase

Triggered by the user asking not to leave the single flagged `loop.py`
bug (missing `import time`) unfixed. Fixing that led to a full-suite run,
which surfaced `trade_plan_tool.py`'s prefix bug was one instance of a
much larger, codebase-wide pattern: every `vinu-*` service mounts its
routes under its own `route_prefix` (`research`, `simulator`, `strategy`,
`analysis`, `features`, `stock`, `news`, `agent`, `portfolio`), and almost
no cross-service HTTP call anywhere in the codebase — except the handful
already fixed earlier this session — included it. Ran a full,
codebase-wide grep audit and fixed every real instance found.

- **`vinu_research/loop.py`** — added missing `import time` (the item that started this).
- **`vinu_research/tools.py`** — `ResearchTools.__init__` now bakes each service's prefix into its `ResilientClient` base URL at construction (fixes `run_backtest` and every other call through these 4 clients at once — this directly underlies Step 06's sweep engine and Step 07's whole design, which had never been run against a real service).
- **`vinu_simulator/service.py`** — same fix for `StrategyClient`/`PriceClient`/`FeaturesClient`.
- **`vinu_agent/broker/order_guard.py`** — `_check_active_artifact` and `_check_portfolio_concentration` were silently always failing open (their downstream calls 404'd, both checks fail-open by design on any exception) — fixed; these are real safety checks, not incidental.
- **`vinu_agent/tools/backtest_tool.py`**, **`trade_plan_tool.py`** (all 8 call sites, done earlier this session).
- **`vinu_portfolio/circuit_breakers.py`**, **`drawdown_scheduler.py`**, **`service.py`** (4 call sites) — the drawdown-monitor halt call was itself broken by this bug until fixed; see live-safety/SKILL.md's correction.
- **`vinu_live/`** — `feedback_loop.py` (3), `scheduler.py` (6), `shadow_evaluator.py` (3, one left correctly-shaped-but-still-broken since its target endpoint doesn't exist at all — see below), `trade_plan/orchestrator.py` (8).
- **`vinu_initial_analysis/cli.py`**, **`vinu_tools/service.py`**, **`vinu_tools/client/stock_price.py`** — smaller, same pattern.
- **`run_pipeline.py`** (repo-root orchestration script) — baked the prefix into the `SERVICES` dict's `base_url` values at the single definition point (fixes 12 call sites at once); found and removed one line that had *already* manually added `/research` — would have doubled up once the base URL carried it too.
- **New, deeper finding, not just a prefix issue:** `ShadowEvaluator._fetch_paper_sharpe` calls `/broker/performance/{artifact_id}` — this route doesn't exist anywhere in `vinu_agent/server/routes_broker.py`. Fixed the URL *shape* for consistency but left a comment: this call will still 404 until someone actually builds that endpoint. Not attempted here — real new feature work, out of scope for a prefix sweep.
- **`.env`** — stripped the redundant path suffixes that had been baked directly into 11 service URLs (e.g. `.../research`), which is what caused this bug to be invisible in casual testing (my early tool-code fixes were *correct* per the checked-in `.env-example` convention, but would have doubled up against this specific machine's `.env` until this was fixed too). Confirmed via user decision before editing — hostnames (docker-compose service names) were deliberately left untouched, only the redundant suffixes were removed.
- **Test files fixed to match corrected behavior** (several had been silently validating the *buggy* URLs as if they were correct — a different failure mode than a test correctly catching a bug): `vinu-agent/tests/test_trade_plan_validation.py`; `vinu-research/tests/test_routes.py` (`TestHealth`/`TestSettings` never updated when `route_prefix="research"` was introduced — every other test class in the same file already had it right), `tests/test_catalog.py` (separately, unclosed SQLite connections before Windows temp-dir cleanup — used `ResearchStorage`'s existing but unused context manager); `vinu-simulator/tests/test_sim_catalog.py`, `test_meta_validation_storage.py` (same SQLite-close pattern); `vinu-portfolio/tests/test_circuit_breakers.py`; `vinu-tools/tests/test_api.py`, `test_feature_spec.py`; `vinu-initial-analysis/tests/test_pnl_attribution.py`; `vinu-stock-price/tests/test_api.py`; `vinu-news/tests/test_api.py`, `test_tier_filter.py`.
- **Final state: 1370 tests passing across all 10 services.** Exactly 2 failures remain, both confirmed unrelated to this bug class and deliberately not fixed:
  1. `vinu-research/tests/test_config.py::test_load_config_defaults` — this specific machine's `.env` uses docker-compose hostnames (`research-api`, etc.); the test asserts `127.0.0.1`. A real, legitimate "local dev vs. docker deployment" convention difference, not a bug — changing docker hostnames wasn't part of what was approved.
  2. `vinu-strategy/tests/test_expression.py::test_division_by_zero` — an unrelated pre-existing bug in the strategy expression evaluator (doesn't raise `ZeroDivisionError` as its own test expects). Different bug class entirely; flagged, not touched, since fixing it requires a design decision (should it raise, or return inf/nan?) not obviously implied by a prefix sweep.
- **Notes for next agent:** if a new cross-service HTTP call is ever added anywhere in this codebase, it must either go through an already-prefixed client (`ResearchTools`, `SimulatorService`'s clients, `run_pipeline.py`'s `SERVICES` dict) or manually include the target service's `route_prefix`. This entire class of bug existed because that convention was never written down anywhere until now.

#### [2026-07-31] Closed both remaining failures — 1372 tests passing, 0 failing, across all 10 services

The user asked directly whether the two previously-flagged remaining
failures were actually fixed (they weren't — only documented) and asked
for a recommendation on ordering against Step 10. Recommended fixing both
first (quick, not design-scale work) so Step 10 starts from a genuinely
clean baseline; user agreed.

- **`vinu-strategy/tests/test_expression.py::test_division_by_zero`** —
  turned out not to be a bug at all. `engine/expression.py`'s `_eval_node`
  already deliberately catches `ZeroDivisionError` and returns `float("nan")`
  (correct behavior for a live strategy-signal evaluator — crashing
  evaluation on a momentary zero denominator would be far worse than
  propagating an unusable NaN downstream). The test was simply never
  updated after that design decision was made. Fixed the test to assert
  `math.isnan(result)` instead of expecting a raised exception — the code
  was right, the test was stale.
- **`vinu-research/tests/test_config.py::test_load_config_defaults`** —
  a real, two-layer test-isolation bug, not just an environment quirk as
  first characterized:
  1. `_reset_env_for_testing()` (`vinu_research/config.py`) only reset an
     internal `_env_loaded` flag — never cleared already-exported
     `VINU_*` keys from `os.environ`. Since `python-dotenv`'s
     `load_dotenv()` never overrides a variable already present in
     `os.environ`, any `VINU_*` var set once in a process (from a real
     local `.env`, or an earlier test) silently persisted through every
     later "reset." Fixed: `_reset_env_for_testing()` now deletes every
     `VINU_*` key from `os.environ`, with a comment explaining why the
     flag-only reset was insufficient.
  2. That alone wasn't enough — `force_reload=True` still calls
     `load_dotenv()` again, which just re-reads the real, legitimate local
     `.env` file (docker-compose hostnames) from disk. Fixed at the test
     level: `test_load_config_defaults` now monkeypatches
     `vinu_research.config.load_dotenv` to a no-op, so it asserts against
     the code's actual built-in defaults regardless of what any given
     machine's `.env` contains — makes the test deterministic across
     machines instead of accidentally depending on a clean environment
     that happened not to be the case here.
- **Final verification:** ran every one of the 10 services' full test
  suites in one pass. **1372 passed, 3 skipped, 0 failed.** Nothing left
  flagged-but-unfixed anywhere in the codebase from this session's work,
  except `ShadowEvaluator`'s missing `/broker/performance/{artifact_id}`
  endpoint (documented in `live-safety/SKILL.md` as real new feature work,
  not a bug — deliberately not attempted).

### 05-tool-catalog (B3)

#### [2026-07-31] Follow-up: fixed the trade_plan_tool.py prefix bug flagged since Step 02

- **Files touched:**
  - `vinu-components/vinu-agent/vinu_agent/tools/trade_plan_tool.py` — fixed all **8** missing-route-prefix call sites, not just the one with an existing test. Turned out every `vinu-*` service mounts under its own `route_prefix` (`research`, `simulator`, `analysis`, `features`, `stock`, `news`) and every single cross-service call in this file was missing it: `_symbol_has_analysis`/`_fetch_angles` (→ `/analysis/...`), `_fetch_features` (→ `/features/requests`), `_fetch_validation` (→ `/simulator/runs`, `/simulator/results/{id}`), `_fetch_liquidity_check` (→ `/stock/candles/{symbol}`), `_fetch_news` (→ `/news/search`), `_fetch_active_strategies` (→ `/research/artifacts`), `_fetch_frozen_trade_plan` (→ `/research/trade-plan/{symbol}`).
  - `vinu-components/vinu-agent/tests/test_trade_plan_validation.py` — updated its mock handler to match the corrected `/simulator/...` paths. This test had been silently validating the *buggy* behavior (its mock matched the unprefixed paths the broken code called) rather than catching it — different failure mode than `research_tool.py`'s test, which correctly expected the fix and was failing until Step 02's fix landed.
- **Tests/checks run:** Verified every relative path (`/symbols`, `/angle/{name}/{ticker}`, `/requests`, `/candles/{symbol}`, `/search`) against each service's actual route definitions before prefixing — confirmed all correct, only the prefix was missing. `pytest tests/ -q` (vinu-agent) → **208 passed, 0 failed** — the codebase's single remaining pre-existing failure from every prior step in this session is now resolved.
- **Notes for next agent:**
  - This was a systemic bug, not a one-off — worth remembering that "no test failure" does NOT mean "correct" when a test's own mock could be matching broken behavior. Three of `test_trade_plan_validation.py`'s four tests were passing before this fix precisely because they mocked the bug, not the contract.
  - `vinu_research/loop.py:288`'s `NameError` (missing `import time`, flagged during Step 06) is still open — that one is inside the research-loop's `Goal`-budget path, unrelated to this URL-prefix class of bug, and remains unfixed/out of scope.

#### [2026-07-31] Completed

- **Files touched:**
  - `vinu-components/vinu-agent/scripts/generate_tool_catalog.py` (new).
  - `project-understanding/skills/vinu-tools-catalog/SKILL.md` (new).
  - `project-understanding/skills/vinu-tools-catalog/tools.yaml` (new — `agent_tools` generated, `services` hand-written).
  - `vinu-components/vinu-agent/tests/test_generate_tool_catalog.py` (new, 3 tests).
  - `05-tool-catalog.md` — "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 05 → Done.
- **Tests/checks run:**
  - `python scripts/generate_tool_catalog.py` — ran for real, produced 29 agent-tool entries and preserved all 9 hand-written service entries.
  - `pytest tests/test_generate_tool_catalog.py -q` → 3 passed.
  - `yaml.safe_load` on the output — confirmed valid structure, correct counts, `services` section untouched by generation.
- **Definition of Done progress:** all 4 checklist items checked, with the CI/pre-commit wiring gap stated explicitly rather than implied solved.
- **Notes for next agent:**
  - 29 agent tools were found, not 26 (the file count) — several files register more than one `BaseTool` subclass (`trade_tool.py`, `hypothesis_write_tools.py`, `run_sweep_candidate_tool.py`). Worth remembering when eyeballing "how many tools exist."
  - `vinu_initial_analysis` and `vinu_stock_price` service entries are intentionally thin — not independently re-verified this session, and the catalog says so rather than presenting a guess as fact. Worth a real pass if anyone builds a tool against either.
  - `vinu_live` is confirmed unreachable from any current agent tool (absent from `vinu_agent/config.py`'s services dict) — consistent with Step 09's `ShadowEvaluator` finding.
  - This closes every remaining item in Phases 0-4. **Only Step 10 (Focus 3, independent track) remains in the entire plan.**

### 06-parameter-sweep-engine (A1)

#### [2026-07-31] Completed

- **Files touched:**
  - `vinu-components/vinu-research/vinu_research/sweep.py` (new) — `substitute_param_value`, `build_candidate_code`, `run_sweep_candidate`, `SweepCandidateResult`, `ParameterNotFoundError`.
  - `vinu-components/vinu-research/vinu_research/server/routes_sweep.py` (new) — `POST /research/sweep/candidate`, `GET /research/sweep/recipes`.
  - `vinu-components/vinu-research/vinu_research/server/app.py` — registered `routes_sweep` router, instantiates a shared `ResearchTools`.
  - `vinu-components/vinu-agent/vinu_agent/tools/run_sweep_candidate_tool.py` (new) — `RunSweepCandidateTool`, `ListSweepRecipesTool`.
  - `vinu-components/vinu-research/tests/test_sweep.py` (new, 13 tests).
  - `vinu-components/vinu-agent/tests/test_run_sweep_candidate_tool.py` (new, 7 tests).
  - `06-parameter-sweep-engine.md` — "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 06 → Done.
- **Tests/checks run:**
  - `pytest tests/test_sweep.py -q` (vinu-research) → 13 passed, covering AST substitution correctness (including "doesn't touch string/comment matches" and "only substitutes numeric constants"), both build modes' validation, and `run_sweep_candidate` with a mocked `ResearchTools`.
  - Manual script: real `substitute_param_value` on a hand-written `UserStrategy` class (confirmed `self.fast_period = 20` → `self.fast_period = 9`, other assignments untouched) and real `build_candidate_code(recipe="crossover", ...)` producing genuine generated strategy code.
  - `create_app()` + `TestClient` — confirmed `/research/sweep/candidate` and `/research/sweep/recipes` mount correctly; `GET /research/sweep/recipes` returned all 15 real recipes; `POST /research/sweep/candidate` with neither mode specified correctly returned 422.
  - `pytest tests/test_run_sweep_candidate_tool.py tests/test_tools_discovery.py -q` (vinu-agent) → 12 passed; confirmed both new tools auto-discovered by `build_registry()`.
  - Full-suite regression check: `pytest tests/` in both `vinu-research` (493 passed, 19 pre-existing failures — see below) and `vinu-agent` (197 passed, 1 pre-existing failure — see below), confirming this step introduced zero new failures.
- **Definition of Done progress:** all 3 checklist items checked, with the same "not yet run against a live simulator" caveat as Step 02's `get_backtest_validation`.
- **Notes for next agent:**
  - Two existing mechanisms did most of the work: `generator.py::generate_strategy(recipe, params)` (15 built-in recipes, each with named tunable params) for template-based candidates, and `ResearchTools.run_backtest` (already returns the full `validation` block via `.raw`) for execution. Only the base-code-mode AST substitution and the thin route/tool wrapper were genuinely new.
  - **Pre-existing bug reconfirmed, not fixed:** `trade_plan_tool.py` has the exact same missing-`/research`-prefix bug flagged in Step 02's notes (`test_trade_plan_frozen.py` fails against it). Still tracked there, not this step's scope.
  - **New pre-existing bug found, not fixed:** `loop.py:288` — `time.perf_counter()` called without `import time`, so any `run()` call that passes a `Goal` object crashes with `NameError`. Confirmed via a full-suite regression run with this step's changes both present and stashed away (same failure either way — not caused by this step). Whoever next touches `loop.py` (likely Step 07 or 08) should fix this before relying on goal-budget behavior.
  - **Process note:** a `git stash` run to isolate an unrelated test comparison accidentally stashed the entire repo's tracked working-tree changes (not just the intended files) and was popped back immediately — no work was lost, but worth remembering `git stash` is repo-wide, not path-scoped, unless `git stash push -- <path>` is used.
  - Step 07 (optimizer-rules skill) now only needs Step 04 (strategy tag layer) before it can start — 01, 02, 03, and 06 are all Done.

### 07-optimizer-rules-skill (B4)

#### [2026-07-31] Completed

- **Files touched:**
  - `project-understanding/skills/optimizer-rules/SKILL.md` — full rewrite.
  - `project-understanding/skills/optimizer-rules/rules.yaml` — full rewrite, `strategies:` section removed entirely, `parameter_library` kept and cross-referenced against all 15 real recipes.
  - `vinu-components/vinu-research/vinu_research/server/routes_hypothesis.py` (new) — mutating hypothesis routes, not covered by Step 02.
  - `vinu-components/vinu-research/vinu_research/server/app.py` — registered `routes_hypothesis`.
  - `vinu-components/vinu-agent/vinu_agent/tools/hypothesis_write_tools.py` (new) — `CreateHypothesisTool`, `AddHypothesisEvidenceTool`.
  - `vinu-components/vinu-research/tests/test_routes_hypothesis.py` (new, 4 tests).
  - `vinu-components/vinu-agent/tests/test_hypothesis_write_tools.py` (new, 8 tests).
  - `07-optimizer-rules-skill.md` — "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 07 → Done.
- **Tests/checks run:**
  - `pytest tests/test_routes_hypothesis.py -q` (vinu-research) → 4 passed, real `HypothesisRegistry` against a temp-file path (not mocked), exercising `create`/`add_evidence` end-to-end through the FastAPI route.
  - `pytest tests/test_hypothesis_write_tools.py tests/test_tools_discovery.py -q` (vinu-agent) → 12 passed; confirmed both new tools auto-discovered by `build_registry()`.
  - `python -c "yaml.safe_load(...)"` on the rewritten `rules.yaml` — confirmed valid YAML, correct top-level structure after removing `strategies:`.
  - Cross-checked every `seen_in_recipes` entry against the real `TEMPLATE_METADATA` params read during Step 06 — corrected two initially-incomplete lists (missed `macd`, `bollinger_bands`, `mean_reversion_zscore`, several `lookback`/`*_period` params on first pass).
- **Definition of Done progress:** all 4 checklist items checked.
- **Notes for next agent:**
  - The hypothesis write-tool gap was a real, confirmed blocker for this step's own Definition of Done, not scope creep — without it, "hypothesis-logging behavior" would have been documented but literally impossible to perform for any sweep-engine-driven candidate. Built minimally: two routes, two tools, matching existing patterns exactly.
  - The removed `strategies:` section is a deliberate, justified design correction, not an oversight — Step 06's `list_sweep_recipes` is the live source of truth for per-recipe parameters now; don't resurrect a hand-maintained strategy list here.
  - `optimizer-rules` and `governor` (Step 08) are explicitly a paired design — this step's algorithm stops "when Step 08's governor says stop," deliberately not defining its own stopping condition. Step 08 should be read alongside this file, not independently.
  - Phase 3 (A1/B4, i.e. Steps 06 and 07) is now fully done — **Focus 1's core deliverable is complete**: an agent can discover a strategy's real parameters, adaptively search them with hypothesis tracking, judge candidates against real gatekeepers, and fall back to an aligned strategy when one isn't working. Remaining work in the plan: Step 08 (governor — the actual stopping logic this step defers to), Step 09 (live-safety doc), Step 05 (tool catalog, never blocking), and Step 10 (Focus 3, independent track).

### 08-governor (B6)

#### [2026-07-31] Completed

- **Files touched:**
  - `project-understanding/skills/governor/SKILL.md` (new)
  - `project-understanding/skills/governor/rules.yaml` (new)
  - `08-governor.md` — "What was actually built" section, status → Done.
  - `00-overview.md` — phase table row for Step 08 → Done.
- **Tests/checks run:** No test applicable — design/doc only. Verification was reading `vinu_agent/agent/loop.py` in full to confirm the real 50-iteration cap and discover the 80%-budget wrap-up nudge (not previously known); re-confirming `_is_improving()`'s call sites are entirely within `vinu_research/loop.py` (grepped, zero references from the sweep engine); grepping `save_checkpoint` across the sweep engine (zero call sites, confirming Step 02's checkpoint tool doesn't apply here). `rules.yaml` validated as parseable YAML.
- **Definition of Done progress:** all 4 checklist items checked.
- **Notes for next agent:**
  - Two of this step's original assumptions (both inherited from before Step 07 existed) were corrected, not just implemented: (1) Layer 1 resumability uses Step 07's hypothesis/evidence tools, not Step 02's checkpoint tool; (2) the progress heuristic is new agent-reasoning logic inspired by `_is_improving()`, not a code edit to it — that function is unreachable from this loop.
  - New finding worth remembering for anyone touching agent orchestration: `vinu_agent/agent/loop.py` (the real ReAct loop, 50-iteration cap, 80%-budget wrap-up nudge) and `vinu_research/loop.py` (`StrategyResearchLoop`, the strategy-refinement loop) are two different files with the same name — same class of naming collision as "Monte Carlo" earlier in this plan. Always specify which one when writing about "the loop."
  - Phase 3 (A1/B4/B6 — Steps 06, 07, 08) is now fully complete. **Focus 1 is done**: sweep engine, evaluation criteria, adaptive search reasoning, and stopping logic all exist and are grounded in real, verified code. Remaining in the plan: Step 05 (tool catalog, never blocking), Step 09 (live-safety doc, depends only on Step 01 which is done), and Step 10 (Focus 3, independent track).

### 09-live-safety-doc (B5)

#### [2026-07-31] Completed

- **Files touched:**
  - `project-understanding/skills/live-safety/SKILL.md` (new) — four-stage chain (research promotion bar / ShadowEvaluator / drawdown circuit breaker / order-level enforcement).
  - `09-live-safety-doc.md` — "What was actually built" section, status → Done.
  - `10-focus3-portfolio-intelligence.md` — cross-referenced per this step's own Definition of Done; added a load-bearing note about the Stage-1-only-cleared gap for whoever designs Focus 3's allocation weighting.
  - `00-overview.md` — phase table row for Step 09 → Done.
- **Tests/checks run:** No test applicable — design/doc only. Verification was reading `vinu_research/promotion.py`, `vinu_portfolio/circuit_breakers.py`, `vinu_portfolio/drawdown_scheduler.py`, and `vinu_agent/server/routes_broker.py` in full, plus `vinu-portfolio/entrypoint.sh` and `docker-compose.yml`'s `portfolio-api` service definition to confirm the drawdown monitor genuinely starts by default in the deployed container (not just theoretically callable). Also checked for a `ShadowEvaluator` test file — none exists.
- **Definition of Done progress:** all 4 checklist items checked.
- **Notes for next agent:**
  - The chain grew from the planned 3 stages to 4 — order-level enforcement (`routes_broker.py`/`OrderGuard`) is a distinct real mechanism, not just plumbing for the circuit breaker's halt call, and deserved its own stage.
  - Found a direct, in-repo precedent for fixing `ShadowEvaluator`'s dormancy: `drawdown_scheduler.py`'s own docstring describes closing the exact same kind of gap ("built and tested but nothing called it") for the circuit breaker. Whoever eventually wires up `ShadowEvaluator` should read that file first as a template.
  - `ShadowEvaluator` is one level more dormant than initially known: no test file exists for it at all, not just no caller.
  - This closes Phase 4. Remaining in the plan: Step 05 (tool catalog, never blocking) and Step 10 (Focus 3, independent track, now has a documented safety-chain dependency to design around).

### 10-focus3-portfolio-intelligence (A3)

#### [2026-07-31] In Progress — substeps 2-4 done (regime-read, outcome-memory, v1 probability model)

- **Files touched:**
  - `vinu-components/vinu-research/vinu_research/server/routes_trade_plan.py` —
    new `GET /trade-plan/{artifact_id}/calibration` route (reads back
    `calibration_entries` via the existing `compute_calibration()`;
    previously write-only).
  - `vinu-components/vinu-research/tests/test_routes_trade_plan.py` — 3 new
    tests for the route (no entries, reflects recorded outcomes, unknown
    artifact returns an empty result rather than erroring).
  - `vinu-components/vinu-portfolio/vinu_portfolio/regime.py` (new) —
    `classify_current_regime()`.
  - `vinu-components/vinu-portfolio/tests/test_regime.py` (new) — 6 tests,
    including a deterministic-periodic-series fixture (rolling-vol
    quantile threshold made random-seed flaky when tested with pure
    Gaussian noise — fixed by using a period-3 cycle whose rolling(21).std()
    is identical across every window, since std depends only on the set of
    values in a window, not their order).
  - `vinu-components/vinu-portfolio/vinu_portfolio/config.py` — added
    `analysis_api_url`, `stock_api_url`, `benchmark_symbol`,
    `regime_tilt_bound`, `outcome_tilt_bound`,
    `min_calibration_entries_for_tilt`, `tags_path`, all via `from_env()`
    following the file's existing pattern; `analysis_api_url`/
    `stock_api_url` deliberately read from the same `VINU_CORRELATION_API_URL`/
    `VINU_STOCK_PRICE_API_URL` env vars `vinu-research` already uses (both
    already present in the real `.env`) rather than inventing new ones.
  - `vinu-components/vinu-portfolio/vinu_portfolio/service.py` — added
    `_fetch_benchmark_regime`, `_fetch_outcome_confidence`, `_load_tags`,
    `_regime_alignment_multiplier`, `_outcome_confidence_multiplier`,
    `_fetch_account_equity`, `compute_daily_allocation` to
    `PortfolioService`. Imports and wires `sizing.py::apply_position_sizing`
    (previously dead code, zero callers anywhere in `vinu_portfolio`).
  - `vinu-components/vinu-portfolio/vinu_portfolio/server/app.py` — new
    `GET /portfolio/daily-allocation` route.
  - `vinu-components/vinu-portfolio/vinu_portfolio/cli.py` — new
    `daily-allocation` one-shot subcommand (mirrors `build`'s shape).
    **Not** added to `entrypoint.sh` — on-demand only, by design.
  - `vinu-components/vinu-portfolio/tests/test_service.py` — extended with
    24 new tests across `TestFetchBenchmarkRegime`,
    `TestFetchOutcomeConfidence`, `TestRegimeAlignmentMultiplier`,
    `TestOutcomeConfidenceMultiplier`, `TestComputeDailyAllocation`,
    `TestFetchAccountEquity`.
  - `project-understanding/skills/daily-allocation/SKILL.md` (new) — full
    reasoning for every design decision below, written for the next agent
    to read before touching this code.
  - `10-focus3-portfolio-intelligence.md` — substeps 2-4 marked done,
    Definition of Done checkbox 2 checked.
- **Tests/checks run:**
  - `pytest vinu-research/tests/test_routes_trade_plan.py -q` → 12 passed
    (9 pre-existing + 3 new).
  - `pytest vinu-portfolio/tests/ -q` → 49 passed (19 pre-existing from
    substep 1's work + 6 new in `test_regime.py` + 24 new added to
    `test_service.py`, which went from 10 tests to 34).
  - Manual import sanity checks (`python -c "import vinu_portfolio.service"`,
    `.cli`, `.server.app`) after each edit, before running the full suite.
  - Full cross-service run after all changes: **1415 passed, 3 skipped,
    0 failed** across all 10 services (was 1382/3/0 before this entry's
    work; net +33 — 30 in vinu-portfolio, 3 in vinu-research — no
    regressions anywhere).
- **Definition of Done progress:** checklist item 2 (regime-read,
  outcome-memory, probability-model each have a resolved design) checked —
  with real, tested code, not just prose, matching every prior step's
  deliverable shape this session. Checklist item 3 (reviewed against
  Step 09 before live wiring) deliberately NOT checked — substep 5 stays
  not-started, a human/design checkpoint.
- **Notes for next agent:**
  - **Real, load-bearing finding from source, not guessed:** `tags.yaml`'s
    `regime:` vocabulary (`trending`/`ranging`/`mean_reverting`) and
    `regime_analysis`'s vocabulary (`bull`/`bear`/`high_vol`/`sideways`)
    were never reconciled anywhere in the codebase before this — confirmed
    by reading `tags.yaml`'s own per-strategy `notes`, which already
    reference `regime_analysis.regime == "bear"` etc. directly in each
    strategy's own signal-zeroing logic (inside `vinu-strategy`'s YAML
    pipeline), a vocabulary `tags.yaml`'s own `regime:` field never uses.
    Added one explicit, documented mapping constant
    (`_REGIME_TO_TAGS` in `service.py`) rather than silently assuming a
    1:1 match — `bull`/`bear` both map to `"trending"` (tags.yaml doesn't
    encode direction, a real ambiguity, not resolved, just documented);
    `high_vol` gets no tag comparison at all, deliberately, since every
    currently-tagged strategy already self-suppresses under `high_vol`.
  - **`regime_analysis`'s stored angle output cannot answer "what's the
    regime today"** — it's a window-aggregate (per-regime bucket stats
    across the whole analyzed history), not a per-day label. This wasn't
    obvious from the plan file's original framing ("reads current market
    regime from vinu-initial-analysis's angles") and only surfaced from
    reading `regime_analysis/compute.py` directly. Resolved by
    reimplementing the angle's own thresholding logic against just the
    latest observation, in `vinu_portfolio/regime.py` — documented as a
    deliberate reimplementation, not an accidental duplication.
  - Outcome-memory reuses existing storage exactly as the plan file's
    substep 3 asked ("check ResearchStorage... before adding a new one") —
    `calibration_entries`, keyed by `artifact_id`, already populated
    end-to-end by `vinu-live`'s feedback loop. The only gap was a missing
    read route, now added. **Still a real, documented gap**: YAML
    strategies have zero outcome tracking anywhere — `_fetch_outcome_
    confidence` always returns `"not_tracked"` for them, never fabricated.
  - **Still true, unaddressed, explicitly flagged (not silently
    inherited)**: Stage 2/`ShadowEvaluator` still never runs. The outcome-
    confidence tilt is a real but weaker proxy for "checked against
    reality since promotion" — not the paper-trading validation Stage 2
    was designed to provide. Closing Stage 2 remains separate, open work.
  - `sizing.py`'s `apply_position_sizing`/`vol_targeting_position_size`
    were dead code (confirmed zero callers anywhere in `vinu_portfolio`
    before this) — now wired in as `compute_daily_allocation()`'s final
    step, gated on live equity being fetchable (same call
    `drawdown_scheduler.py` already makes to `agent-api`'s
    `/broker/account`).
  - Deliberately did **not** add this to any scheduler or
    `entrypoint.sh` — on-demand route + CLI only, per
    `promote_scan_main`'s own precedent (a consequential action stays
    manually invoked, not a silent loop). Substep 5 (confirm against
    Step 09's safety doc before any live wiring) is the natural next
    piece of work, but is explicitly a human/design checkpoint, not
    something this pass self-certifies.

#### [2026-07-31] In Progress — substep 1 done, found and fixed a real bug

- **Files touched:**
  - `vinu-components/vinu-portfolio/vinu_portfolio/service.py` — bugfix, see below.
  - `vinu-components/vinu-portfolio/tests/test_service.py` (new) — 10 tests.
  - `10-focus3-portfolio-intelligence.md` — substep 1 marked done with full
    finding writeup, status → In Progress, Definition of Done checkbox 1 checked.
  - `00-overview.md` — phase table row for Step 10 → In Progress.
- **Tests/checks run:**
  - `pytest vinu-portfolio/tests/ -q` → 19 passed (9 pre-existing + 10 new).
  - Regression-verified the fix is load-bearing, not cosmetic: temporarily
    reverted `build_portfolio()` to the old buggy wiring and re-ran the new
    `test_allocator_receives_actual_returns_not_the_correlation_matrix` test
    — it failed (`DataFrame shape mismatch: (2, 2) vs (15, 2)`), confirming
    the correlation matrix really was being passed where returns belonged.
    Re-applied the fix, re-ran — passes.
  - Full cross-service suite re-run after the fix: **1382 passed, 3 skipped,
    0 failed** across all 10 services (was 1372/3/0 before this session's
    work on Step 10; net +10 from the new test file, no regressions anywhere).
- **Definition of Done progress:** first checklist item checked (baseline
  re-confirmed, with a bug found and fixed during the confirmation, not just
  noted). Substeps 2-4 (regime-read design, outcome-memory design,
  probability-model design) not yet started.
- **Notes for next agent:**
  - **Real bug found and fixed while doing substep 1's "re-read to confirm
    baseline" task** (not scope creep — this is exactly what the substep
    asked for): `build_portfolio()` was passing `compute_correlation_matrix()`'s
    output (a correlation matrix — values bounded [-1, 1], diagonal 1.0)
    into `allocate_risk_parity()`'s `returns_df` parameter. That function
    then computed `returns_df.std() * sqrt(252)` on it as if it were a daily
    returns time series and called the result "volatility" — it isn't;
    std-dev of correlation coefficients annualized by sqrt(252) is a
    meaningless number. Net effect: the "risk-parity" (inverse-vol)
    allocation has never actually weighted by real volatility since this
    code was written — it was weighting by noise shaped like the wrong thing.
  - Fix: extracted `_build_returns_df()` as a shared helper (previously
    inlined only inside `compute_correlation_matrix`). `build_portfolio()`
    now calls it once, passes the real returns frame to
    `allocate_risk_parity()`, and derives the correlation matrix
    (`returns_df.corr()`) from the same fetch instead of the other way
    around. `compute_correlation_matrix()`'s public signature/behavior is
    unchanged for any future caller.
  - Zero test coverage existed for `service.py` before this — no
    `test_service.py` existed at all, confirmed via `Glob` of
    `vinu-portfolio/tests/*.py` (only `test_circuit_breakers.py` and
    `test_drawdown_scheduler.py` existed). Added coverage for
    `allocate_risk_parity`, `compute_correlation_matrix`, `build_portfolio`,
    and `list_active_strategies`, following this repo's established
    `asyncio.run(...)` + `AsyncMock`/`MagicMock` pattern (matched from
    `vinu-live/tests/test_feedback_loop.py`, since `vinu-portfolio` has no
    `pytest-asyncio` dependency or `asyncio_mode` config).
  - **Corrected baseline for substeps 2-4 to design against:**
    `build_portfolio()` is a same-day, stateless pipeline (list active
    strategies → fetch returns → correlation matrix → inverse-vol weights).
    No regime-awareness, no memory of prior days' outcomes, no probability
    model — that part of the original plan-file framing was accurate. Only
    the volatility calculation itself was silently broken; now it's real.
    Design work on regime-read / outcome-memory / probability-model can now
    safely assume "inverse-vol weighting works correctly" as a component to
    build on top of, rather than needing to fix it first.
  - Still true, unchanged by this fix, per `09-live-safety-doc.md`: no
    ACTIVE strategy going into this allocator has ever been checked against
    paper-trading performance (Stage 2/`ShadowEvaluator` is dormant) — any
    probability-weighting design (substep 4) still needs to either account
    for that gap explicitly or treat closing it as a prerequisite.
  - Substeps 2-4 (regime-read via `AngleRunner`, outcome-memory store,
    probability model) not started — substep 4 in particular is flagged in
    the plan file as deserving its own dedicated design pass, not a quick
    continuation of this entry.

---

## Entry template (copy this when adding a new one)

```
#### [YYYY-MM-DD] <status after this session>

- **Files touched:** <exact paths, or "none — investigation only">
- **Tests/checks run:** <exact command + result, or "No test applicable — design/doc only">
- **Definition of Done progress:** <which checklist items in the step file are now checked>
- **Notes for next agent:** <blockers, surprises, decisions made, anything
  that diverged from the step file's original plan>
```
