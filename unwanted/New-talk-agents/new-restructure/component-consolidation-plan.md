---
name: component-consolidation-plan
status: proposed-not-built -- today's 10 containers keep running unchanged; this is the target shape if/when consolidation work starts. Re-verified 2026-08-11 against real current code -- several claims below were stale (written before later-session fixes landed) or wrong (written without reading the folded-in service's actual consumers); corrections are inline, marked "Re-verified 2026-08-11". A second pass later the same day (also marked "2026-08-11") finished the vinu-research in-process migration end to end (all 26 vinu-agent call-site files plus vinu-portfolio's separate 3) and fixed a real deployment-blocking bug found along the way: neither vinu-agent's nor vinu-portfolio's Dockerfile actually installed vinu-research, so every in-process import added by the migration would have raised in the real container and silently failed open -- see "Suggested order" item 1.
purpose: how many real deployment boundaries this system needs, and why -- checked against the actual docker-compose.yml dependency graph and real code in each service, not assumed.
---

# Component consolidation plan

Today's `docker-compose.yml` runs 10 services. Not all of those splits exist
for a real architectural reason -- several look like "one repo per team/
capability" rather than "one boundary because something requires it." This
doc works out which splits are load-bearing and which aren't, and what a
from-scratch design would look like if the current 10 didn't already exist.

**Leave today's containers exactly as they are.** This is a target shape to
work toward opportunistically (starting with the piece already mid-migration),
not a rewrite to schedule.

## The test: when does a boundary earn its cost

A service boundary costs a network hop, a separate deploy, a separate set of
things that can go wrong independently. It's only worth that cost if it buys
one of these:

1. **A genuinely different resource/scaling profile** -- bursty, slow LLM
   calls behave nothing like steady CPU-bound compute; putting them in the
   same process means one starves the other under load.
2. **A watchdog that must outlive the thing it watches** -- a drawdown halt
   is useless if it dies at the exact moment the thing it's supposed to stop
   goes haywire.
3. **Credential / blast-radius isolation** -- nothing holding real broker
   credentials should be one bug away from an LLM's tool-calling loop.
4. **Independent failure domains** -- one thing crashing shouldn't take an
   unrelated thing down with it.

Checked against the real `depends_on` graph in `docker-compose.yml` and the
actual code in each service (`vinu-strategy`, `vinu-live`, `vinu-portfolio`
read directly this session), only 3 of today's 10 services hold up against
this test. The rest cluster into one group.

## The four groups

### Group 1 -- Quant core (6 services today -> 1 component)

`vinu-news` (8080), `vinu-stock-price` (8081), `vinu-tools` (8082),
`vinu-initial-analysis` (8083), `vinu-strategy` (8084), `vinu-simulator`
(8085).

None of these hold secrets, none move money, all are deterministic compute
on data. Their only real internal difference is "ingest worker" (news,
stock price) vs. "on-demand compute" (features, angles, strategy
evaluation, backtesting) -- that's a **process** split (a worker process +
an API process from the same codebase), not a **component** split.

This is the same pattern already decided and in motion for one piece of the
system: `New-talk-agents/implementation/13-vinu-research-in-process-migration.md`
commits `vinu-research`'s real HTTP call sites to in-process imports, retiring
its standalone server once done. **Done, 2026-08-11 (second pass).** All 26
real `vinu-agent` runtime call-site files now try the in-process path first
(`broker/research_link.py`'s shared getters/serializers -- `get_strategy_store`,
`get_hypothesis_registry`, `get_research_storage`, `get_research_service`,
`get_research_tools`, plus matching serializers so an in-process caller and
an HTTP caller of the same data get identical dicts), falling back to HTTP
only if that raises -- same transport-agnostic contract
`trade_plan_calibration.py` established first. `vinu-portfolio`'s own,
separately-discovered 3 call sites (`_list_llm_strategies`,
`_fetch_outcome_confidence`, `_fetch_trade_plan` in
`vinu_portfolio/service.py`) got the identical treatment via a new
`vinu_portfolio/research_link.py`. Every migrated file has its own tests
proving the in-process path against a real tempfile-backed store (no
mocking the storage layer) AND the HTTP fallback path forced by patching
the relevant `research_link` getter to raise -- 772 vinu-agent tests, 116
vinu-portfolio tests, 610 vinu-research tests, all passing, no regressions.

