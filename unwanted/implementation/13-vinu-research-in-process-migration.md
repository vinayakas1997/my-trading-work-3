---
name: vinu-research-in-process-migration
status: done -- see "Update 2026-08-11" at the end of this file for the completing pass; everything below this header is the original first-slice record, left as-is.
purpose: as-built record of discovering how much real infrastructure vinu-research already has, and the first slice of migrating vinu-agent off HTTP calls to it and onto direct in-process imports instead.
---

# vinu-research in-process migration

## The discovery this started from

While starting to implement the first new team from
[../new-thinking/think-1.md](../new-thinking/think-1.md) (`strategist`,
which needed a `strategy_specs` store and a `memory_ledger` store), a
routine check of `session/service.py` surfaced references to a real
`broker/` module and `audit/` module that weren't accounted for anywhere
in this session's design work — `PositionCloseDetector`,
`_build_broker`, `ResearchDigestReader`.

Following that thread found: **`vinu-agent` already has a mature,
extensive, tested integration with `vinu-research`** — 39 files reference
it, including a 1125-line `trade_plan_tool.py`, plus
`hypothesis_write_tools.py`, `query_hypotheses_tool.py`,
`run_sweep_candidate_tool.py`, `run_checkpoints_tool.py`,
`portfolio_comparison_tool.py`, `symbol_research_state_tool.py`, and the
real broker safety layer (`broker/mandate.py`, `broker/order_guard.py`,
`broker/kill_switch.py`, `broker/debrief.py`).

And `vinu-research`'s own code turned out to be far more mature than
what this session's "8 teams / 9 pillars" design (`../new-thinking/`)
had built from scratch: `Artifact`/`ArtifactStatus`
(`CREATED→BENCHING→ACTIVE→MONITORING→DECAYED→DISABLED`, gated by a real
promotion bar — deflated Sharpe ratio, out-of-sample holdout, stress
test, correlation gate), `HypothesisRegistry` (evidence-tracked research
theses), `TradePlan` with mechanically-evaluable `ContingencyRule`/
`InvalidationCondition` (`metric operator threshold → action`, not free
text), a real `shadow/` module (extractor/backtester/attribution),
decay snapshots, calibration tracking, walk-forward, PBO
(probability-of-backtest-overfitting).

**Honest assessment:** most of the `../new-thinking/` data-layer design
(`strategy_specs`, `memory_ledger`, `shadow_ledger_snapshots`)
substantially duplicated what already exists here, under different names
and less mature. What wasn't duplicated, and is still worth keeping, is
the agent-team orchestration layer itself (teams, delegation, the
manager-verification idea, the bull/bear/risk_officer debate pattern) —
that's genuinely new; the data it would operate on isn't.

## The direction, per explicit user instruction

Not a fresh rebuild, and not literally moving/rewriting `vinu-research`'s
~40 files into `vinu-agent`. The user's own framing: bring
`vinu-research`'s real components into `vinu-agent`'s architecture. The
actual technical shape that means: `vinu-research`'s Python package stays
exactly as it is (its logic is real and correct); only its **standalone
FastAPI server** (`server/app.py`, `routes_*.py`) is being retired, and
the HTTP call sites that currently reach it over the network get rewired
to import and call the same classes directly, in-process.

`vinu-agent`'s `pyproject.toml` now depends on `vinu-research` directly
(added alongside the existing `vinu-infra` dependency) — confirmed
importable in this environment before making any other change.

## What's done — the first, most safety-critical slice

Two of the 39 real call sites, chosen because they're the ones a broker
safety check can't afford to have fail due to a second service being
down:

