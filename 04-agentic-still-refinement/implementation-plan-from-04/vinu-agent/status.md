# vinu-agent — Status

**Status: all five pieces implemented.** Full detail in [`plan.md`](plan.md).

## Files touched

**Piece 1 — Facts & Limitations Registry:**
- `vinu_agent/facts/registry.py` (new) — `Fact` dataclass + `FactsRegistry(SQLiteBackend)`: `add_fact`, `supersede`, `count_active`, `active_facts_for(symbols, signals)`.
- `vinu_agent/facts/seed.py` (new) — `SEED_FACTS` (direction-prediction negative result, JNJ fabrication, 16/20-day silent-agent bug) + `seed_if_empty`, idempotent by row count.
- `vinu_agent/facts/__init__.py` (new) — exports `Fact`, `FactsRegistry`, `SEED_FACTS`, `seed_if_empty`.
- `vinu_agent/broker/kill_switch.py` — added `AuditLogger.FACT_REGISTRY_WRITE` action constant; `FactsRegistry.add_fact` logs through it.
- `vinu_agent/agent/context.py` — `ContextBuilder` gained `facts_registry` param, `_last_facts_msg`/`last_facts_msg`, `is_known_constraints_msg()`; `build_messages()` injects a `<known-constraints>` block (same seam as `GroundTruthInjector`) filtered by held symbols + `_extract_symbols(user_message)`.
- `vinu_agent/agent/loop.py` — `AgentLoop._facts_system_msg` added and preserved across `_auto_compact()`, mirroring `_ground_truth_system_msg`.
- `vinu_agent/session/service.py` — `SessionService` takes `facts_registry`, passes it into `ContextBuilder`, sets `agent_loop._facts_system_msg`.
- `vinu_agent/service.py` — `AgentService` constructs `FactsRegistry(data_root / "facts_registry.db")`, calls `seed_if_empty()` at startup, closes it in `close()`.
- `tests/test_facts_registry.py` (new, 7 tests) — invalid kind rejection, symbol-scoped/unscoped/signal-scoped matching, supersede, seed idempotency, seeded JNJ fact retrievable.
- `tests/test_integration_facts.py` (new, 5 tests) — the named acceptance test (seeded row reaches the injected block, not just the store), plus non-matching-symbol exclusion, held-symbol-without-mention, unscoped-always-included, no-registry-no-crash.

**Piece 2 — Debrief-on-close:**
- `vinu_agent/broker/debrief.py` (new) — `PositionCloseDetector`: diffs currently-held positions against a persisted last-seen snapshot (no fill-event webhook exists in this codebase; both brokers are polled on demand), fetches a fresh exit price via the `get_stock_price` tool for anything that dropped out, computes realized P&L against the entry snapshot, and writes it back as `Evidence` (`metric: realized_pnl`, `conclusion: supports|contradicts`) to any open (`testing`/`exploring`/`monitoring`) `HypothesisRegistry` thesis for that symbol via `POST /research/hypotheses/{id}/evidence`. Logs through `AuditLogger.JOURNAL_STATUS_CHANGED`.
- `vinu_agent/audit/ground_truth.py` — refactored broker construction out of `_get_held_symbols` into a reusable `_build_broker(as_of, session_id)` so the debrief detector and the ground-truth injector share one broker instance per turn.
- `vinu_agent/session/service.py` — `_run_with_agent` calls `PositionCloseDetector.check_and_debrief()` once per turn, best-effort (wrapped in try/except, never blocks the main flow), state persisted under `{VINU_AGENT_DATA_ROOT}/debrief_state/{session_id or "live"}.json`.
- `tests/test_debrief.py` (new, 6 tests) — no-prior-state snapshot, still-open no-op, closed-with-thesis writes evidence, closed-at-a-loss marks `contradicts`, closed-with-no-open-thesis reports P&L but doesn't write, exit-price-fetch-failure doesn't raise.
- **Known limitation, stated once**: `HypothesisRegistry`'s status lifecycle (`exploring/testing/validated/rejected/monitoring/mc_gate_failed`) has no literal "resolved" state, and only `POST .../evidence` is exposed over HTTP (no `reject_with_reason` route) — so a debrief write records the outcome as evidence but does not itself force a terminal status change. This is a real gap in the existing registry API, not something Piece 2 was scoped to fix; noted here so it isn't silently assumed solved.

**Piece 3 — Prospective fact-check:**
- `vinu_agent/tools/trade_plan_tool.py` — reordered `_execute_async` so the plan is rendered to markdown *before* the journal write, added `_prospective_fact_check()` (reuses `FactAuditor`, wraps the same fetched artifacts — angles/features/validation/liquidity/news — used to build the plan as pseudo tool-result messages) and `_render_fact_check_warning()`. A `Fail` verdict skips `_schedule_journal_write` and prepends a warning block instead of silently journaling an unverified number.
- `tests/test_prospective_fact_check.py` (new, 6 tests) — clean plan passes, **the named JNJ-reconstruction acceptance test** (a stated $162.45 with no matching fetched data is caught as `Fail`, real value $267.16 backed by fetched data passes), warning rendering, and two tests against the real `_execute_async` control flow confirming a blocking finding skips the journal write while a clean one still calls it.

