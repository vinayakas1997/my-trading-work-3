# Inconsistencies — recorded, not solved

Companion to `../vision-trding-system.md` (WHAT+WHY) and `../how-system-implemented.md`
(HOW+WHERE). Every item below was verified against `vinu-components/` code on 2026-09-30.
Format per item: title, explanation, evidence, where found, solution, what it will achieve,
how it will be used. Nothing here is acted on — this is the list to work through.

---

## GROUP A — Recorded but never decides (write-only / prompt-only data)

### A1. Signal-evidence indicators (regime, news_confound, MFE/MAE) computed but never read programmatically

- **Title:** Indicator payload recorded per trigger, skipped by every aggregate reader.
- **Explanation:** Each trigger stores a full indicator snapshot including `regime`,
  `news_confound{occurred,minutes_before,article_id}`, `volume_vs_avg20`, MFE/MAE. The
  aggregate paths (`track2_aggregate`, signal-evidence bridge, `list_unconfirmed_moves`) read
  metadata only (condition, times, `return_at_horizon`). No code anywhere does
  `indicators.get("regime")` or `["news_confound"]` outside the writer and tests.
- **Evidence:** `list_triggers` docstring explicitly performs no indicator join; grep for
  `indicators.get("regime")` / `["news_confound"]` / `volume_vs_avg20` returns zero outside
  `signal_evidence/compute.py` and tests; only single-trigger LLM read sees the blob.
- **Where found:**
  - Writer: `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/signal_evidence/compute.py:663-806` (`regime:804`, `news_confound:806`, `_news_confound:508`)
  - Store: `vinu-components/vinu-research/vinu_research/storage/signal_evidence_store.py:61-115` (`record_trigger`, `signal_evidence_indicators`), `:117-147` (`record_outcome` MFE/MAE), `:149-167` (`get_trigger`), `:169-171` (`list_triggers` no-join docstring), `:188-209` (`get_unresolved_triggers`, zero prod callers)
  - Skipping readers: `vinu-components/vinu-research/vinu_research/track2_aggregate.py:78`, `vinu-components/vinu-research/vinu_research/signal_evidence_bridge.py:97-105`, `vinu-components/vinu-research/vinu_research/track2_reconciliation.py:52`
  - HTTP: `vinu-components/vinu-research/vinu_research/server/routes_signal_evidence.py:56-91`
  - Tool: `vinu-components/vinu-agent/vinu_agent/tools/signal_evidence_tool.py:59-62`
- **Solution:** Extend `track2_aggregate.summarize` (via `vinu_infra/evidence_confidence.py`) to
  group by `(must_condition, regime)` and exclude/flag `news_confound.occurred`, using the already
  stored columns — no new table. Add one regression test: same condition in `bull` vs `bear`
  yields separate confidences.
- **What it will achieve:** Evidence-confidence becomes regime-aware and news-aware instead of one
  blended number; Track-1's two hardest-built fields finally affect a decision.
- **How it will be used:** `EvidenceConfidenceSizer` and `compute_track2_aggregate()` consumers;
  live-decision prompt cites "58% overall, 71% in bull ex-news" instead of one flat rate.
- **Touched (2026-09-30 fix):** `vinu-infra/evidence_confidence.py` (+`regime_of`,
  `is_news_confounded`, `summarize_by_regime`; `summarize_resolved_triggers` untouched),
  `vinu-research/.../storage/signal_evidence_store.py` (+`get_indicators_for_triggers` batch raw
  read, chunked 500, no schema change), `vinu-research/.../track2_aggregate.py` (+`by_regime`,
  `news_confounded_total` keys; all prior keys byte-identical in meaning).
- **Tests:** `vinu-infra/tests/test_evidence_confidence.py` +7 (regime mapping, confound shape,
  same-formula buckets, exact confound count, empty ex_news shape) — 14 passed;
  `vinu-research/tests/test_track2_aggregate.py` +4 (bull/bear split, confound flag+exclusion,
  unknown bucket, bucket↔overall reconciliation) — related files 50 passed;
  `vinu-simulator` sizing/confidence/evidence 65 passed (shared-module consumer unaffected).
- **Verified:** `GET /research/track2-aggregate/{symbol}` returns the extended shape (additive
  keys only); existing suites green, no regressions; `EvidenceConfidenceSizer` path untouched.
- **Bugs found / re-fixed:** none — first implementation passed all suites on first run.

### A2. MoveEvidenceStore logged unconditionally, never consumed

- **Title:** Every detected move persisted, no decision-maker reads unconfirmed moves.
- **Explanation:** Poller records each `detect_move()` (2×ATR floor) unconditionally per candle
  close per watched pair. `list_unconfirmed_moves()` (read-time join vs SignalEvidenceStore)
  exists but has no scheduled prod caller and no HTTP route wiring it to any consumer.
- **Evidence:** Only tests + manual GET reference `list_unconfirmed_moves`; store docstring admits
  everything looks `track2_only` until the signal-evidence writer gap closed (now closed, reader
  still unwired).
- **Where found:**
  - Store: `vinu-components/vinu-research/vinu_research/storage/move_evidence_store.py:52-92`
  - Writer: `vinu-components/vinu-live/vinu_live/live_decision/poller.py:157,431-440`
  - HTTP: `vinu-components/vinu-research/vinu_research/server/routes_signal_evidence.py:115-135`
  - Join: `vinu-components/vinu-research/vinu_research/track2_reconciliation.py:60-80`
- **Solution:** Expose `GET /research/unconfirmed-moves?symbol=` reusing the introspect file
  convention, and add it to `get_live_decision_context` output as `unconfirmed_moves[]`. No new
  table, no new scanner.
- **What it will achieve:** `track2_only` becomes a visible, queryable signal instead of a table
  nobody queries.
- **How it will be used:** Live-decision agent checks "did Track-2 see a move Track-1 missed"
  before EXECUTE; reflection `regime_drift` analyst cites it.