- **`broker/order_guard.py::_check_active_artifact`** — was
  `requests.get({research_api_url}/research/artifacts, params={"status":
  "ACTIVE"})`, now
  `SqliteStrategyStore.list_artifacts_for_symbol(symbol,
  statuses=[ArtifactStatus.ACTIVE])`, reading `vinu-research`'s real
  `strategy_store.db` directly. Same fail-open-on-exception policy as
  before (an unreachable/corrupt local DB doesn't silently block all
  trading, same posture the class already documents for every other
  check). `OrderGuard.__init__`'s now-dead `research_api_url` parameter
  was removed rather than left as a misleading unused knob — confirmed no
  caller (including `trade_tool.py` and the test suite) ever passed it
  explicitly, so this was a safe removal.
- **`broker/debrief.py::_fetch_open_thesis_ids` /
  `_write_evidence`** — was `httpx.get`/`httpx.post` against
  `{vinu_research_url}/research/hypotheses...`, now
  `HypothesisRegistry.query_by_symbol(...)` /
  `HypothesisRegistry.add_evidence(...)` directly. The evidence written
  uses `run_id=0, iteration=0` — confirmed against
  `vinu_research/server/routes_hypothesis.py`'s own
  `AddEvidenceRequest` model, which defaults those same two fields to
  `0` — so this in-process call produces the exact same evidence shape
  the old HTTP call would have, not a redesigned one.

**New file**: `vinu_agent/broker/research_link.py` — the shared
in-process link both files above use (`get_hypothesis_registry()`,
`get_strategy_store()`), resolving `VINU_RESEARCH_DATA_ROOT` the same way
`vinu_research`'s own modules already do, so the in-process path always
points at the same data the old HTTP-serving process would have used.

## Tests

Both files' tests were rewritten from mocked HTTP responses to real
stores — `SqliteStrategyStore`/`HypothesisRegistry` against a tempfile,
same no-mocking-the-storage-layer convention already used for
`AngleStorage`'s and `TeamRunStore`'s own tests, rather than mocking
`requests.get`/`httpx.post` response envelopes as before. One new test
added (`test_rejects_when_artifact_exists_but_not_active`) that the old
HTTP-mocked version couldn't easily express — an artifact that exists for
the symbol but hasn't reached `ACTIVE` yet must still reject, not just
"no artifact at all."

`python -m pytest -q`: **394/394 passing** (was 386 before this slice;
the +8 are the debrief/order-guard test rewrites plus the one new test
above — net small increase since most tests were rewritten in place, not
purely additive).

## What's deliberately NOT done in this slice

The other 37 of 39 real `vinu-research` integrations
(`trade_plan_tool.py`, `research_tool.py`, `query_hypotheses_tool.py`,
`hypothesis_write_tools.py`, `run_sweep_candidate_tool.py`,
`run_checkpoints_tool.py`, `portfolio_comparison_tool.py`,
`symbol_research_state_tool.py`, `memory/sync_service.py`,
`audit/ground_truth.py`, `audit/research_digest.py`,
`audit/freshness.py`) still call `vinu-research` over HTTP, unchanged.
`vinu-research`'s FastAPI server therefore **cannot be retired yet** —
doing so now would break all 37 of those, not just stop an unused
process. This was a deliberate scope decision, not an oversight: migrate
the two safety-critical, always-in-the-hot-path checks first, prove the
in-process pattern works end to end (it does — 394/394), then migrate the
rest as a separate, larger pass before the server can actually come down.

Also not done: anything from `vinu-research`'s deeper modules (`shadow/`,
`walk_forward.py`, `calibration.py`, `decay.py`, `pbo.py`,
`trade_plan_authoring.py`, `scheduled/`) — none of `vinu-agent`'s current
code calls these directly yet (they're reached indirectly, through the
HTTP-based tools above), so migrating them has no urgency until those
tools' own migration is tackled.

## What this means for `../new-thinking/`

The 8-team / 9-pillar design there isn't wasted, but its data-layer
assumptions need revisiting against what's real: `strategy_specs` should
likely become a thin layer over `vinu-research`'s real `Artifact`/
`SqliteStrategyStore` rather than a new parallel schema; `memory_ledger`
should likely just be `HypothesisRegistry`, used directly. Not resolved
here — flagged so the next pass on `strategist`/`strategy_lab` starts
from this corrected understanding instead of the original, independently-
designed schemas.