**Real deployment-blocking bug found and fixed along the way**: neither
`vinu-agent/Dockerfile` nor `vinu-portfolio/Dockerfile` actually installed
`vinu-research` (or its own transitive deps -- `vinu-stock-price`,
`vinu-tools`, `vinu-simulator`) into the built image -- only `vinu-infra`
and the service's own package. Every in-process `import vinu_research...`
this migration adds (and the 2 safety-critical ones from the first pass --
`order_guard.py`'s active-artifact check, `debrief.py`'s evidence
write-back) would have raised `ImportError` in the real deployed
container, not in dev/test (where all packages are editable-installed in
one shared environment) -- and because most call sites catch broadly and
fail open or silently fall to an equally-broken HTTP path, this would have
shipped as a silent safety-check no-op, not a visible failure. Both
Dockerfiles now install the same dependency chain vinu-research's own
Dockerfile already does, in the same order.

`vinu-research`'s FastAPI server is still running today (nothing retired
it), but every real caller this session could find now has a working
in-process path with HTTP as a safety net, not the only path -- the
precondition the original migration doc set for eventually retiring the
standalone server is met for the parts of the system audited this
session. Group 1 is the same "one codebase instead of a network hop"
idea applied to the rest of the compute-only cluster instead of just this
one dependency.

**Re-verified 2026-08-11 -- this "one consumer" claim is wrong.**
`vinu-agent` calls vinu-news's HTTP API directly at three real call sites
(`tools/news_tool.py`, `tools/trade_plan_tool.py`, `memory/sync_service.py`),
independent of `vinu-initial-analysis`, and `docker-compose.yml`'s
`agent-api` service has its own `depends_on: news-api`. Folding vinu-news
in-process into `vinu-initial-analysis` would leave those three
vinu-agent call sites pointing at a service that no longer exists,
unless they're also migrated (to call `vinu-initial-analysis` instead,
or a thin HTTP facade is kept for them) -- not a clean, isolated fold.