- **Touched (2026-09-30 fix):** `vinu-agent/.../tools/get_live_decision_context_tool.py`
  (+`unconfirmed_moves[]` from `GET /research/unconfirmed-moves?symbol=&limit=10`, fail-open to
  `[]`; module docstring 5th source; tool description documents the field). No route work needed
  — see Verified.
- **Tests:** `vinu-agent/tests/test_get_live_decision_context_tool.py` +2 (events included with
  `confirmed_by_track1: False`; fetch failure → `[]`, status stays ok) — file 9 passed; broader
  context/live_decision/signal_evidence selection 79 passed.
- **Verified:** Route half of the solution already existed and is mounted + tested:
  `GET /research/unconfirmed-moves` (`routes_signal_evidence.py:139-150`, prefix `research`,
  covered by `test_routes_signal_evidence.py:190-206`). Only the context-tool wiring was missing.
  Existing strict-URL mocks updated for the new fetch; no regressions.
- **Bugs found / re-fixed:** none — but scope shrank on evidence: half the item was already built,
  so the fix was one field, not a route + a field.

### A3. Sweep grid winner scores discarded; param_diff_from_winner not persisted

- **Title:** Sweep comparison table is human-introspection-only for automation purposes.
- **Explanation:** `sweep_grid_points` stores rank/score/risk/complexity per point, but the
  graveyard skips winners (`if p["succeeded"]: continue`) so winner scores never reach any reader,
  and `param_diff_from_winner` is computed live in `_serialize_grid` from in-memory results — not a
  column, so nothing can read it back later. No generator/ranker reads the store.
- **Evidence:** Graveyard code filters successes; grep shows no `loop.py`/agent read of
  `SweepGridStore` for ranking; diff function lives in `sweep_grid.py:358`, serialization in
  `routes_sweep.py:183`.
- **Where found:**
  - Store: `vinu-components/vinu-research/vinu_research/sweep_store.py:44-186`
  - Grid: `vinu-components/vinu-research/vinu_research/sweep_grid.py:245-315,358`
  - Routes: `vinu-components/vinu-research/vinu_research/server/routes_sweep.py:183-244`
  - Graveyard: `vinu-components/vinu-research/vinu_research/candidate_graveyard.py:81-97`
- **Solution:** Persist `param_diff_from_winner` JSON on each loser row at `record_sweep()` time
  (pure function already exists), and include winner rows in graveyard with `source=sweep_winner`.
  Migration: nullable column, backfill null = unknown.
- **What it will achieve:** "Why did this lose, and how far from the winner" becomes queryable
  history, not a live-only response field.