## Update 2026-08-11 -- migration finished

Picked back up from `component-consolidation-plan.md`'s re-verified count
(26 real call-site files, not the "2 of 39" originally recorded above --
this doc's own numbers had drifted; corrected there, not rewritten here).
Confirmed by direct re-read at the time: 11 of 26 already had an
in-process path (the 2 from this doc's first slice, plus 6 more and 3
in-process-first-with-fallback files added in an earlier session not
recorded in this file). This pass finished the other 15:
`memory/sync_service.py`, `audit/research_digest.py`,
`audit/ground_truth.py`, `tools/hypothesis_write_tools.py`,
`tools/query_hypotheses_tool.py`, `tools/symbol_research_state_tool.py`,
`tools/run_checkpoints_tool.py`, `tools/find_trade_plan_tool.py`,
`tools/portfolio_comparison_tool.py`, `agent/significance_triage.py`
(`record_human_override`), `tools/submit_thesis_tool.py`,
`tools/research_tool.py`, `tools/run_sweep_candidate_tool.py` (+
`ListSweepRecipesTool`), `tools/run_parameter_sweep_tool.py`,
`tools/trade_plan_tool.py` (3 separate call sites within one file).

Same pattern throughout, no exceptions: try the real in-process path
first (`vinu_agent/broker/research_link.py`'s shared getters --
`get_strategy_store`, `get_hypothesis_registry`, `get_research_storage`,
`get_research_service`, `get_research_tools` -- plus serializers kept
byte-for-byte in sync with the FastAPI routes they replace), fall back to
the original HTTP call only on any exception. Every file's tests were
extended (not replaced) with real-store-backed in-process cases plus a
forced-fallback case (patching the relevant `research_link` getter to
raise), mirroring `trade_plan_calibration.py`'s own test convention.
Compute-heavy call sites (`run_research`, `run_sweep_candidate`,
`run_sweep_grid`, `author_trade_plan`/`freeze_trade_plan`) now run the
real research/backtest engine in-process too, not just reads -- these
were previously assumed out of scope ("no urgency" above) but turned out
to be the same mechanical pattern once `ResearchTools`/`ResearchService`
were confirmed cheap to construct per call.

`vinu-portfolio` turned out to have its own, entirely separate 3 HTTP
call sites against `research-api` (`_list_llm_strategies`,
`_fetch_outcome_confidence`, `_fetch_trade_plan` in
`vinu_portfolio/service.py`) -- not part of this doc's original scope at
all, discovered while re-verifying `component-consolidation-plan.md`'s
own claims. Given the identical treatment via a new, parallel
`vinu_portfolio/research_link.py` (vinu-portfolio has no `broker/`
package to put it in), plus `vinu-research` added to its `pyproject.toml`
dependencies.

**Real bug found and fixed, not just code migrated**: neither
`vinu-agent/Dockerfile` nor `vinu-portfolio/Dockerfile` installed
`vinu-research` (or its own transitive deps) into the built image --
only local dev/test environments had it editable-installed, so every
in-process import (including this doc's original 2-file first slice)
would have raised `ImportError` in the real deployed container and, for
`order_guard.py`'s active-artifact check specifically, silently
fail-opened a real safety gate. Both Dockerfiles now install
`vinu-stock-price`/`vinu-tools`/`vinu-simulator`/`vinu-research` in the
same order `vinu-research`'s own Dockerfile already does.

Full-suite results after this pass: vinu-agent 772 passed, vinu-portfolio
116 passed, vinu-research 610 passed/1 skipped -- no regressions in any
of the three.

`vinu-research`'s FastAPI server is still running today; nothing in this
pass retired it (that's a separate, later decision once every consumer
is confirmed migrated across the whole system, not just the two
codebases audited here). What this pass does close out is
`component-consolidation-plan.md`'s "Suggested order" item 1.