**Bugs found and fixed while building Piece 2** (both are real, previously-undiscovered gaps in already-"shipped" items 2 and 3 — found because Piece 2 reused the same HTTP call pattern and it didn't work against the actual mounted routes):
1. `ground_truth.py`'s `_fetch_open_theses` called `GET {research_url}/hypotheses` and expected a bare list back. The route is actually mounted at `/research/hypotheses` (confirmed via `vinu_lib/server.py`'s `route_prefix="research"`, matching the already-correct `query_hypotheses_tool.py`) and returns `{"count": N, "hypotheses": [...]}`. Both the URL and the response-shape assumption were wrong — the "Active Trade Theses" ground-truth block has never actually populated in a real run. Fixed both; added `tests/test_ground_truth.py` (4 tests, previously zero coverage existed for this module).
2. `trade_plan_tool.py`'s `_write_trade_journal_async` POSTed to `{research_url}/hypotheses` instead of `/research/hypotheses` — every trade-plan journal write has been silently 404'ing (fire-and-forget, swallowed by a bare `except`). Item 3's decision-journal write-side never actually landed a row in a real run despite passing unit tests that never exercised the real URL. Fixed; added `tests/test_trade_journal_write.py` (1 test, regression-locks the corrected URL).

**Piece 4 — Freshness-warnings reader:**
- `vinu_agent/audit/freshness.py` (new) — `FreshnessChecker`: fetches `vinu-initial-analysis`'s existing `/analysis/angle/regime_analysis/{symbol}` route per symbol, reads the `analysis_at` already stamped on every row, flags a symbol `STALE` if the latest one is older than `STALE_AFTER_DAYS` (2.0). No changes needed on the `vinu-initial-analysis` side.
- `vinu_agent/agent/context.py` — `ContextBuilder` gained `freshness_checker` param, `_last_freshness_msg`/`last_freshness_msg`, `is_freshness_warnings_msg()`; injects a `<freshness-warnings>` block on the same seam as ground-truth/facts.
- `vinu_agent/agent/loop.py` — `AgentLoop._freshness_system_msg` preserved across `_auto_compact()`, same as the other two system-message blocks.
- `vinu_agent/session/service.py` — constructs a `FreshnessChecker` only when `as_of is None` (live mode; a wall-clock age comparison is meaningless in replay), passes it into `ContextBuilder`, sets `agent_loop._freshness_system_msg`.
- `tests/test_freshness.py` (new, 8 tests) — fresh passes, stale is flagged, uses the latest of multiple rows, no-rows/no-service-url/non-200/exception all skip cleanly, custom threshold respected.
- `tests/test_integration_freshness.py` (new, 5 tests) — the same reaches-the-actual-block acceptance pattern used for the Facts Registry: stale finding reaches the injected block, no findings means no block, no checker means no crash, no symbols-in-play skips the check entirely, a held symbol triggers the check even without an explicit mention.

## Test run

`python3 -m pytest` (system interpreter — `vinu-lib` is `pip install -e`'d system-wide, not resolvable by an isolated `uv run` venv) from `vinu-agent/`: **280 passed** (was 224 before this work; +56 new tests across Pieces 1-5 and the two bug-fix regression tests, 0 regressions at any step).

**Piece 5 — Research-digest reader:**
- `vinu_agent/audit/research_digest.py` (new) — `ResearchDigestReader`: fetches `GET /research/runs?symbol={s}&limit=1` per symbol in play, surfaces the run's `summary_text` only if its `id` hasn't already been shown for that symbol (persisted "seen" state file, same mechanic as `PositionCloseDetector`'s snapshot).
- `vinu_agent/agent/context.py` — `ContextBuilder` gained `research_digest_reader` param, `_last_research_digest_msg`/`last_research_digest_msg`, `is_recent_research_msg()`; injects a `<recent-research>` block on the same seam as the other three.
- `vinu_agent/agent/loop.py` — `AgentLoop._research_digest_system_msg` preserved across `_auto_compact()`.
- `vinu_agent/session/service.py` — constructs a `ResearchDigestReader` per turn (runs in both live and replay mode, unlike Piece 4 — no wall-clock dependency), passes it into `ContextBuilder`, sets `agent_loop._research_digest_system_msg`.
- `tests/test_research_digest.py` (new, 9 tests) — new run surfaces once, same run doesn't repeat, new run id surfaces again, empty summary skipped, no-runs/no-service-url/non-200/exception/no-symbols all skip cleanly.
- `tests/test_integration_research_digest.py` (new, 5 tests) — the same reaches-the-actual-block acceptance pattern used for Facts/Freshness.
- **Cross-component**: `vinu-research` gained the actual summary-generation and the fix for `ScheduledResearchExecutor.dispatch()` discarding `run_research()`'s return value — see `../vinu-research/status.md`.