- **How it will be used:** Generation dedup ("we already tried MA(5,50)±X, winner was (5,50) by
  Sharpe 0.3") and reflection decay analysis.

### A4. Generation code_hash written, indexed, never queried

- **Title:** Candidate identity infrastructure with zero production readers.
- **Explanation:** Every generation round stores `code_hash` (truncated SHA-256) with an index plus
  `find_by_code_hash()`, but no prod path calls it, and the graveyard explicitly documents the
  sweep side records params not hashes, so no cross-death-point join exists.
- **Evidence:** `find_by_code_hash` referenced only in its own tests; graveyard docstring `:17-23`
  states the join is unmade.
- **Where found:**
  - Store: `vinu-components/vinu-research/vinu_research/generation_candidate_store.py:40-178`
  - Graveyard: `vinu-components/vinu-research/vinu_research/candidate_graveyard.py:17-79`
- **Solution:** Record `code_hash` alongside `sweep_grid_points.params_json` at sweep time (one
  nullable column), then implement the documented join in `query_candidate_graveyard()`. Keep
  read-only (no blocking gate yet).
- **What it will achieve:** First true cross-death-point answer: "this exact code failed at
  generation AND sweep" vs "similar idea, different code".
- **How it will be used:** Graveyard `GET /research/candidate-graveyard/{symbol}` links entries by
  hash; later, optional generation-time blocklist.

### A5. live_snapshots multi-angle schema with single-angle writer

- **Title:** Over-general persistence for a single producer.
- **Explanation:** Table + routes support N angles with history, but only `live_indicators` is ever
  written. Decisions use the in-memory snapshot / decision-context endpoint, never the DB history.
- **Evidence:** Single `record_live_snapshot(angle_name="live_indicators")` call site; snapshot
  routes loop generically but always return one angle.
- **Where found:**
  - Store: `vinu-components/vinu-live/vinu_live/live_decision/storage.py:107-116,515-584`
  - Schema: `vinu-components/vinu-live/vinu_live/live_decision/schema.py:164`
  - Writer: `vinu-components/vinu-live/vinu_live/live_decision/poller.py:144-147`
  - Routes: `vinu-components/vinu-live/vinu_live/server/app.py:212-267`
- **Solution:** Either (a) document as intentional single-angle log and drop generic claims, or (b)
  wire one more real producer (e.g. live regime snapshot) before generalizing further. Recommend (a)
  now, (b) only with a consumer.
- **What it will achieve:** No future builder mistakes the table for "all 30 angles live" (the
  synthesis doc already scopes it honestly to one angle — keep that honest).
- **How it will be used:** Audit/debug history for `live_indicators` only until a second angle earns
  a writer.

### A6. reflection_beliefs brain-only; evaluation-status manual-only

- **Title:** Two rich state views with exactly one real consumer each (brain / human).
- **Explanation:** 24 analysts write `reflection_beliefs`, but only `brain.py` reads them — no
  planner/scheduler/risk/capital path does. `strategy_evaluation_status` is served over HTTP but
  only consumed as best-effort idea-prompt context (inert when env unset) plus debug; no gate blocks
  on it.
- **Evidence:** Grep shows belief readers only in `brain.py` + tests/comments; eval-status readers
  only in `scheduler_workers._strategy_evaluation_context_for_ticker` + CLI debug.
- **Where found:**
  - Beliefs: `vinu-components/vinu-infra/reflection.py:264-402,526-574`, `vinu-components/vinu-reflection/vinu_reflection/reflection/brain.py:84-92,226-282`
  - Eval: `vinu-components/vinu-infra/strategy_evaluation.py:58-216,288-422`, `vinu-components/vinu-research/vinu_research/server/routes_introspect.py:233-273`, `vinu-components/vinu-agent/vinu_agent/agent/scheduler_workers.py:695-752`
- **Solution:** Wire `evaluation-status` into the research generation prompt as required context
  (cheap, read-only), and expose `get_belief(cluster, key)` to `get_live_decision_context` as an
  advisory `reflection_notes[]` field. No new gates yet.
- **What it will achieve:** Existing reflection work reaches the two LLM decision points that need
  it most, without inventing new enforcement.
- **How it will be used:** Idea generator sees "eval CRITICAL at correlation_gate, 41 lifetime
  trials, best 0.9"; live-decision agent sees "Regime cluster: degrading" alongside tier.
- **Touched (2026-09-30 fix):** `vinu-research/.../loop.py` (+`_build_eval_status_context`,
  appended to generation-story `memory_context` in `_default_quant_coder`, flows to generate +
  refine); `vinu-reflection/.../server/routes_synthesis.py` (+`GET /reflection/beliefs/notable`,
  reuses brain `gather_synthesis_inputs`, read-only); `vinu-agent/.../get_live_decision_context_
  tool.py` (+`reflection_notes[]`, fail-open `[]`; description + docstring updated).
- **Tests:** research `test_loop.py` +5 (no-db→empty + creates nothing, empty symbol, rejection +
  in-flight render, ticker isolation, env-root override) — file 87 passed; reflection
  `test_routes_synthesis.py` +4 (empty→200 `[]`, routine never listed, notable listed with
  identity, limit) — file 11 passed; agent context tool +2 (notes included, fetch failure→`[]`)
  — file 11 passed; broader agent context/live_decision/synthesis 74 passed, reflection
  brain+routes 25 passed.
- **Verified:** Prompt byte-identical when no eval rows on file (helper returns "" unless db +
  rows exist); eval helper never writes (skips `seed_step_registry`, never creates the db file);
  new route read-only; no gates added — both fields advisory-only, confirmed by grep (no new
  `if` on either value in scheduler/decision paths).
- **Bugs found / re-fixed:** none in code. One honest deviation from the filed solution: the
  item says "expose `get_belief(cluster, key)`", i.e. in-process — but agent↔reflection share
  no process by documented design (`reflection_synthesis_tool.py:14-16`), so a direct import
  would be circular. Shipped `GET /reflection/beliefs/notable` (same notable set the brain
  synthesizes from) over HTTP instead, same advisory purpose, same fail-open posture.

### A7. Maturity brier_mean / live_trade_fraction computed, ignored

- **Title:** Two precision signals calculated then dropped at every consumption point.
- **Explanation:** Reflection assessor computes `brier_mean` and `live_trade_fraction`, but its sole
  reader (`lesson_maturity_baseline_check`) uses tier + recent-form only, and the research assessor
  deliberately drops both from `as_prompt_dict`. All live consumers branch on tier (+counts/accuracy/
  coverage).
- **Evidence:** `as_dict` includes them, `as_prompt_dict` excludes; no consumer references either
  name outside the assessor and its test.
- **Where found:**
  - Assessors: `vinu-components/vinu-reflection/vinu_reflection/reflection/_maturity_assessor.py:74-164`, `vinu-components/vinu-research/vinu_research/maturity_assessor.py:67-137`
  - Reader: `vinu-components/vinu-reflection/vinu_reflection/reflection/lesson_maturity_baseline_check.py:99-117`
  - Consumers: `vinu-components/vinu-live/vinu_live/scheduler.py:218-244`, `vinu-components/vinu-live/vinu_live/maturity_link.py:55`, `vinu-components/vinu-research/vinu_research/forecast_skill.py:256-269`
- **Solution:** Either consume (add Brier-gated tier-downgrade rule + live-fraction-gated `mature`
  requirement) or delete the computation. Recommend consume: `mature` requires `live_fraction ≥
  configured floor` in addition to counts/regimes.
- **What it will achieve:** `mature` means "proven live", not just "many paper rows + two regimes".
- **How it will be used:** Tier function + prompt evidence line ("live fraction 12% — early_live
  ceiling applies").

### A8. precondition_held/tested prompt-only, never mechanical

- **Title:** The strategy's own falsifiability flag has no enforcing reader.
- **Explanation:** Poller writes `tested/precondition_held` per EXECUTE/SKIP via a dedicated store
  overlaid on GET, and the deciding agent reads it qualitatively — but the scheduler filters on
  `decision==EXECUTE` only, and `StrategyService.evaluate()` never checks it. An EXECUTE with
  `precondition_held=false` flows identically to `true`.
- **Evidence:** Scheduler weight fetch ignores the field; service `get_precondition_state` is
  display-only; tests pin write-back for EXECUTE+SKIP but no test asserts blocking.
- **Where found:**
  - Store/routes: `vinu-components/vinu-strategy/vinu_strategy/storage/precondition_state.py:39-65`, `vinu-components/vinu-strategy/vinu_strategy/server/routes_read.py:28-48`, `vinu-components/vinu-strategy/vinu_strategy/api.py:53-68`, `vinu-components/vinu-strategy/vinu_strategy/service.py:57-71`
  - Writer: `vinu-components/vinu-live/vinu_live/live_decision/poller.py:375-429`
  - Tool/prompt: `vinu-components/vinu-agent/vinu_agent/tools/get_live_decision_context_tool.py:121-123`, `vinu-components/vinu-agent/teams/live_decision/agents/live_decision_agent/prompt.md:26-32`
  - Non-reader: `vinu-components/vinu-live/vinu_live/scheduler.py:377-442`
- **Solution (needs explicit go-ahead, live-money):** Add opt-in `precondition_enforcing_enabled`
  (default off): scheduler skips `EXECUTE` rows with `precondition_held==false`, logged to
  `MaturityConsultationStore`-style record or `live_decisions`. Ship prompt-only by default first.
- **What it will achieve:** "Tested and held" becomes a real gate, not a display badge.
- **How it will be used:** Risk path drops false-precondition EXECUTEs before sizing; reflection
  counts enforcement events.

---

## GROUP B — Prompts missing available inputs at conclusion time

### B1. live_decision_agent (+ manager) omits maturity, synthesis, regime, news, correlation, drawdown, eval

- **Title:** Deciding agent concludes without seven inputs available one call away.
- **Explanation:** Prompt covers stage/snapshot/precondition/evidence-counts/past-decisions, but
  never instructs use of `maturity_status` (tool returns it when enabled), synthesis profile (tool
  exists, not registered), live regime label, news-confound check, session/shock correlation,
  drawdown state, or evaluation-status. Manager JSON (`decision/ticker/strategy_id/trigger_id/
  precondition_held/reasoning`) doesn't request tier, evidence detail (MFE/MAE, return-at-horizon),
  or past decisions.
- **Evidence:** `prompt.md` zero hits for maturity/synthesis/regime/correlation/drawdown/eval;
  `get_live_decision_context_tool.py:112-156` provides maturity; `reflection_synthesis_tool.py`
  exists but `AGENT.md:12` tools list excludes it; nearby contrasts: `trade_plan_authoring.py:
  996-1000` (regime), `loop.py:1835-1848` (news Granger), `llm.py:85-89` (correlation),
  `llm.py:81-84` (drawdown), `llm.py:60-67` (eval catalog).
- **Where found:**
  - Prompts: `vinu-components/vinu-agent/teams/live_decision/agents/live_decision_agent/prompt.md:20-112`, `vinu-components/vinu-agent/teams/live_decision/manager_prompt.md:15-62`, `vinu-components/vinu-agent/teams/live_decision/agents/live_decision_agent/AGENT.md:12`, `vinu-components/vinu-agent/teams/live_decision/TEAM.md:1-6`
  - Tools: `vinu-components/vinu-agent/vinu_agent/tools/get_live_decision_context_tool.py:104-156`, `vinu-components/vinu-agent/vinu_agent/tools/reflection_synthesis_tool.py:28-67`, `vinu-components/vinu-agent/vinu_agent/tools/signal_evidence_tool.py:59-62`
  - Route: `vinu-components/vinu-agent/vinu_agent/server/routes_live_decision.py:33-78`
- **Solution:** Register `get_reflection_synthesis` on the agent (advisory, fail-open on
  `status:none/error`); add prompt sections: maturity-tier weighting, regime label citation,
  news-confound check, correlation/drawdown awareness (explicit "state unknown if unavailable",
  never invent); extend manager JSON with `tier`, `evidence_summary{count,win_rate}`, `past_decision_noted`.
- **What it will achieve:** EXECUTE/SKIP grounded in system-confidence + cross-cutting risk, not just
  trigger history.
- **How it will be used:** Every `ready_to_execute` and `review` conclusion cites tier + synthesis +
  regime before deciding; consultations logged.
- **Touched (2026-09-30 fix):** `teams/live_decision/.../AGENT.md` (+`get_reflection_synthesis`;
  stale "Track 2 is design-only" comment corrected — no agent move-tool exists yet, but Track 2
  reaches the agent via `unconfirmed_moves[]`); `prompt.md` (+steps 6–10: maturity weighting,
  synthesis call, unconfirmed moves, reflection notes, correlation/drawdown honesty rule; review
  mode points at the same steps); `manager_prompt.md` (both JSON blocks +`tier`,
  +`evidence_summary{trigger_count, outcomes_recorded}`, +`past_decision_noted`, with
  copy-don't-compute rules).
- **Tests:** new `vinu-agent/tests/test_live_decision_prompt_wiring.py` +3 (every declared tool
  resolves in the real registry; prompt anchors present; manager JSON anchors present) — 3 passed;
  team/routes/scope/delegate suites 48 passed.
- **Verified:** `routes_live_decision.py` parses only decision/precondition_held/reasoning from the
  JSON block (extra keys ignored — additive, old readers unaffected); `subset()` skips unknown
  tools without crashing, and the registry test proves no skip happens; no prompt asks for a
  number that isn't in context.
- **Bugs found / re-fixed:** none in code. One filed-solution correction: the item proposes
  manager JSON `evidence_summary{count,win_rate}` — but `signal_evidence_summary` carries no
  win rate (`count/outcomes_recorded/triggers[]` only), so requesting one would invite invention
  against the prompt's own honesty rule. Shipped `{trigger_count, outcomes_recorded}` (copied
  fields only) instead, recorded here not rewritten there.

### B2. idea_generator omits synthesis, evidence, history, regime, correlation, drawdown, eval

- **Title:** Idea drafting ignores the system's own memory sitting next to it.
- **Explanation:** Synthesis tool is registered and described as advisory, yet `prompt.md:1-128`
  never mentions calling it, tier, or `status:none/error` handling. No signal-evidence rows, past
  run/hypothesis history, precondition fetch, required regime citation, Granger check, correlation
  tool, drawdown-events read, or eval-catalog read — all exist nearby.
- **Evidence:** `AGENT.md:6` tools vs `prompt.md` zero synthesis/evidence/history/trigger mentions;
  contrasts: `llm_generator._build_memory_context:161-191`, `loop.py:1577-1602,2107-2111`,
  `llm.py:60-89`, `research_link.py:67`.
- **Where found:**
  - Agent: `vinu-components/vinu-agent/teams/research/agents/idea_generator/AGENT.md:6-25`, `vinu-components/vinu-agent/teams/research/agents/idea_generator/prompt.md:1-128`
  - Nearby: `vinu-components/vinu-research/vinu_research/llm_generator.py:161-225`, `vinu-components/vinu-research/vinu_research/loop.py:1561-1602,2107-2111`, `vinu-components/vinu-agent/vinu_agent/tools/reflection_synthesis_tool.py:28-67`
- **Solution:** Add required-context checklist to the prompt (synthesis or `none`, eval-catalog line,
  regime citation, correlation/drawdown consulted-or-unknown); register `get_signal_evidence` read
  for the ticker before drafting.
- **What it will achieve:** Fewer duplicate/doomed ideas drafted; generation consumes the graveyard
  and reflection it currently bypasses.
- **How it will be used:** Every RECIPE/raw-code/BASE_CODE conclusion lists consulted memory with
  fallbacks stated, not silently omitted.
- **Touched (2026-09-30 fix):** `teams/research/.../idea_generator/AGENT.md` (+`get_signal_evidence`,
  +`query_hypotheses`, +`get_correlation`); `prompt.md` (+“Required context before drafting”
  consulted-or-unknown checklist: synthesis-or-none, signal-evidence rows, prior-verdict
  statuses, explicit regime citation, correlation/drawdown consulted-or-unknown).
- **Tests:** extended `vinu-agent/tests/test_live_decision_prompt_wiring.py` +2 (declared tools
  incl. the three new ones all resolve in the real registry; checklist anchors present) — file
  5 passed; team/scope/end-to-end suites 38 passed.
- **Verified:** All three tools exist in the auto-discovered registry (no registration code
  needed); no prompt step references a nonexistent tool; conclusion shapes (RECIPE/raw/BASE_CODE)
  unchanged — checklist lives in reasoning, not in output schema.
- **Bugs found / re-fixed:** none in code. One scoping note: the filed "eval-catalog line" is
  covered only via `query_hypotheses` prior verdicts + task-text rejection feedback — the
  machine gate verdicts still have no agent-side tool (research-side generation got its eval
  line in A6). A dedicated `get_evaluation_status` agent tool remains open work, recorded here.

### B3. forecast prompt omits synthesis, evidence detail, past verdicts, live regime, correlation, drawdown events, eval

- **Title:** Direction/magnitude conclusion lacks seven authoring-time inputs.
- **Explanation:** Prompt carries maturity + digests + personality/risk, but no synthesis param
  exists in its signature, no trigger-outcome section, no past plan verdicts, live regime is
  computed after the forecast call, no explicit news-correlation block, no drawdown events, and
  per-artifact eval plus options context are fetched but not forwarded.
- **Evidence:** `_build_forecast_prompt` signature takes only
  `personality,risk_state,summary,maturity`; `market_regime_stats` / `fetch_current_regime` run
  after; `check_correlation_gate` / `drawdown_events` / `MarketRegimeHistoryStore` / catalog
  `regime_tag` / `options_context(status:ok only)` never enter the prompt.
- **Where found:**
  - Prompt: `vinu-components/vinu-research/vinu_research/forecast_skill.py:163-179,248-371`
  - Authoring: `vinu-components/vinu-research/vinu_research/trade_plan_authoring.py:841-1000`
  - Nearby: `vinu-components/vinu-research/vinu_research/service.py:347-469`,
    `vinu-components/vinu-research/vinu_research/storage/strategy_store.py:45-65`,
    `vinu-components/vinu-research/vinu_research/storage/market_regime_history.py:23-28`
- **Solution:** Reorder regime fetch before forecast; add optional params
  (`synthesis_brief`, `evidence_brief`, `eval_line`, `correlation_note`, `drawdown_note`) defaulting
  to None (prompt unchanged when absent); forward options context as-is with status shown.
- **What it will achieve:** Forecast sees the same risk picture the gate chain sees seconds later.
- **How it will be used:** Every `author_trade_plan()` conclusion carries regime + eval + drawdown
  lines; backtests of prompt variants become comparable.

### B4. Generation / refinement prompts omit maturity, synthesis, full metrics, correlation, drawdown events, eval catalog

- **Title:** Strategy-code conclusion drawn from 5 scalars instead of the available rich record.
- **Explanation:** Generation `story` holds angles/features/memory/stock-profile only; refinement
  shows last code + 5 scalars (Sharpe/MaxDD/WinRate/TotalReturn/TradeCount) + critic text. Missing:
  maturity tier, synthesis, flattened-instead-of-sectioned signal reasoning, iter-history beyond
  last-2, precondition concept, explicit regime tag, required Granger judgment, portfolio
  correlation, drawdown events (critic-only), eval catalog + full metrics
  (Sortino/Calmar/CVaR/VaR/turnover/alpha/IR) that the rule-based check already computes.
- **Evidence:** `story={angles,features,memory_context,stock_profile}` only; refinement prompt lines
  show 5 scalars; `drawdowns=get_drawdowns` passed to critic, never to `story`; catalog line passed
  to risk-critic only.
- **Where found:**
  - Prompts: `vinu-components/vinu-research/vinu_research/llm_generator.py:194-315,351-482`
  - Loop: `vinu-components/vinu-research/vinu_research/loop.py:501-543,1432,1549-1666,1857-1929,2107-2111`
  - Critic: `vinu-components/vinu-research/vinu_research/llm.py:33-97`
- **Solution:** Extend `story` with `maturity_line`, `eval_catalog_line`, `drawdown_events_brief`,
  `correlation_note`; render signal-evidence as its own section (counts + reasoning) instead of
  flattening; show full metric row on refinement.
- **What it will achieve:** Drafts compete on the same metrics they will be judged by; fewer
  iterations wasted on ideas the catalog already rejects.
- **How it will be used:** Every generate/refine call logs the extended story for later prompt
  ablation.

### B5. Duplicate-idea check judges on name strings alone

- **Title:** Dedup LLM never sees each idea's track record.
- **Explanation:** Caller passes only `[h.strategy_type or ""]` strings; the LLM never sees
  `Hypothesis.status/best_sharpe/evidence/invalidation_reason/indicators_used`, TF-IDF score, or
  graveyard rejects. A `rejected` idea with negative evidence looks identical to `exploring` with
  positive evidence.
- **Evidence:** Call site slices strings; `Evidence{metric/conclusion/reasoning/metric_kind}` and
  graveyard list available in scope but unpassed.
- **Where found:**
  - Check: `vinu-components/vinu-research/vinu_research/llm.py:284-294,519-538`
  - Caller: `vinu-components/vinu-research/vinu_research/loop.py:1354-1424`
  - Models: `vinu-components/vinu-research/vinu_research/models.py:22-86`
  - Graveyard: `vinu-components/vinu-research/vinu_research/candidate_graveyard.py:100`
- **Solution:** Pass per-candidate `{strategy_type, status, best_sharpe, evidence_count,
  last_conclusion, tfidf_score}` (short, bounded); keep one-call shape; log the enriched input.
- **What it will achieve:** Fewer false merges (different ideas sharing words) and fewer wasted
  reruns (same idea re-proposed after rejection).
- **How it will be used:** Every dedup verdict cites status + evidence, not just wording overlap.
- **Touched (2026-09-30 fix):** `vinu-research/.../llm.py` (+`_format_duplicate_candidate`,
  `check_duplicate_idea` accepts enriched dicts, system prompt demands status+evidence citation);
  `vinu-research/.../loop.py` (+`_enrich_duplicate_candidate`, caller passes
  `{strategy_type,status,best_sharpe,evidence_count,last_conclusion,invalidation_reason,
  tfidf_score}` + debug log of enriched inputs; one-call shape kept).
- **Tests:** `test_llm.py` +4 (string passthrough, enriched render, missing-keys degrade, prompt
  demands citation) — file 26 passed; `test_loop.py` +1 (rejected-with-evidence vs
  exploring-with-evidence carry different records into the call) — dedup selection 16 passed.
- **Verified:** Legacy string lists still accepted (formatter passthrough); one-call shape
  unchanged; enriched-input debug log gives the audit trail; existing dedup semantics
  (skip screen, confidence floor, trusted negative, similarity fallback) untouched.
- **Bugs found / re-fixed:** one, mine: a no-op edit stripped a newline in `test_llm.py:156`,
  breaking collection with IndentationError — caught by pytest before anything else ran,
  repaired to byte-identical original line, file green after. Also noted: graveyard rejects are
  still not passed (call site only holds Hypotheses; graveyard join is A4's code_hash work) —
  hypothesis-side track record covers the filed substance.

### B6. Brain prompt omits maturity, past syntheses, recency, raw regime/news/correlation/drawdown detail

- **Title:** System-level synthesis concludes without its own history and without raw signals.
- **Explanation:** Prompt rows carry analyst/cluster/scope/severity/trend/metric/narrative/count,
  but drop `computed_at` (recency unknowable), past synthesis + resolution trend (by design no
  LLM-grading, but trend still hidable as data), maturity tier, Track-1/hypothesis rows, and raw
  regime/news/correlation/drawdown detail behind the narratives (domain floors, windows, polarity,
  matrices, events, eval values).
- **Evidence:** Row builder omits `computed_at`; store has `get_latest_synthesis` /
  `list_pending_syntheses` / resolution history never fed back; cluster narratives are the only
  carriers.
- **Where found:**
  - Brain: `vinu-components/vinu-reflection/vinu_reflection/reflection/brain.py:59-147,205-282`
  - Store: `vinu-components/vinu-infra/reflection.py:171-274,406-501`
  - Assessors: `vinu-components/vinu-research/vinu_research/maturity_assessor.py:81-157`
- **Solution:** Add `computed_at` + `days_stale` per row; prepend compact past-synthesis trend
  (ids, actions, outcomes — data, not grading); append maturity line + eval counts as appendix rows.
  Keep one-call shape and fail-open.
- **What it will achieve:** Syntheses become temporally aware and self-referential without a second
  grading LLM.
- **How it will be used:** Hourly brain cites "belief from 6d ago, still significant" and "last 3
  syntheses: 2 inconclusive, 1 correct" before proposing.
- **Touched (2026-09-30 fix):** `vinu-infra/reflection.py` (+`list_recent_syntheses`, read-only);
  `vinu-infra/strategy_evaluation.py` (+`count_by_status`, read-only); `vinu-reflection/.../
  reflection/brain.py` (`_build_prompt` +`computed_at`/`days_stale` per row, past-trend section,
  system appendix; +`_past_synthesis_trend`, `_maturity_line_for_prompt`, `_eval_line_for_prompt`
  helpers; `run_synthesis` +`data_root_paths` kwarg); `vinu-reflection/.../cli.py` (worker passes
  `data_root_paths`).
- **Tests:** reflection `test_brain.py` +9 (recency fields, first-synthesis note, trend
  action+outcome, appendix gating, end-to-end prompt via FakeLLM, both helpers fail-open, eval
  counts from env root) — file 22 passed; infra `test_reflection.py` +1 (recent order+limit),
  `test_strategy_evaluation.py` +2 (counts grouped, empty) — files 56 passed; routes+cli 14 passed.
- **Verified:** One-call shape kept; trend is data (ids/actions/mechanical outcomes), never a
  second grading LLM; both appendix lines best-effort (missing roots/db/env → line omitted,
  synthesis proceeds); eval helper never writes (no seeding, no file creation); existing
  run_synthesis callers work unchanged (kwarg defaults None).
- **Bugs found / re-fixed:** two, both mine, both caught before running anything: (1) a stray
  edit dropped a newline in `vinu-infra/reflection.py` — reverted immediately, diff confirmed
  empty before proceeding; (2) a test I first placed in `test_reflection.py` belonged in
  `test_strategy_evaluation.py` — moved, no stray test left behind. Also one scoping note:
  eval appendix resolves only via `VINU_STRATEGY_EVAL_DATA_ROOT` env (reflection owns no
  research root — paths are never guessed); maturity line needs `vinu_agent` in
  `data_root_paths`, which the worker already provides.

---

## GROUP C — Concluded but defaulted (durable yet non-advancing branches)

### C1. Unrecognized / failed live decisions recorded, never advanced

- **Title:** Unknown verdicts sit in `ready_to_execute` and retry forever without escalation.
- **Explanation:** Every branch is durably recorded (`decision` or `"unrecognized"` / `"error"`),
  but only EXECUTE/SKIP advance the lifecycle; EXTEND_GRACE_WINDOW, unrecognized, empty, error, and
  HTTP exceptions all log and stay, retrying next cycle with no counter, no alert, no dead-letter.
- **Evidence:** Poller branches: EXECUTE/SKIP → `mark_executed` + precondition write; EXTEND →
  warning no-op; else → error no-advance; HTTP fail → `error` row. Review mode mirrors: only
  HOLD/EXIT advance `last_reviewed_bar_ts`.
- **Where found:**
  - Poller: `vinu-components/vinu-live/vinu_live/live_decision/poller.py:235-429`
  - Storage: `vinu-components/vinu-live/vinu_live/live_decision/storage.py:292-395`
  - Tracker: `vinu-components/vinu-live/vinu_live/live_decision/state_tracker.py:74-178`
- **Solution:** Add `consecutive_unrecognized_count` per trigger (same streak pattern as
  `RECON_DRIFT_ALERT_CYCLES=3` and `unavailable_halt_threshold=3`); escalate to notify route after
  N, expire to `expired` after M. Record both transitions in `stage_transitions`.
- **What it will achieve:** No trigger spins silently forever; ops sees the stuck list.
- **How it will be used:** State tracker owns the counters; poller only increments; notify on
  newly-persistent streaks (edge-triggered, not every cycle).

### C2. Unsized EXECUTE marked applied and forgotten

- **Title:** Real EXECUTE with `position_size==0.0` is final-dropped with only a log line.
- **Explanation:** Fetch-failure stays unapplied (retried), but configured-yet-unsized is marked
  applied, contributes no weight, and is never re-logged or re-surfaced. A misconfigured strategy
  looks identical to "decided nothing" after one line.
- **Evidence:** `mark_decision_applied()` called on the unsized path; only warning emitted.
- **Where found:**
  - Scheduler: `vinu-components/vinu-live/vinu_live/scheduler.py:377-442`
  - Config: `vinu-components/vinu-strategy/vinu_strategy/models/strategy.py:95-148`
- **Solution:** Route unsized EXECUTEs to a visible `needs_sizing` list (`GET /live/decisions/
  needs-sizing` or eval-status step) instead of silent-applied; keep no-retail behavior (never
  invent size), but make the queue drainable by config fix.
- **What it will achieve:** Configuration gaps become actionable work items, not one-line logs.
- **How it will be used:** Ops/config review drains the list; reflection counts time-to-sized.

### C3. Breaker VaR skipped (covariance None), guards fail-open, translator fail-closed — three postures, one undocumented page

- **Title:** Risk path mixes skip-open and skip-closed without a single stated rule.
- **Explanation:** Aggregate-VaR returns None on missing covariance / <2 symbols / non-positive
  value and the verdict stays ALLOW on other checks; spread/event/halt fetch failures return None =
  proceed; unknown limit-price falls back to market (never guessed limit); missing price skips
  instruction / expected-position / orchestrator cycle (retry later). Each is locally sensible, but
  no one page states which failure opens and which closes.
- **Evidence:** `check_limits` continues past None subchecks; guards map fetch-fail → None →
  proceed; translator/orchestrator/reconcile skip on missing price; scheduler omits silently-failed
  price fetches.
- **Where found:**
  - Breaker: `vinu-components/vinu-live/vinu_live/breaker/engine.py:46-57,139-173`,
    `vinu-components/vinu-live/vinu_live/breaker/limits.py:8-23`
  - Scheduler: `vinu-components/vinu-live/vinu_live/scheduler.py:227-284,514-579,646-739`
  - Translator: `vinu-components/vinu-live/vinu_live/signal_translator.py:121-168`
  - Guards: `vinu-components/vinu-live/vinu_live/trade_plan/guards.py:28-132`
  - Orchestrator: `vinu-components/vinu-live/vinu_live/trade_plan/orchestrator.py:883-884,1024-1026`
- **Solution:** Write the one-page fail-open/fail-closed matrix (per check: failure → open/closed +
  why), starting from current behavior; cov-matrix None stays open-but-logged until a shared
  covariance provider exists (named gap, already documented as scoped).
- **What it will achieve:** Future risk edits follow the matrix instead of guessing per call site.
- **How it will be used:** Review checklist for every new gate: "state your failure posture + log +
  test both sides".

### C4. Degraded strategy runs persist with 0.0 fills; unfunded portfolio sleeves stay at ~0 invisibly

- **Title:** Two "kept visible" paths that are only visible if you know where to look.
- **Explanation:** Strategy omits failed symbols, fills missing/non-numeric features with 0.0,
  clamps bad shorts, logs degraded + `sanity_issues`, but still persists/returns weights. Portfolio
  skips funded sleeves without record and writes heuristic `RejectionRecord` for the rest into
  `not_funded` + `allocation_history` (best-effort). Both are honest but discoverable only via
  specific meta keys / routes.
- **Evidence:** Service fills + quality flag + clamp-keep; portfolio heuristic attribution documented
  as heuristic; write failures only warn.
- **Where found:**
  - Strategy: `vinu-components/vinu-strategy/vinu_strategy/service.py:132-238,314-328`,
    `vinu-components/vinu-strategy/vinu_strategy/engine/pipeline.py:75-106`
  - Portfolio: `vinu-components/vinu-portfolio/vinu_portfolio/service.py:937-989,1200-1244`
  - Shape: `vinu-components/vinu-infra/rejection_log.py:25-49`
- **Solution:** Surface both in `GET /research/evaluation-status/by-ticker/{ticker}` as
  `data_quality{is_degraded,sanity_issues}` and `not_funded[]` (already partially there — complete
  the threading rather than new UI).
- **What it will achieve:** "Why is this weight 0" answerable in one status call.
- **How it will be used:** Support/debug reads eval-status first; reflection tallies degraded-rate
  per strategy.

### C5. Research all-fail / empty-candidate / walk-forward-None / store-disabled paths rely on caller discipline

- **Title:** Five quiet empties with correct-but-scattered handling.
- **Explanation:** Per-candidate backtest exceptions become `result=None`; only all-None raises
  (`infra_failure` vs `no_strategy_found` vs `passed` correctly distinguished). Empty sweep yields
  `ranked=[]/pbo=None`/skipped walk-forward. Bad windows become None; zero completed → None verdict.
  Generation store None/disabled is a deliberate no-op; record failure never breaks generation.
  Sweep `persist=False` inner grids fold into the outer row by design. Each correct alone, but the
  "what empty means" contract lives in five places.
- **Evidence:** Loop/sweep/walk-forward/generation branches each handle None locally; outcome_status
  naming avoids `status` collision deliberately.
- **Where found:**
  - Loop: `vinu-components/vinu-research/vinu_research/loop.py:70-73,1475-1541`
  - Sweep: `vinu-components/vinu-research/vinu_research/sweep_grid.py:245-315`
  - Walk-forward: `vinu-components/vinu-research/vinu_research/walk_forward.py:347-419`
  - Routes: `vinu-components/vinu-research/vinu_research/server/routes_read.py:270-300`,
    `vinu-components/vinu-research/vinu_research/server/routes_introspect.py:247-248`
- **Solution:** Document the empty-meaning table (`None` vs `[]` vs `""` sweep_id vs `no_strategy_
  found`) in one place (introspect module docstring + HOW file), no behavior change; add one test
  per empty spelling the contract.
- **What it will achieve:** No future caller mistakes "no rows" for "not yet run".
- **How it will be used:** Contract tests pin the empties; agent tools map them to WAIT, not ERROR.
- **Touched (2026-09-30 fix):** `vinu-research/.../server/routes_introspect.py` (module docstring +
  empty-meaning table: outcome_status trio, per-candidate/all-None, sweep/pbo/walk-forward/sweep_id,
  generation-store-None, eval 404 vs count-0 vs agent "", paper-return statuses, WAIT/DONE vs ERROR
  rule); `newer-thinking-with-discussed/how-system-implemented.md` (+appendix with the same table).
  Zero behavior change — docs only.
- **Tests:** new `vinu-research/tests/test_empty_meanings.py` +7 (outcome trio; all-points-failed
  sweep → ranked []/succeeded 0/completeness 0/pbo None/walk_forward None; sweep_id "" vs uuid;
  generation-store-None no-op; agent eval context "" with env unset) — 7 passed; introspect-eval
  + sweep suites 31 passed.
- **Verified:** Every spelling in the table re-read against current code (loop/sweep_grid/
  walk_forward/routes line numbers re-resolved post-fix-shift — the filed C5 line numbers were
  pre-fix and have moved); previously-pinned empties (outcome trio, all-fail reraise, pbo-None,
  persist-False blank id, walk-forward Nones, paper-return statuses, eval 404, by-ticker count-0)
  cited, not duplicated.
- **Bugs found / re-fixed:** one, mine: first draft of the contract test built IterationRecord
  without its required `strategy_code` field (TypeError at collection of one test) — fixed to
  match the existing test_loop helper shape, green after. One filed-claim correction: "empty
  sweep yields ranked=[]" needed precision — an empty *grid* is rejected with ValueError; only
  all-points-*failed* yields ranked [] — table states both.

### C6. Maturity / synthesis / eval / precondition fetch failures all fail-open — correctly, but silently compounding

- **Title:** Six independent fail-opens can stack into an unflagged fully-open run.
- **Explanation:** Maturity fetch → None/1.0, disabled → defaults, prompt proceeds without block;
  synthesis `none`/error → advisory skip; eval missing → 404/inert `""`; precondition write fail →
  warning only (EXECUTE/SKIP-only). Each is the right local default, but a cycle with all six
  failing looks identical to "all signals genuinely neutral" — no combined flag exists.
- **Evidence:** Six `LOG.debug/warning` + default paths; consultation store records
  `tier=unknown/no_change_status_unavailable` for one of them; others leave no joint trace.
- **Where found:**
  - Maturity: `vinu-components/vinu-live/vinu_live/maturity_link.py:39-52`,
    `vinu-components/vinu-live/vinu_live/scheduler.py:218-244`,
    `vinu-components/vinu-portfolio/vinu_portfolio/service.py:895-928`,
    `vinu-components/vinu-research/vinu_research/trade_plan_authoring.py:893-908`
  - Synthesis: `vinu-components/vinu-agent/vinu_agent/tools/reflection_synthesis_tool.py:28-67`
  - Eval: `vinu-components/vinu-agent/vinu_agent/agent/scheduler_workers.py:695-752`
  - Precondition: `vinu-components/vinu-live/vinu_live/live_decision/poller.py:375-429`
  - Log: `vinu-components/vinu-infra/maturity_consultation.py:47-105`
- **Solution:** Add a per-cycle `confidence_gaps[]` list (which inputs were unavailable) to the
  decision context + evaluation-status, and down-tier size/wording when gaps stack (e.g. ≥3 gaps →
  treat as one tier colder). Log-only first, enforce later.
- **What it will achieve:** "I don't know because inputs were missing" becomes distinguishable from
  "I know and I'm neutral".
- **How it will be used:** Live-decision prompt + forecast prompt cite gaps; risk scaler reads the
  count; reflection tracks gap-rate as a reliability metric.

---

## Index (for the fix passes)

- Wiring first (no new tables): A1, A2, A6, B1–B2 (prompt-only), C5 (docs+tests).
- Small schema (nullable columns, backfillable): A3, A4, C2.
- Policy decisions (needs explicit go-ahead): A8, C1 escalation counts, C3 matrix sign-off, C6
  down-tier rule, B-side blocking gates (eval, precondition) — prompt advisory ships first.
- Deferred by design (recorded, not scheduled): bucket table, REDUCE/ADD, P&L-for-reviewer,
  full 30-angle live snapshots, agent↔research stamp, blessed-path lint, `trade_plan_tool` coverage.

Recheck: every cited file path above exists on disk 2026-09-30; every claim traces to
a cited line; no stale-doc facts mixed in (old counts, prompt-only maturity, no-exit, seed-only,
no-graveyard/write-back all corrected in HOW file).

