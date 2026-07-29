# Roadmap — Phases A–F Implementation Plan

Companion to [status-1.md](./status-1.md). That document is the gap analysis; this is the
build plan. Every file/function reference below was verified against the actual code on
2026-07-20 (not the status doc's prose) — see the "Verified" notes inline. Each phase lists
concrete steps, the files they touch, and a definition of done.

---

## Phase A — Close the research loop

**Goal:** remove the two remaining human-in-the-loop requirements in vinu-research, and stop
wasting the feature/factor library that's already built.

### A1. Autonomous hypothesis generation
- **Problem:** `ResearchService.ensure_strategy(self, user_idea: str, ...)`
  (`vinu-research/vinu_research/service.py:203`) requires a human-supplied idea. Angle
  context (`ResearchTools.get_angle_context`, `tools.py:177`) is fetched and injected into
  prompts, but only ever as a *suffix* to an existing idea — see
  `_build_generation_prompt` (`llm_generator.py:130`) and `_build_refinement_prompt`
  (`llm_generator.py:154`), both of which take `user_idea` as a mandatory first argument.
- **Change:**
  1. Add `propose_idea_from_angles(angles: AngleContext) -> str` in `llm_generator.py`,
     an LLM call whose prompt is built from `format_angle_context_lines(angles)` alone
     (reuse the existing angle formatter, no new client needed).
  2. Make `ensure_strategy`'s `user_idea` optional (`user_idea: str | None = None`); when
     `None`, call `get_angle_context` first (already done at `loop.py:174`), then
     `propose_idea_from_angles`, then proceed as today.
  3. Same optionality on the HTTP route (`routes_read.py:58`, `RunResearchRequest.user_idea`)
     and CLI (`cli.py:154`, make the `idea` positional arg optional with `nargs="?"`).
- **Files:** `vinu_research/service.py`, `vinu_research/llm_generator.py`,
  `vinu_research/server/routes_read.py`, `vinu_research/cli.py`.
- **Done when:** `vinu-research ensure <symbol>` with no idea argument produces a strategy,
  end to end, sourced only from that symbol's angle context.

### A2. Decay → re-research auto-trigger
- **Problem:** `transition_status` (`decay.py:170`) correctly moves artifacts to `DECAYED`,
  but nothing downstream calls `ensure_strategy` again. Also note: `schedule-decay`
  (`cli.py:144`, `schedule_decay_main` at 448) is a **CLI-only polling loop**, not a running
  part of the `research-api` process — there is no FastAPI lifespan/background-task hook in
  `server/app.py:10` today.
- **Change:**
  1. In `_run_decay_scan` (`cli.py:368`), after a status transition lands on `DECAYED`, call
     `ensure_strategy(user_idea=None, symbol=...)` (depends on A1) for that symbol.
  2. Move the scan loop from CLI-only into the service process so it runs unattended in the
     container: follow the `while True: cycle(); time.sleep(interval)` idiom already used by
     `vinu-news`'s `--continuous` (`vinu_news/cli.py:107`) and `vinu-stock-price`'s
     `--continuous` (`vinu_stock/cli.py:108`) — both run as their **own container** in
     `docker-compose.yml`, not inside the FastAPI process. Add a new `research-decay-scan`
     compose service (same pattern as `news-ingest`/`stock-ingest`: no published port,
     `depends_on: research-api`) running `vinu-research schedule-decay` continuously, rather
     than inventing an in-process scheduler.
- **Files:** `vinu_research/cli.py`, `vinu-components/docker-compose.yml` (new service block).
- **Done when:** an artifact manually forced into `DECAYED` triggers a fresh `ensure_strategy`
  run within one scan interval, with zero human action.

### A3. Wire the vinu-tools feature/factor library into generation
- **Problem:** `ResearchTools._features_client` (`tools.py:23`) is constructed but never
  called anywhere in `tools.py`, `loop.py`, `llm_generator.py`, or `generator.py` — confirmed
  dead. The LLM generator and template recipes only ever see 3 hardcoded indicators plus
  angle context; the Alpha101/Alpha191/ML pipeline in `vinu-tools` (`features-api`, :8082)
  never reaches strategy authoring.
- **Change:**
  1. Add a method on `ResearchTools`, e.g. `get_feature_snapshot(symbol, recipe="alpha158")`,
     calling the existing `features-api` client (`self._features_client`) against its
     `/features/{symbol}` or recipe-compute endpoint (mirror how `vinu-strategy` already
     calls the same API: `GET /features/{symbol}` per `strategy-api`'s `WeightPipeline`
     integration, `status-1.md` §1.3).
  2. Thread the result into `loop.py` alongside `self._angle_context` (`loop.py:174-175`),
     append it to both `_build_generation_prompt` and `_build_refinement_prompt` the same
     way angle lines are appended today (`llm_generator.py:148-150`, `200-202`).
  3. For the template-recipe path (non-LLM), pass the feature snapshot into whichever recipe
     functions currently only see raw OHLCV — audit `generator.py`'s template branch for the
     exact injection point during implementation (not fully explored this pass).
- **Files:** `vinu_research/tools.py`, `vinu_research/loop.py`, `vinu_research/llm_generator.py`,
  `vinu_research/generator.py`.
- **Done when:** a generated/refined strategy's prompt log shows Alpha101/191 or ML-pipeline
  features, not just the 3 hardcoded indicators.

---

## Phase B — Bridge + portfolio layer

**Goal:** the two independent weight-producing mechanisms (vinu-strategy YAML,
vinu-research LLM-Python) become inputs to one portfolio decision, with real risk logic
instead of none.

### B0. Fix the correlation URL env mismatch first
- **Verified bug**, independent of everything else: `docker-compose.yml:277` sets
  `VINU_INITIAL_ANALYSIS_API_URL` for `strategy-api`, but `vinu_strategy/config.py:60` reads
  `VINU_CORRELATION_API_URL`. Since the compose block never sets that key, `strategy-api`
  falls back to `DEFAULT_CORRELATION_API_URL = http://127.0.0.1:8083` (`config.py:14`), which
  inside the container resolves to itself, not `initial-analysis-api`. `research-api`'s
  compose block (`docker-compose.yml:350`) already uses the correct key — copy that.
- **Fix:** change `docker-compose.yml:277` key from `VINU_INITIAL_ANALYSIS_API_URL` to
  `VINU_CORRELATION_API_URL`. One-line change, do this before anything else in Phase B so the
  correlation calls a new portfolio service depends on aren't silently broken.

### B1. Cross-mechanism strategy inventory
- **Problem:** `StrategyRegistry.load_all()` (`vinu_strategy/engine/registry.py:19`) only
  globs YAML files — it has no knowledge of `vinu-research`'s `Artifact`/`ArtifactStatus`
  objects (`vinu_research/models.py:56`, stored via `SqliteStrategyStore`,
  `vinu_research/storage/strategy_store.py`). There is currently no single call that lists
  "all ACTIVE strategies" across both packages.
- **Change:** build a small aggregation client (new module, e.g.
  `vinu_agent/tools/portfolio_inventory.py` or a new service — see B2 below) that:
  1. Calls `strategy-api`'s existing list endpoint for YAML strategies
     (`StrategyService.list_strategies()`, `vinu_strategy/service.py:38`).
  2. Calls a new/extended `research-api` endpoint that lists all `ACTIVE` artifacts across
     symbols (check `strategy_store.py` for an existing repo-wide query first — the explore
     pass found only a per-symbol query at `service.py:195-201`; a `list_all(status=ACTIVE)`
     method likely needs to be added to `SqliteStrategyStore`).
  3. Returns a unified `[{name, kind: "yaml"|"llm_python", symbol, weights_source}, ...]` list.
- **Files:** `vinu_research/storage/strategy_store.py` (new query method),
  `vinu_research/server/routes_read.py` (new list-active-artifacts route), new aggregation
  module (location TBD — see B2 for where it should live).

### B2. Portfolio construction service
- **Decision needed before implementation:** should this be a new package
  (`vinu-portfolio`, its own compose service/port) or a new module inside an existing
  package? Given every other pipeline stage in this repo is its own service with its own
  port (`status-1.md` §1.1 diagram — 12 services, one per concern), and this needs to sit
  *between* strategy/research output and the simulator/broker, treat it as a new package
  following the same convention as the other 12: `Dockerfile`, `.env.example`,
  `docker-compose.yml` block (loopback-bound port, `restart: unless-stopped`,
  `cap_drop: [ALL]` etc. — copy the `research-api` block verbatim as a template).
- **Responsibilities:**
  1. Pull the B1 inventory of ACTIVE strategies.
  2. For each, pull historical weights/returns — YAML strategies from vinu-strategy's
     Parquet output (`data/weights/{strategy}/{yyyy}/{mm}/{dd}.parquet`, per §1.3), LLM
     strategies from vinu-simulator's `SimulationResult.portfolio_values`/`daily_returns`
     (`vinu_simulator/models/simulation.py:63` — **note:** the status doc calls this
     `BacktestResult`; the actual dataclass is `SimulationResult`, verified, no
     `BacktestResult` class exists anywhere in vinu-simulator).
  3. Compute a correlation matrix across strategies (new logic — nothing in the repo does
     this at the strategy level today; `vinu-initial-analysis`'s `/correlation` endpoint is
     per-ticker, not per-strategy, and is a different computation).
  4. Allocate capital/risk budget per strategy: start with risk-parity (inverse-vol
     weighting) as the simplest correct baseline before Sharpe-weighting; cap max-per-strategy
     and max-per-sector.
  5. Emit target portfolio weights (aggregate, post-allocation) via its own HTTP endpoint,
     analogous to `strategy-api`'s `/weights`.
- **Files:** new package `vinu-components/vinu-portfolio/`.

### B3. Position sizing as code
- **Problem:** `execution-model` is currently only an LLM prompt-injection skill
  (`vinu_agent/skills/`, per §1.4) — no executable vol-targeting or fractional-Kelly logic
  exists anywhere.
- **Change:** implement vol-targeting sizing (`target_position = risk_budget / realized_vol`)
  as a pure function inside the new portfolio service (B2), called after the correlation/
  allocation step, before final weights are emitted. Keep it simple — vol-targeting first,
  Kelly is a stretch addition, not a blocker.
- **Files:** `vinu-portfolio/` (new module, e.g. `sizing.py`).

### B4. Portfolio-level circuit breakers
- **Problem:** the only kill switch today is
  `vinu_agent/broker/kill_switch.py:14` (`/tmp/vinu-trading-halt`), a single global flag with
  no drawdown trigger, checked first in `OrderGuard.check()` (`order_guard.py:59`).
- **Change:** add a drawdown monitor in the portfolio service (B2) that computes running
  portfolio-level drawdown from the aggregate weights/returns it already has, and — when
  breached — writes the same kill-switch sentinel file `OrderGuard` already checks (reuse
  the existing mechanism, don't invent a second one). Also flagged during exploration:
  `TradingMandate.max_position_pct` and `max_daily_trade_volume`
  (`vinu_agent/broker/mandate.py:18`) are defined but **never enforced** in
  `OrderGuard.check()` (`order_guard.py:51-87`, only `max_order_value`, `max_daily_orders`,
  `blocked_tickers`, `allowed_tickers`, `allow_short` are actually checked) — fix this gap in
  the same pass since it's a one-file change adjacent to the circuit-breaker work.
- **Files:** `vinu-portfolio/` (new drawdown monitor), `vinu_agent/broker/order_guard.py`
  (enforce the two currently-dead mandate fields).

---

## Phase C — vinu-live (execution engine)

**Goal:** the one piece that makes trading autonomous rather than chat-triggered.

### C1. Signal → order translation
- **New logic, nothing to reuse directly.** Needs to: fetch current broker positions (via
  `AlpacaBroker`, `vinu_agent/broker/alpaca.py:108`), diff against the portfolio service's
  (B2) target weights, size the delta in dollars/shares, and submit through the existing
  `OrderGuard`/`TradeTool` path (`vinu_agent/tools/trade_tool.py:44`) rather than calling
  `AlpacaBroker.submit_order` (`alpaca.py:151`) directly — this preserves the mandate/kill-
  switch checks for free.
- **Files:** new package `vinu-components/vinu-live/`, importing `vinu_agent`'s broker module
  as a dependency (check current inter-package import conventions — other packages call each
  other over HTTP, not via direct Python import; if that convention holds, `vinu-live` should
  call `agent-api`'s trade tool over HTTP instead of importing `vinu_agent` directly — decide
  this during implementation, don't assume).

### C2. Execution algorithms (TWAP/VWAP/slippage-aware slicing)
- **Problem:** `execution-model` skill documents Almgren-Chriss slippage and TWAP/VWAP
  slicing as text for the LLM to reason about, but `AlpacaBroker.submit_order`
  (`alpaca.py:151`) places a single naive order — no slicing code exists.
- **Change:** implement the slicing logic as real code in `vinu-live`, informed by (but not
  dependent on) the skill's documented models — treat the skill file as a spec to translate,
  not a runtime dependency.
- **Files:** `vinu-live/` (new module, e.g. `execution.py`).

### C3. Scheduling — the actual "autonomous" part
- **Pattern to copy, verified:** the repo's existing continuous-operation convention is a
  plain `while True: cycle(); time.sleep(interval)` loop running as its **own container**,
  not inside a FastAPI process — see `vinu_news/cli.py:107` and
  `vinu_stock/cli.py:108-114`, both wired into `docker-compose.yml` as dedicated worker
  services with no published port and a `depends_on` on their upstream API. Do **not** copy
  `vinu_strategy`'s `schedule_main` (`vinu_strategy/cli.py:78`) — it's CLI-only and not
  containerized today, which is exactly the gap Phase A2 also has to fix for decay-scanning.
- **Change:** `vinu-live` ships as two things: an API (for status/manual triggers, following
  every other package's `<pkg>-api` convention) and a worker process running the C1→C2 cycle
  on an interval, added to `docker-compose.yml` as its 13th/14th service. Copy the
  `research-api` compose block as the API template and `stock-ingest`'s worker block
  (no ports, `depends_on`) as the scheduler template. Note: `agent-api`'s compose block is
  missing `env_file:` (only inline `environment:`) — an inconsistency with every other
  service; don't repeat it in the new blocks.

### C4. Reconciliation
- **New logic, nothing to reuse.** After each C1→C2 cycle, compare `AlpacaBroker`-reported
  positions/fills against the portfolio service's expected state; alert on drift (wire into
  whatever notification path Phase E delivers — see below, don't build a second one).
- **Files:** `vinu-live/` (new module, e.g. `reconciliation.py`).

---

## Phase D — Validation gate before real capital

### D1. Automate the shadow-account methodology
- **Problem:** `shadow-account` (per §1.4) is currently a `vinu_agent/skills/` prompt pack —
  documents the right methodology (extract trades → simulate what-if → compare P&L) but
  isn't a running pipeline.
- **Change:** implement as a scheduled job (same worker-container pattern as C3) that, for
  each artifact in `BENCHING` (`ArtifactStatus`, `vinu_research/models.py:56`), pulls N days
  of paper P&L from the broker (C4's reconciliation data) and compares against the backtest's
  `SimulationResult.metrics` (`vinu_simulator/models/simulation.py:63`). If within tolerance,
  transition `BENCHING → ACTIVE` — extend `transition_status`
  (`vinu_research/decay.py:170`) with this new inbound transition (today it only has outbound
  transitions from `ACTIVE`).
- **Files:** `vinu_research/decay.py` (new transition), new scheduled job (package location
  TBD — likely `vinu-live` since it's the piece with broker/paper-P&L visibility).

### D2. Feed live/paper P&L into decay detection
- **Change:** `transition_status`'s decay evaluation currently only looks at re-backtested
  historical data (per `decay.py:170`'s surrounding scan logic — not fully explored this
  pass, audit during implementation). Add live/paper P&L as an additional input signal
  alongside the existing backtest-based evaluation.
- **Files:** `vinu_research/decay.py`.

---

## Phase E — Human oversight made usable

### E1. Wire Telegram/Discord
- **Problem, verified:** `BaseChannel` subclasses (`vinu_agent/channels/base.py:5`,
  `telegram.py:16`, `discord.py:16`) exist and are real implementations, but
  `server/app.py`'s `create_app()`/`_lifespan` (lines 8-34) never imports or starts them, and
  `cli.py:161`'s `channel send` hard-codes `{"status": "not_implemented", ...}`.
- **Change:** start the configured channel bot(s) in `server/app.py`'s `_lifespan` context
  manager (the same place event-bus wiring already happens, lines 27-33) rather than the CLI
  path. Wire `TradeTool`'s `pending_confirmation` response
  (`vinu_agent/tools/trade_tool.py:74-87`) to actually send via the started channel instead of
  only returning to the calling chat session.
- **Files:** `vinu_agent/server/app.py`, `vinu_agent/cli.py` (remove the
  `not_implemented` stub once wired), `vinu_agent/tools/trade_tool.py`.

### E2. Kill switch granularity + audit log
- **Problem:** `kill_switch.py:14` is a single global sentinel file — no per-strategy or
  per-symbol granularity.
- **Change:** extend `is_trading_halted()`/`halt_trading()` (`kill_switch.py:17-29`) to accept
  an optional scope (`strategy_name` or `symbol`), storing per-scope sentinel files or a small
  JSON state file instead of a single flag; `OrderGuard.check()` (`order_guard.py:59`) already
  calls this first, so the check-site doesn't need to change, only what it checks. Add
  structured audit logging of every order/confirmation/override — log at the same point
  `TradeTool.execute()` (`trade_tool.py:44`) makes its decision.
- **Files:** `vinu_agent/broker/kill_switch.py`, `vinu_agent/broker/order_guard.py`,
  `vinu_agent/tools/trade_tool.py`.

---

## Phase F — Observability

### F1. Live-vs-backtest dashboard
- **Depends on:** C4 (reconciliation data) and D1 (shadow P&L comparisons) already producing
  the comparison data — this phase is presentation, not new computation. Reuse
  `vinu_simulator`'s `SimulationResult.metrics` as the backtest-side baseline and the
  portfolio service's (B2) live aggregate weights/P&L as the live side.
- **Options:** an `agent-api` tool (simplest — the swarm/chat surface already exists,
  `vinu_agent/server/routes_swarm.py` shows the pattern for adding new routes) vs. a standalone
  dashboard. Given every other capability in this repo is exposed as an agent tool first,
  default to that unless the user wants a persistent visual dashboard.
- **Files:** TBD — depends on the option chosen above; defer detailed design until Phases
  B–D are further along, since this phase has nothing to observe until they exist.

---

## Suggested execution order

Phase A is small and self-contained — do it first for momentum and because A3's feature
wiring makes Phase B's strategies richer before portfolio logic is built on top of them.
**B0 (the one-line env var fix) should land before any other Phase B work**, since it's an
independent bug that would otherwise silently break the new portfolio service's correlation
calls. Phases B and C are correctly identified in the status doc as the largest lift and the
real definition of "self-reliant with portfolio management" — B (portfolio construction) is a
prerequisite for C (execution needs something to execute against). D and E can proceed in
parallel with late-stage C work once C1's signal→order translation exists. F is last by
construction — it has nothing to display until B/C/D produce real data.

## Open decisions to make before implementation starts
1. **B2/C1/C3 package boundaries** — new standalone packages (`vinu-portfolio`, `vinu-live`)
   following the existing one-package-per-concern convention, vs. folding portfolio logic
   into `vinu-strategy` and execution into `vinu-agent`. The existing repo convention (12
   services, each a clear single concern with its own port) argues for new packages, but this
   is a real cost/complexity tradeoff worth confirming before scaffolding new services.
2. **Inter-package calls in `vinu-live`** — HTTP calls to `agent-api` (matching how every
   other package talks to every other package today) vs. direct Python import of
   `vinu_agent.broker`. HTTP keeps the pattern consistent; import would be faster to build but
   inconsistent with the rest of the repo.
