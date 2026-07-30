---
name: 01-stage-skills
status: Completed
phase: 1
code: D1
depends_on: []
unlocks: [02-shock-clustering, 03-probabilistic-exit, 06-agent-integration]
---

# Step 01 — Stage Skills Live + Wire ShadowEvaluator

## Why this step

Everything built in the first 10-step plan is invisible to the running
agent. All 7 new skills sit in `project-understanding/skills/` — a staging
directory, not the live `vinu-agent/skills/` directory that
`load_skill_tool.py` reads at runtime. The agent's philosophy ("skills are
a knowledge library the agent composes at runtime") is literally impossible
today because the library isn't on the shelf the agent can reach.

Separately, `ShadowEvaluator` — Stage 2 of the live-safety chain (paper
trading validation between research promotion and live capital) — is built
code that has never been called, has no test file, and is wired to a
non-existent endpoint. The live-safety doc (Step 09) correctly identifies
this as a gap; this step closes it.

## What we're achieving

- All 7 staged skills are available in `vinu-agent/skills/` so the agent
  can read and compose them at runtime.
- `ShadowEvaluator` has a test file, is wired to a real endpoint, and can
  be invoked on demand.

## Where it matters in the future

Without this step, nothing else in this plan matters — the agent cannot
use any skill, and the live-safety chain has a known missing stage.
Every step in this plan depends on or benefits from this being done.

## How it connects to other steps

- **Depends on nothing** — pure mechanical work, no design decisions.
- **Unlocks Step 02** (shock clustering needs staged skills to reference).
- **Unlocks Step 03** (probabilistic exit skill needs to be live).
- **Unlocks Step 06** (agent integration obviously needs skills live).

## Substeps

1. **Copy skills live.** Copy every skill folder from
   `project-understanding/skills/` to `vinu-agent/skills/`. The 7 skills
   are: `gatekeepers`, `strategy-tags`, `vinu-tools-catalog`, `optimizer-rules`,
   `governor`, `live-safety`, `daily-allocation`. Verify each one has the
   expected file structure (at minimum `SKILL.md`, some also have
   `rules.yaml` / `tags.yaml` / `tools.yaml`).

2. **Verify agent can read them.** Use `load_skill_tool.py`'s existing
   machinery (or a direct test) to confirm the agent's skill-reading path
   discovers all 7. Write a short test if one doesn't exist for this.

3. **Audit ShadowEvaluator source.** Read `vinu_live/shadow_evaluator.py`
   in full. Identify:
   - What it needs to run (which endpoints, what data).
   - Why it's never called (confirmed: grepped earlier, zero callers).
   - The missing endpoint it calls (`/broker/performance/{artifact_id}` —
     does not exist in `routes_broker.py`).

4. **Build the missing endpoint.** Add `GET /broker/performance/{artifact_id}`
   to `vinu_agent/server/routes_broker.py`. This endpoint fetches the
   artifact's track record from the calibration data (Step 10's new route)
   and returns performance metrics the evaluator expects. Follow existing
   route patterns in that file.

5. **Write ShadowEvaluator tests.** Create a test file at
   `vinu-live/tests/test_shadow_evaluator.py` covering normal operation,
   no-data case (artifact with no outcome entries), and the case where the
   performance endpoint is unreachable.

6. **Wire the call.** Ensure the evaluator is callable on demand (no
   scheduler yet — Step 07 may schedule it for validation). At minimum,
   expose it via a CLI command or a route so it can be manually triggered.

## What was actually built

**Substep 1: Skills copied live.** All 7 skill folders copied from
`project-understanding/skills/{gatekeepers,strategy-tags,vinu-tools-catalog,optimizer-rules,governor,live-safety,daily-allocation}`
to `vinu-agent/skills/`. Total skills in agent directory: 29 (7 new + 22 existing).

**Substep 2: Agent can read them.** `SkillsLoader` confirms all 29 skills loaded
(verified via Python script). Existing `test_skills.py` (15 tests) continues to pass.
Encoding fix: `skills.py:53` changed from `read_text()` to `read_text(encoding="utf-8")`
— one existing skill (`options-trading/SKILL.md`) had a UTF-8 byte that cp1252
couldn't decode, which would cause a `UnicodeDecodeError` on any agent that
loaded all skills.

**Substep 3: ShadowEvaluator audited.**
- Needs: research API + agent broker/performance endpoint
- Missing endpoint confirmed: `/broker/performance/{artifact_id}` (now built)
- Two missing `await` bugs found and fixed: `_list_benching_artifacts()` and
  `_fetch_paper_sharpe()` both returned `resp.json()` as a coroutine instead of
  awaiting it (lines 55, 111). These would have caused `TypeError: 'coroutine'
object is not iterable` at runtime when BENCHING artifacts were present.

**Substep 4: Missing endpoint built.**
- `vinu_agent/broker/performance_store.py` — `PaperPerformanceStore` singleton with
  in-memory dict for per-artifact daily returns
- `GET /broker/performance/{artifact_id}` in `routes_broker.py` — returns
  `{"artifact_id": ..., "daily_returns": [...]}`
- `POST /broker/performance/{artifact_id}` — records daily returns for an artifact
  (called by vinu-live's cycle)

**Substep 5: ShadowEvaluator tests written.**
- `vinu-live/tests/test_shadow_evaluator.py` — 3 test cases:
  - Normal promotion (paper Sharpe > 0, degradation <= max)
  - Insufficient data (empty daily_returns → insufficient_data)
  - Unreachable endpoint (HTTP 500 → insufficient_data)

**Substep 6: Evaluator wired.**
- CLI: `vinu-live shadow-evaluate` added to cli.py
- Server route: `POST /live/shadow-evaluate` added to server/app.py
- `vinu_live` registered in `AgentConfig.services` dict (env var `VINU_LIVE_API_URL`)

**Surprises found:**
1. Missing `await` on two `resp.json()` calls in shadow_evaluator.py — these
   were latent bugs that would surface when BENCHING artifacts existed.
2. `options-trading/SKILL.md` contains non-cp1252 bytes — fixed by adding
   `encoding="utf-8"` to `SkillsLoader._load_from_dir`.
3. The performance data source is an in-memory store for v1 — persistent storage
   (e.g., new SQLite table in the research API) should be added when
   shadow evaluation is scheduled in Step 07.

## Definition of done

- [x] All 7 skills copied from `project-understanding/skills/` to
      `vinu-agent/skills/` — confirmed by listing both directories.
- [x] Agent can discover and read all 7 — confirmed by test or direct run.
- [x] `GET /broker/performance/{artifact_id}` exists and returns correct
      shape — confirmed by route test.
- [x] `ShadowEvaluator` test file exists with at least 3 test cases.
- [x] ShadowEvaluator is callable on demand (CLI or route).

## Open risks / assumptions

- The missing endpoint name (`/broker/performance/{artifact_id}`) was
  identified in the first plan's route-prefix sweep notes. Confirm the
  exact URL `ShadowEvaluator` calls by re-reading the source before
  building the endpoint — the name may differ from memory.
- `vinu_live` is not in `vinu_agent/config.py`'s `services` dict
  (confirmed in Step 05's findings). The ShadowEvaluator CLI/route may
  need to live in `vinu-live` or `vinu-agent` depending on where it's
  naturally callable — verify by reading how other services expose
  on-demand commands.