vinu-news also runs **two** independent background processes today, not
one, and the split is deliberate: `vinu-news-ingest --continuous` (RSS +
per-ticker polling, ~600s cycle) and `vinu-news-finbert` (an independent
60s sentiment-scoring sweep) are separate OS processes specifically so
an hours-long LLM-analysis backlog in the ingest process never blocks
FinBERT scoring (`cli.py`'s own docstring states this explicitly).
Collapsing this into one process needs to preserve that decoupling
(e.g. separate threads/asyncio tasks per loop), not just merge the code.

**Re-verified 2026-08-11 -- the "none differ in resource profile" premise
is also false for 2 of the 6 services.** `vinu-strategy` and
`vinu-simulator` run no background worker at all (confirmed via their
`docker-compose.yml` `command:` overrides and the absence of any
`entrypoint.sh`) -- pure request/response APIs, idle when not queried.
The other four (`vinu-news`, `vinu-stock-price`, `vinu-tools`,
`vinu-initial-analysis`) each run a continuous background ingest/compute
loop alongside their API. `vinu-strategy`/`vinu-simulator` are the
actual lowest-risk fold candidates in this group -- no ingest-worker
blocking-isolation concern, no fan-out consumer surprise like vinu-news's.

### Group 2 -- Research / orchestration brain (2 services today -> 1 component)

`vinu-agent` (8086), `vinu-research` (8087).

Kept separate from Group 1 for reason (1) above: LLM calls are bursty,
slow, and expensive in a way steady feature computation isn't. This is
also where the whole agentic pipeline in `mermaid-explanation.md` lives --
Planner, Researcher/Executor, Thesis Intake, risk_gatekeeper,
capital_allocator.

**Two redundant-build findings from this session fold in here, not into
new code -- both now RESOLVED, re-verified 2026-08-11:**
- The doc's proposed **Live+Shadow** role is built as `vinu-live/
  shadow_evaluator.py`'s `ShadowEvaluator`. ~~It's currently broken --
  it calls `/agent/broker/performance/{artifact_id}` on vinu-agent, a
  route that was never implemented (404s today).~~ **Closed.** The
  route is real and implemented (`routes_broker.py`, mounted at
  `/agent/broker/performance/{artifact_id}` exactly as `ShadowEvaluator`
  calls it). A separate, more serious bug (both response-parsing call
  sites used `await resp.json()` against a sync method, silently
  swallowed, always returning empty) was found and fixed in the same
  session (`phase-4-live-shadow-fix/04-implement-test.md`), and the
  evaluator is now actually scheduled -- `vinu-live/entrypoint.sh` runs
  `vinu-live shadow-worker &` (`phase-9-scheduler-wiring`). This
  document's "currently broken" framing was written before those fixes
  landed and was never updated afterward -- nothing left to build here.
- The doc's proposed **Monitor** role is built as `vinu-live/trade_plan/
  orchestrator.py`'s `TradePlanOrchestrator` -- entry, invalidation-exit,
  contingency, rebalance-request gating (declines if profitable or
  kill-switched), and an event-driven shock-angle trigger are all
  present and confirmed running (`entrypoint.sh` starts
  `trade-plan-worker`). Outcome write-back into `HypothesisRegistry`/
  `TickerLedger` happens in the adjacent `feedback_loop.py` worker, same
  book, same cycle boundary. **One real piece is still genuinely
  missing**, not build-vs-duplicate: the Monitor spec's "batch and
  prioritize by decay/volatility, not poll every position identically"
  efficiency addition. `_evaluate_open_position` still makes individual,
  un-batched calibration/correlation calls per symbol per cycle
  regardless of signal strength. Real, but a performance optimization,
  not a correctness gap -- no prioritization heuristic has been decided,
  and inventing one now would be the same kind of ungrounded number this
  project's discipline avoids elsewhere. Left as a known follow-up.
- `capital_allocator`'s allocation math -- confirmed reused, not
  provisional: `allocation_tool.py`'s `POST /portfolio/evaluate-batch`
  call is a direct passthrough to `PortfolioService.build_portfolio()` →
  `allocate_risk_parity()`, the real inverse-vol/correlation-aware
  engine. Nothing to build here.
- `risk_gatekeeper`'s exposure check against `compute_risk_budget` --
  **this one is a genuine, still-open gap, not already resolved.**
  `exposure_reviewer` (its prompt, not code) decides its own hardcoded
  "no symbol above ~20% of portfolio_value" rule against raw broker data
  (`portfolio_tool.py` → live Alpaca `get_account()`/`get_positions()`),
  with zero vinu-portfolio involvement. `compute_risk_budget` has no
  callers anywhere in vinu-agent today. It's also not a drop-in
  replacement even once wired up -- `compute_risk_budget`'s signature is
  a daily drawdown/halt budget (per-symbol day-loss thresholds), a
  different concept from a per-symbol concentration cap. Built 2026-08-11
  -- see the implementation record this produced.

`vinu-strategy` (in Group 1) was checked for overlap with this group too --
none found. It's a deterministic, hand-authored YAML rule engine
(crossover/mean-reversion configs -> weight pipeline), a different paradigm
from the LLM-hypothesis loop. Nothing to fold between them.

### Group 3 -- Portfolio watchdog (1 service today -> stays alone)

`vinu-portfolio` (8090).

Non-negotiable, reason (2): `circuit_breakers.py`'s `PortfolioDrawdownMonitor`
+ `drawdown_scheduler.py` halt trading via `agent-api`'s `/broker/halt` on
a drawdown breach. If this lived inside Group 2's component, it would die
exactly when Group 2 (the brain) is hung, looping, or wedged on a bad LLM
call -- precisely the moment the halt is needed most.

### Group 4 -- Live execution (1 service today -> stays alone)

`vinu-live` (8091).

Non-negotiable, reason (3): real broker credentials, real order placement
(`breaker/engine.py`'s multi-check circuit breaker, TWAP/VWAP slicing,
book reconciliation against the broker). Keeping it isolated from Group
2's much larger, much chattier tool-surface is a deliberate blast-radius
fence -- an LLM prompt-injection or tool-use bug in Group 2 should never
have a direct path to money-moving code. This is the group to defend
hardest against merging, regardless of container-count pressure.

## Net effect

10 containers -> 4 components. Almost the entire reduction is Group 1
(6 -> 1) -- the split that doesn't map to any of the four real reasons.
Groups 2/3/4 staying separate isn't leftover complexity; each is paying for
something specific (resource profile, watchdog independence, credential
isolation).

Even inside Group 1, ingest workers (news, stock price) would likely still
run as separate *processes* from the API, for restart-independence -- the
actual win isn't "fewer running processes," it's one codebase, one deploy
artifact, one version to keep in sync, instead of six.

## Suggested order, if this gets picked up -- status as of 2026-08-11

1. Finish the already-in-motion `vinu-research` -> in-process migration
   (Group 2 half). **Done, 2026-08-11 (second pass)** -- all 26
   `vinu-agent` call-site files plus the separately-discovered
   `vinu-portfolio` dependency (3 call sites) are migrated, each with its
   own tests, plus a real deployment-blocking Dockerfile bug (neither
   image actually installed `vinu-research`) found and fixed along the
   way. Nothing left to build here.
2. ~~Fix `ShadowEvaluator`'s broken endpoint and extend
   `TradePlanOrchestrator`~~ -- **done.** Both the endpoint and the real
   bug behind it (sync/async mismatch) were fixed and the worker is
   scheduled, all earlier this session. Only the decay/volatility
   batching efficiency addition remains, and it's optional, not
   blocking.
3. Wire `risk_gatekeeper` to a real `vinu-portfolio` concentration check.
   **Built 2026-08-11** (`capital_allocator` was already wired --
   confirmed, not assumed). `risk_gatekeeper`'s exposure_reviewer now
   has a real `/portfolio/state`-derived symbol-concentration figure to
   reason with (see this build's own implementation record), replacing
   its previously self-contained, broker-only concentration estimate --
   the specialist's own 20%-rule judgment call is preserved, but now
   informed by vinu-portfolio's live, correlation-aware view of the
   whole book, not just raw positions for one symbol.
4. Investigate `vinu-news`'s ingest-worker internals -- **done, and the
   answer is more cautious than the doc's original framing.** `vinu-news`
   has two real consumers (`vinu-initial-analysis` AND `vinu-agent`, three
   separate call sites), not one, and its two background processes
   (ingest, FinBERT) are deliberately split to avoid one blocking the
   other. Folding it in-process is still possible but is no longer the
   "cleanest first candidate" -- it needs vinu-agent's 3 call sites
   re-routed or fronted by a thin facade, and the process-blocking
   isolation preserved as separate threads/tasks, not a straight code
   merge.
5. Fold the rest of Group 1, starting with the lowest-risk pair.
   **`vinu-strategy` + `vinu-simulator` code-merged 2026-08-11** -- one
   process now serves both (`vinu_strategy/server/merged_app.py`,
   `vinu-quant-core/Dockerfile`, `vinu-strategy serve-merged` CLI
   command), `docker-compose.yml`'s `strategy-api`/`simulator-api`
   replaced by one `quant-core-api` service with a merged `depends_on`
   graph, and `.env`/`.env-example`/`run_pipeline.py` updated so every
   consumer (`vinu-portfolio`, `vinu-research`, `vinu-agent`) points at
   the shared host:port -- their real paths (`/strategy/*`,
   `/simulator/*`) are unchanged, so none of those consumers' own code
   needed touching. Proven with `TestClient` against the real merged
   ASGI app (both real route sets respond under their real prefixes, no
   collision, no path leaks) plus the full `vinu-strategy`
   (68 passed + 2 pre-existing unrelated `test_allocation.py` failures,
   confirmed present before this work too) and `vinu-simulator`
   (129 passed) suites, unaffected.

   **Not done, and the honest reason why**: an actual `docker build` +
   `docker compose up` smoke test of the merged image. That's the one
   part of "production grade, ready to deploy" this pass could not
   verify -- there is no Docker available in this session's environment,
   and unlike the Python-only migration in item 1, this specific risk
   (does the merged image actually build and boot, do the real bind
   mounts/health checks/`depends_on` ordering work end to end) can only
   be checked by actually building and running it. Do that before
   trusting this fold in a real deployment.

   `vinu-stock-price`/`vinu-tools`/`vinu-initial-analysis` (each with
   their own ingest/compute worker) and `vinu-news` (two workers, real
   fan-out) remain, in roughly that order of increasing risk, once this
   fold is confirmed working with a real build.

## Honest scope note

Updated 2026-08-11 (second pass): item 1 (the `vinu-research` in-process
migration, across both `vinu-agent` and `vinu-portfolio`) is genuinely
done, tested, and includes a real Dockerfile fix that would otherwise
have shipped a silent safety-check regression. That was the one piece of
this plan that was pure application-code migration, reversible, and safe
to complete without touching `docker-compose.yml` or any running
container's topology -- exactly why it was tractable in one sitting where
the rest of this plan isn't.

`vinu-strategy`/`vinu-simulator` (the lowest-risk Group 1 pair) got the
same real treatment this session: code merged, config updated, tested
everywhere Python tests can reach -- but real infrastructure changes have
a layer unit tests can't cover, and this pass is explicit about not
having verified that layer (an actual container build/boot). That's the
honest line between "the code is right" and "this is safe to deploy,"
and it's why the rest of Group 1 (`vinu-stock-price`/`vinu-tools`/
`vinu-initial-analysis`/`vinu-news`, each with a real background worker
this pair didn't have) is real, multi-week infrastructure work that
should land service by service, each with its own tests, a real build
verification, and a staged rollout -- not something to declare "finished,
ready to deploy" without that verification. The corrections earlier in
this document are exactly why: several of this document's own premises
were stale or wrong until re-checked against real code, and the same
discipline (verify before trusting, one piece at a time) applies to
whatever comes next.
