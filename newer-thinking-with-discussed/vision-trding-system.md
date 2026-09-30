# Vision — Trading System (consolidated, no case missed)

Sources, read cover-to-cover twice:
- `high-expectations/chatgpt-version/how-the-system-should-be.md` (18 sections)
- `high-expectations/chatgpt-version/how-he-will-trade.md` (17 sections)
- `high-expectations/chatgpt-version/already-built.md` (built / partial / deferred ledger)
- `missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-design/00-overview.md`
- `.../01-full-system-layer-map.md` (6 layers + reflection + infra)
- `.../02-open-questions-strategy-and-simulation.md` (items #1–#26, 5075 lines, incl. all dated UPDATEs to 2026-09-28)
- `.../03-strategy-definition-full-schema.md` (8-field schema)
- `.../04-synthesis-built-vs-missing-2026-09-28.md` (synthesis + every 2026-09-28 follow-up build)
- `.../05-remaining-items-2026-09-28.md` (the 3 deliberately-left items)
- `.../reverse-engineering/00-overview.md`, `01-live-decision-loop-open-points.md` (9 points),
  `02-implementation-status.md`, `03-poller-and-state-schema.md`, `04-live-detector-schema.md`,
  `05-deciding-agent-and-precondition-tracking.md`, `06-execution-handoff-and-architecture.md`,
  `07-bucket-table-deferred.md`

Note on maturity: the high-expectations docs do NOT explain maturity as a subsystem —
they only ask for gradual capital scaling (should-be #12: backtest → walk-forward → paper →
small-live → gradual scaling). The maturity tier itself (`cold_start/paper_only/early_live/mature`,
`MaturityAssessor`, `MaturityConsultationStore`, capital/risk scaling) lives in
`missing-pieces-of-system/maturity-agentic-system/00-maturity-agentic-system-explanation.md`
and item #25. It is the mechanism that implements the scaling expectation. Both are covered below.

---

## PART A — High expectations: every case (should-be 1–18, will-trade 1–17)

### A1. Pre-trade intelligence layer (should-be #1)
Analyze per asset: price action, volume, order book / depth, bid/ask imbalance, volatility regime,
momentum, trend structure, support/resistance, liquidity, spread, funding rates, open interest,
options data / IV, correlations, sector/index relationships, macro, news, earnings/events,
sentiment, historical patterns, cross-asset signals. Most important output: **what type of market
are we in** (trending → momentum; mean-reverting → fade extremes; high-vol → cut size;
low-liquidity → avoid; event-driven → suspend normal strategies). Status: built — 30 computed
angles in `vinu-initial-analysis/angles/` (`regime_analysis`, `trend_lifecycle`,
`news_price_causality`, `signal_evidence`, `peer_relative_strength`, `search_trends` 30th angle via
`pytrends` z-score + forward-return backtest).

### A2. AI Market Brain, multi-agent, hard risk layer (should-be #2)
Market data → price/TA + order-book + news/macro → Market Regime AI → signal generation
(trend / mean-reversion / event models) → aggregator → risk engine → portfolio optimizer →
execution → broker. AI never touches broker directly. Status: built — separate angles feed common
signal; `risk_gatekeeper` / `order_guard` sit between AI and execution.

### A3. Know WHY, structured decision (should-be #3)
Not `BUY BTC 82%`. Must carry: asset, direction, expected return, expected volatility, P(positive),
regime, supporting signals (+/++/+++), contradicting signals (−/−−), stop, expected drawdown,
position size, risk/reward, EXECUTE/WAIT verdict. Status: built — `TradeScore`
(`trade_score_calibration.py`) carries regime fit + EV + risk + R:R together.

### A4. Confidence ≠ P(win); Expected Value (should-be #4, will-trade #5)
`EV = P(win)×avg_win − P(loss)×avg_loss`, then subtract fees/slippage/impact/uncertainty; ask
whether net EV pays for risk+cost+uncertainty. Status: built — `TradeScoreResult.ev_score` is a
real scored EV component.

### A5. Uncertainty, right to say "I don't know" (should-be #5)
Weak signal + low model agreement + low regime confidence + poor liquidity + imminent event →
DO NOT TRADE. **No-trade is a decision.** Status: partial — expressed indirectly via independent
gates (trade-score tier, correlation gate, calibration gate), now unified read-only in
`StrategyEvaluationStore` (`GET /research/evaluation-status/*`); no single confidence abstraction.
Left open honestly.

### A6. Risk engine stronger than AI, deterministic, overriding (should-be #6, will-trade #6)
Controls: max position/leverage/exposure (portfolio, sector, single-asset), daily/strategy loss
limit, max drawdown, correlation exposure, vol-adjusted sizing, stop/take-profit/trailing, max
order size, max slippage, liquidity requirements. Example: AI asks $1M → engine allows $270k on
exposure+correlation+vol. AI cannot override hard kill switch. Status: built —
`vinu-portfolio/circuit_breakers.py`, `risk_gatekeeper`, `order_guard`, independent of model
confidence.

### A7. Intelligent / dynamic / conservative position sizing (should-be #7, will-trade #6–#7)
Never flat size. Size = f(signal, expected return, volatility, liquidity, exposure, correlation,
drawdown, regime, event risk). Strong+low-vol+liquid → larger; strong+extreme-vol → smaller;
weak+correlated → tiny/none. Risk per trade from stop distance (e.g. 0.5% portfolio), never from
AI confidence. All four composite factors built: vol-target + correlation-aware (`CompositeSizer`,
DCC-GARCH/Gerber via shared `vinu_tools/compute/risk/shock_correlation.py`) + evidence-confidence
(`vinu_infra/evidence_confidence.py`, `compute_track2_aggregate()`,
`GET /research/track2-aggregate/{symbol}`, `EvidenceConfidenceSizer` — Laplace-smoothed,
point-in-time-safe; caveat: no caller populates `SimulationInput.evidence_triggers` yet) +
regime-aware (`RegimeAwareSizer`, benchmark-level, reuses already-fetched benchmark series) +
drawdown-aware (`compute_drawdown_action()` pure extraction, live monitor delegates unchanged;
`DrawdownAwareSizer` maps ok/halve/flat/halt → 1.0/0.5/0.0/0.0, halt non-sticky). Item #14A fully
closed.

### A8. Execution intelligence — HOW to buy (should-be #8)
Large orders sliced via VWAP/TWAP/limit/iceberg/splitting/passive/aggressive/dynamic; monitor
spread, depth, impact, slippage, latency, liquidity, fill probability; adapt live. Status: built —
`vinu-live/execution.py` VWAP/TWAP slicing.

### A9. Continuous re-evaluation, thesis invalidation, time stop (should-be #9–#10, will-trade #8–#10)
Not analysis→BUY→WAIT→SELL. ANALYSIS→ENTRY→MONITOR→NEW DATA→RE-EVALUATE→HOLD/ADD/REDUCE/EXIT.
Entry states thesis/invalidation/target/horizon; invalidation = thesis-level (e.g. close back
below breakout on volume), not fixed 1%. Time stop: thesis not working in expected window → exit
on opportunity cost even if price stop unhit. Trade Score re-scored live (82→79→63→41 →
REDUCE/EXIT). Before entry: thesis validator (evidence ✓, risks ⚠, VALID?). After entry: thesis
score tracked, reduce on decay. Status: built — `vinu-live/live_decision/` (detector/poller/state
tracker/deciding agent/record) + 2026-09-28 exit fix (`live_decision_open_positions` table as
per-cycle source of truth; HOLD/EXIT review `mode=review` every N bars, default 5; REDUCE/ADD
deliberately not built — no sizing mechanism exists).

### A10. Adversarial analysis, bull vs bear vs risk (should-be #11, will-trade #4)
Always ask "why NOT buy": bull case, bear case, risk case → scored verdict (e.g. +7/−5/−4 → NO
TRADE). Reduces confirmation bias. Status: built but intentionally async/opt-in —
`investment_committee` (`bull_advocate`, `bear_advocate`, `risk_officer`); `routes_swarm.py`:
`none` → proceed. Kept non-blocking on explicit instruction (LLM latency per trade), not a gap.

### A11. Backtest is not enough (should-be #12)
Historical backtest + walk-forward (train→test→roll→retrain→test) + paper + small-live + gradual
scaling. Status: built — backtest + walk-forward + paper + opt-in `maturity_capital_gating_enabled`
scales `deployable_equity` by tier multiplier; fails open to full capital.

### A12. Strategy-degradation detection (should-be #13)
Sharpe 2.1/win 61% → 0.4/48% + slippage/drawdown ↑ → detect degradation → cut allocation →
investigate → retrain/recalibrate → paper → restore. Status: built — `vinu-research/decay.py`
(`DecayThresholds`, `DecaySnapshot`); `trade_score_calibration` reuses same machinery.

### A13. Market memory, historical analogues (should-be #14)
"This looks like 37 past situations: 23+/14−, avg +1.3%, med +0.9%, max DD −2.8%" → current +
analogues + stats. Status: built — `trend_lifecycle/patterns.py` KNN over peak/trough library.

### A14. Alternative data, unified market state (should-be #15)
Beyond OHLCV: market/trades/order-book/options/funding/OI/news/calendar/earnings/sentiment/search/
on-chain/alternative → one market-state representation. Status: search-trends built (30th angle);
order-book/L2 deferred (paid Alpaca/Polygon tier blocker); on-chain deferred (zero consumer —
equities-only via Alpaca paper today). Decisions, not gaps.

### A15. Full audit trail per trade (should-be #16)
Timestamp, market state, features, model versions, signals, AI reasoning, expected return, risk,
size, execution/order/slippage, exit reason, P&L, post-trade analysis → "why did we lose?"
answerable. Status: built — `trade_audit_log.py` + run cards + `StrategyEvaluationStore`
(`get_status`/`get_history`) + 3 new read-only routes.

### A16. Post-trade learning loop (should-be #17, will-trade #17)
Prediction vs actual (+1.8% vs −0.7%): what worked/broke (momentum ✓, liquidity ✗, news regime
change, late entry, 0.31% slippage) → classify loss (prediction/execution/risk/data/regime/model/
unexpected) → closed learning loop → research machine over 10k trades (where edge holds/fails).
Status: built — `HypothesisRegistry` evidence trail + `vinu-reflection` (loss attribution,
threshold calibration, 24 analysts, step-8 brain, step-9 consumer).

### A17. Ultimate architecture + philosophy + metrics (should-be #18, will-trade loop)
Market data → understanding (regime/features/news-macro-sentiment) → AI research (prediction/
pattern/NLP/analogues) → multi-agent debate → decision engine (EV/confidence/uncertainty/thesis)
→ risk → execution → broker → continuous monitoring → post-trade learning → back to AI. Philosophy:
don't be right always; find asymmetric odds; upside ≫ downside; risk little when uncertain; scale
only on confluence; exit on invalidation; never let one trade hurt portfolio; learn regimes of
edge. Metrics: Sharpe/Sortino/max-DD/expectancy/turnover/slippage/tail-risk/robustness across
unseen regimes — never win rate (55% with great R:R beats 80% with tails). Status: built —
`vinu-simulator/engine/metrics.py` (Sharpe/Sortino/MDD/expectancy/turnover/VaR/CVaR); architecture
layers real (see Part B).

### A18. Senior-trader operating rules (will-trade #1–#3, #11–#16 consolidated)
WAIT-first (trade only if edge pays risk+cost+uncertainty); regime-first strategy selection;
confluence over single-indicator (never RSI=28→BUY); three decisions BUY/WAIT/SHORT and
HOLD/ADD/REDUCE/EXIT; asymmetry (+3%/−1% with distribution, not 1%/1% on uncertainty);
selectivity funnel (500 → regime → liquidity → event → EV → risk → correlation → execution → 15);
Trade Score checklist with calibrated bands (>110 strong / 90–110 moderate / 70–90 watch / <70 none;
weights self-calibrated, not hand-picked); portfolio-level netting (4 apparent longs = one risk-on
bet → take A, trim B, reject C/D); kill switch (daily-loss/max-DD/vol/data/exchange/exec/model/
OOD-regime/slippage triggers). Status: all built — PASS/REFINE/STOP + HOLD/ADD/REDUCE/EXIT;
hard-filters → K-cap (`thesis_intake_gate`, 3/ticker) → Monte Carlo → holdout; self-calibrating
`TradeScore`; `_reward_risk_ratio()` floor 1.5 → `no_trade`; DCC-GARCH/Gerber + `_net_by_symbol`
(net chosen: only realizable single-account policy; severe conflicts escalate to
`/notify/symbol-conflict`); `_halt_trading` wired to live cycle (item #24 fix).

---

## PART B — System-wide audit and design: every case

### B1. Layer map (01)
L1 discovery `vinu-screener` → L2 data+understanding (`vinu-stock-price`, `vinu-news`,
`vinu-tools` 28 real indicators, `vinu-initial-analysis` 28→30 angles) → L3 hypothesis+validation
(`vinu-agent` planner-worker, `vinu-research` generator+`HypothesisRegistry`, `vinu-simulator`
backtest) → L4 daily execution (`vinu-strategy` WeightPipeline/registry) → L5 portfolio risk
(`vinu-portfolio` sizing/risk-budget/breakers/drawdown/correlation) → L6 real execution
(`vinu-live` translator/approval/reconciliation/scheduler). Cross-cutting `vinu-reflection`
(worker-loop auditor). Infra `vinu-infra` (SQLiteBackend, auth, risk-math, policy/manifest,
`point_in_time`, `rejection_log`, `evidence_confidence`, `contract_version`,
`strategy_evaluation`, `maturity_consultation`, `reflection` tables), `hindsight-llm` (local LLM
server; no real client in code yet — v1 brain reads `reflection_beliefs` only), `vinu-ui`
(read-only frontend). L3 traced file-by-file; L4–L6 confirmed real but handoffs less deeply
traced. Known caveat fixed 2026-09-28: ticker source was seed-and-forget, now live screener
intersection when `screener_ranker_id` set, seed additive as override, fail-open fallback.

### B2. Items #1–#10 (strategy/simulation/recording core)
- #1 must-condition "why" → HypothesisRegistry wiring: built — evidence-trail-only
  (`Evidence.metric_kind`, strict exact-match, no auto-promotion, no auto-create) via
  `signal_evidence_bridge.py`, wired to planner-worker cycle; fails open.
- #2 universal strategy in 29th angle: proof-of-concept built — `MustCondition` + `series_by_key`,
  `_find_crossings` reused for threshold-cross + two-series-cross; RSI(14)>30 mean-reversion proven
  through same pipeline; `None` preserves old SMA5/50 byte-for-byte; no config/HTTP surface yet
  (runner has `inspect.signature` extension point, unfed).
- #3 sweep comparisons discarded: built — `sweep_store.py` (`sweep_runs` + `sweep_grid_points`,
  losers with real failure reasons, `persist=False` on walk-forward inner grids), `sweep_id` on
  `POST /research/sweep/grid`, `GET .../{sweep_id}` + `?symbol=`.
- #4 simulator PnL sizing vs Track-2 engine: built — shared `vinu_infra/evidence_confidence.py`
  (Laplace, point-in-time-safe) + `compute_track2_aggregate()` + `GET /research/track2-aggregate/{symbol}`
  (reads Track-1 `SignalEvidenceStore`; Track 2 itself still design-only) + `EvidenceConfidenceSizer`
  (per-symbol, no network calls; `evidence_triggers` pre-fetched by caller; no caller wires it yet —
  small integration left).
- #5 present-data live snapshots: built, honestly scoped — append-only `live_snapshots` (wall-clock
  recency, mirrors `RunLog`), written by `live_decision/poller.py` (the only real live-snapshot
  producer), `GET /live/snapshots/{symbol}` (+`staleness_seconds` fresh, never stored) and
  `.../{angle}/history`; covers `live_indicators` only, not all 30 historical angles.
- #6 regime tagging: Track-1 half built — public `regime_analysis/compute.py` series reused,
  `bar_ts` lookup (not positional; warmup re-index trap avoided), stored in flexible `indicators`
  dict (`session`/`day_of_week` confirmed absent from real payload); Track-2 half untouched (no code).
- #7 assumption decay/versioning: already existed (`HypothesisRegistry` lifecycle
  exploring/testing/validated/rejected/monitoring/mc_gate_failed + evidence + invalidation) — same
  gap as #1, same fix.
- #8 cross-strategy indicator pooling: built — `pool_evidence_by_indicator()` read-time query (no new
  table), grouped by `(indicator, metric_kind)`, `GET /research/indicators/pool`; 8 tests.
- #9 news-confound flagging: Track-1 half built — no new HTTP (runner already fetches/caches news per
  run; `signal_evidence/compute.py` just never read it); `news_confound{occurred,minutes_before,
  article_id}` (≤ trigger only, no look-ahead) in `indicators` dict; `NEWS_CONFOUND_WINDOW_MINUTES=60`
  guessed like `FORWARD_HORIZON_BARS`; precondition was item #19 fix (already landed). Track-2 half
  untouched.
- #10 cross-track disagreement: built scoped-down — `detect_move()` (2×ATR(14) floor) runs per candle
  close per watched (ticker,timeframe) unconditionally in vinu-live poller (no new scanner);
  `MoveEvidenceStore` (vinu-research, sibling of SignalEvidenceStore) records detections only;
  `list_unconfirmed_moves()` read-time join (established cross-store pattern, no periodic table);
  honest caveat: nothing wrote `SignalEvidenceStore` in production until 2026-09-28 writer fix, so
  everything defaulted `track2_only` until then; writer now auto-derives name
  (`live_indicators.adx_14_gt_999`), once per genuine firing, best-effort.

### B3. Items #11–#13 (service inefficiency audits)
- #11 vinu-agent tools: #1 date-helper dedup+fix (`tools/_date_utils.py`; `mktime` local-tz bug fixed,
  22 tests), #2 as-of clamp coverage for priority files + 7/8 remaining zero-coverage files closed
  (`portfolio/remember/query-memory/web-search/session-search/skill/workflow/compact/angle-clusters/
  position-sizing-wrapper`; 27+30 tests; `trade_plan_tool.py` 1330 lines deliberately left as
  session-sized work), #3 fundamentals yfinance retry (6 tests), #5 options retryable/permanent split
  (`RetryableOptionsError`, 403 grouped with 401; 21 tests), #4 per-turn `CallCache` built
  (instance-lifetime scoped, never across replays; errors/empties never cached; 11 tests). Real bugs
  fixed: partial-section failure discarding good sections; re-remember resetting `created_at`;
  web-search limitation flagged (DuckDuckGo Instant-Answer only, mostly empty).
- #12 vinu-research: fully closed — #3 PBO/CSCV math 14 tests; #2 dead `diverse_top_n()` built on
  instruction (`_backtest_and_rank_candidates()`, diverse subset really backtested, re-ranked by
  actuals via pre-existing `backtest_results` param; LLM cost unchanged; 4+8 retrofitted tests); #1
  atomic `_write_state` (tmp+`os.replace`) + `judgment_store.py` → `SQLiteBackend` (`:memory:` for
  `path=None`; zero real callers — dormant risk); #4 walk-forward persisted on same `sweep_runs` row.
- #13 vinu-simulator: fully closed — #1 AST-guard sandbox escape fixed (was `ast.Call`-only; attribute
  escapes via `os`/`subprocess` unblocked); #2 dead `meta.json`/`load_meta()` removed; #5 dead
  `MetricRow`/`SimulateDryRunResponse` removed; #6 coverage (`service.py` 31 tests incl. real
  `dry_run=True` `TypeError` bugfix — missing 3 dataclass fields, zero real callers; `base.py`
  thread-local confirmed, `price_client.py` fan-out + ValueError paths, 15 tests); #3 unindexed
  symbols → `simulation_run_symbols(run_id,symbol)` join table + backfill; #4 bounded per-instance LRU
  (`PriceClient`/`FeaturesClient`, one long-lived instance each; sorted-keys vs ordered-columns
  handled distinctly); 35+31 tests.

### B4. Items #14–#15 (sizing recommendation, backfill)
- #14A composite sizing factors #1–#4: all built (see A7). #14B sweep verdicts: `param_diff_from_winner`
  built (pure diff → `POST /sweep/grid` response via `_serialize_grid`; needs no new collection);
  `rejection_reason` categorization open; persistence table now exists via #3.
- #15 rolling backfill: option (a) built — `days_stale` fresh at read time from `analysis_until`,
  never stored, already on coverage route; option (b) auto-request orchestrator left as larger
  decision.

### B5. Item #16 five autonomy gaps (pipeline trace)
Working path confirmed: planner-worker → `PlannerTriage` K-cap → `LlmStrategyGenerator` (3 drafts,
real angle/feature context) → registry fuzzy-match/create → best → HTTP backtest → evidence back.
- #1 evidence-into-prompt: closed — prompt already pulled `evidence[-3:]`; fix renders full
  `reasoning` for `signal_evidence` kind only (3 tests).
- #2 generation discard: closed — `generation_candidate_store.py` (rounds header + per-candidate rows,
  `code_hash` identity, `chosen` flag; store defaults `None`, `ResearchService` injects real one;
  best-effort; `GET /research/generation-rounds[/{id}]`).
- #3 unified graveyard: closed — read-time `candidate_graveyard.py` over 3 stores (tagged by source,
  ISO-normalized sort, optional registry param) + `GET /research/candidate-graveyard/{symbol}`;
  code_hash→sweep join + blocking-gate wiring deliberately left open.
- #4 fragile dedup: closed — TF-IDF cosine screen (`idea_similarity.py`, same algorithm as news
  `cosine_dedup`, reimplemented) + one-call `check_duplicate_idea()` LLM tie-break ("SMA" vs
  "moving-average" = same; shared-word different ideas ≠ same); LLM "not duplicate" trusted;
  threshold fallback only when LLM absent/fails; `_match_score` removed (19 tests; correction
  recorded that `indicators_used` can't apply at idea-time).
- #5 live ticker discovery: closed — screener current top (intersected with bootstrapped) is per-cycle
  source when configured; seed additive override; fail-open fallback; unranked ticker stops refresh
  (named consequence, not side effect).

### B6. Items #17–#20 (seams, screener, data, indicators)
- #17 seams: fully closed on numbered findings — `raise_on_error` reaches dead `HTTPStatusError`
  handler; blanket `except Exception` → `ImportError` (real `InfrastructureError` surfaces, no silent
  duplicate HTTP rerun); `outcome_status` (`infra_failure|no_strategy_found|passed`) threaded to
  tool response; `_SWEEP_CANDIDATE_TIMEOUT_SEC` computed (worst-case 365.0s + 35s margin, not guessed
  180); contract tests per hop (agent→research vs real pydantic models; research→simulator vs real
  schema); `policy_version` vs `contract_version` naming trap cleared — deterministic schema-hash
  `vinu_infra.contract_version` (ML checkpoint vs schema-drift are different questions); receiver
  echoes live version on every response, pinned in import-based test (no service imports another's
  models in prod). Research↔simulator hop done; agent↔research hop = remaining item #1.
- #18 screener: fully closed — #1 `min_history_bars` on `HardFilterConfig`, enforced in
  `RankerRunner` before scoring (matches Track-1 `min_observations=70`); #2 documented recommendation
  (`min_price=5.0`, `min_dollar_volume=1M` from `seed.py`; no silent default flip); #4 per-function
  verdict (sma/ema/macd duplicated-not-divergent; wma no counterpart; std different feature; `rsi()`
  real divergence fixed index-for-index; no full delegation — no dependency + Series-vs-row mismatch);
  #3 `RejectionRecord` via shared `vinu_infra/rejection_log.py` + `FilterChain` before/after diff +
  `PipelineResult.rejected_samples`; `HardFilterRule` now attaches `veto_reason` (was computed then
  dropped); `RankerSnapshot.to_dict()` now includes `trace` (was stranded one call from API).
- #19 data providers (most serious point-in-time finding): #1 news `sort_ts` conflation fixed to
  `published_at`/`ingested_at`/`publish_time_is_estimated` (dataclass+schema+migration+`enrich_article`
  + round-trip test); #2 + stock-price #1 fixed once as shared `vinu-infra/point_in_time.py`
  (`clamp_to_as_of()`) on `/candles/{symbol}` + `/ticker/{symbol}` (other relative-window routes need
  per-route `as_of` semantics — left as design); stock-price #4 yfinance retry (plain sleep loop,
  8 tests), #2/#5 gap-count + cache-age headers (`X-Session-Gap-Count` 1m-only,
  `X-Cache-Age-Seconds`, same convention as `X-Clamped-To-As-Of`/`X-Data-Empty`); frame-cache
  isolation bug documented (symbol-keyed 30s blind trust; 12 tests); #3 indicator duplication →
  pattern #2.
- #20 tools/angles: #1/#2 ADX/ATR Wilder fixes + tests; #7 `trend_lifecycle` partly deduped
  (`wilder_smooth` shared; true-range → `vinu-tools.true_range()` index-identical); #4 already-fixed
  elsewhere (re-checked, not assumed); #6 blessed path documented (`apply_indicators()` in
  `vinu-tools/AGENTS.md`); #5 vectorization scoped (18/28 loop modules; rolling-window = lower risk,
  path-dependent smoothing = higher risk + persisted-comparability check; deferred on instruction);
  6th instance (`snapshots.py` ~90-line private RSI/MACD/ATR/ADX with real divergences) deliberately
  unfixed — persisted KNN library must stay comparable forever; needs migration decision
  (recompute/version-tag/freeze), not wiring.

### B7. Item #21 five cross-cutting patterns
- #1 no server-side point-in-time: fixed once via shared `clamp_to_as_of()` (plain function, not
  decorator — route shapes differ too much); two fittable routes wired; rest need per-route design.
- #2 indicator duplication (4 instances + 5th/6th found later): instances all fixed or deliberate
  non-fix (see B6); root cause (`get_indicator_module()` blessed-path enforcement) = remaining item #2.
- #3 silent rejection discard (3 + live-decision 4th): shared `vinu_infra/rejection_log.py`
  (`RejectionRecord`/`record_rejection()`, exact spec shape) + all three named instances fixed
  (screener first; portfolio `allocation_history.py` reuses computed tilts as heuristic attribution,
  documented as such; generation store new with opposite persistence default — see B5); sweep
  comparison fixed independently (ranking table ≠ rejection log); `LiveDecisionRecord` keeps own shape
  (no stylistic retrofit). Pattern fully addressed on named instances.
- #4 yfinance bypassing shared retry: both instances fixed (agent fundamentals + stock-price provider).
- #5 three disconnected evidence streams: partially unified — Track-1→registry bridged, generation
  graveyard queryable, reflection brain+consumer built; full single-ingest contract still open
  (see B10).

### B8. Items #22–#24 (strategy, portfolio, live — highest stakes last)
- #22 strategy: #1 silent degraded weights fixed; #2 NaN/inf/allow_short gate; #5 false unknown-method
  warning; #6 atomic reload (single swap); #7 `clients/base.py` lock dropped (`httpx` thread-safe);
  #8 `timing.py` 10 tests; #3 point-in-time at strategy layer built (`as_of` from
  `POST /strategies/{name}/evaluate` → `evaluate()` once per run → `FeaturesClient` → tools →
  stock-price enforcement; default now, unchanged for callers); #4 schema→dispatcher wiring open
  (bigger decision).
- #23 portfolio: fully closed — #1 net decided (only realizable single-account policy; not duplicated
  in portfolio — would corrupt strategy-keyed tilts; `_detect_symbol_conflicts` gains
  severity/gross_weight + severe → `/notify/symbol-conflict`); #2 halve/flat consumed; #3 risk-tiering
  consumed; #4 agent-unreachable escalates; #5 `allocation_history` why-unfunded via `RejectionRecord`;
  #6 confirmed fine.
- #24 live (CRITICAL): all 3 fixed — #1 `LiveScheduler` constructs `BookBackend`+`BreakerState`, calls
  `check_limits()` pre-order (same shape as orchestrator, real cross-process halt; `covariance=None`
  skips aggregate-VaR only — named gap); #2 `_net_by_symbol` pre-instruction (provisional default,
  opposite-sign warning); #3 drift streak alert (`RECON_DRIFT_ALERT_CYCLES=3` guessed like #23,
  edge-triggered, `target_weight_drift` action reusing notify route with `expected/actual/drift_pct`).

### B9. Item #25 cross-check + reflection brain (steps 8–9)
- Q1 data-freshness vs self-confidence: separate axes, both needed.
- Q2 two evidence pipelines: Track-1→registry was broken (now bridged); maturity→prompt was the one
  working end-to-end even then (now extended to risk + live-decision + capital).
- Q3 autonomy vs confidence: separate; neither substitutes.
- Q4 step-8 synthesis agent: strongest candidate (real unconsumed `reflection_beliefs`); built
  2026-09-27 narrower-than-vision honestly — Layer-0 only (no Hindsight client exists anywhere);
  6-axis profile = 6 analyst clusters (healthy/degrading/insufficient_evidence, one LLM call,
  belief-rows only); `reflection_synthesis_outcomes` 12-col exact spec; `brain.py`
  (`gather_synthesis_inputs` pure, `run_synthesis` fails-open, `resolve_pending_syntheses`
  mechanical not LLM-graded, threshold-nudge only checkable, rest inconclusive); opt-in
  `brain_synthesis_enabled`, hourly worker; never orders/kill-switch; 24 tests.
- Q5 table overlap: zero (checked both directions) — build both sets.
- Step 9 consumer: built 2026-09-28 scoped to Planner/research-team `idea_generator`
  (`vinu-reflection serve` :8092 read-only `GET /reflection/synthesis/latest|pending`;
  `get_reflection_synthesis` HTTP-only, no in-process fallback — circular dep both directions;
  Planner = `planner_worker_main` triage → research team, documented honestly; 13+4 tests;
  reflection suite runs clean first time, 192 passed). Risk/capital consumers unwired (same endpoints
  serve them when wanted). Exit-mechanism point-1 confirmed real, then built (see B10).

### B10. Item #26 honest answer + synthesis follow-ups
Verdict was **no** — well-built components, broken seams. Then every ready-to-build seam was built:
exit mechanism (worse-than-reported second-cycle force-close fixed via open-positions table);
live ticker discovery; unified graveyard; present-data snapshots; precondition write-back
(`PreconditionStateStore` separate table — never YAML — overlaid at read time;
`POST /strategy/strategies/{name}/precondition-check` 404-guarded; EXECUTE+SKIP count as tested;
best-effort; singleton test-isolation gap found+scoped-fix; 18 tests; point 6 fully closed);
strategy-layer `as_of`; evidence-confidence sizer closing #4's blocker (#10 not closed until
`MoveEvidenceStore` + reconciler — then built scoped: unconditional per-candle `detect_move()`,
store + `list_unconfirmed_moves()` join, writer gap closed via auto-derived names); regime sizer;
tool caching + 7/8 coverage files; drawdown sizer (all four #14A factors now: evidence+regime+
drawdown this session, correlation pre-existing); pattern #2 final instance
(`query/indicators.py` → `vinu-tools.compute`, 4 tests, 139→143, no migration risk — in-memory
DuckDB only); Step 9; one-hop contract stamp; SignalEvidence writer (closes #10 loop: genuine
`track1_only` vs `track2_only` now distinguishable).

### B11. Strategy-definition schema (03, 8 fields)
1. must/supporting "why" (falsifiable, checked vs Track-1 once wired). 2. `hypothesis_id` link
   (kills fuzzy `_match_score` fragility). 3. `risk_management` (per-trade stop/take/risk% +
   `sizing_profile` vol/evidence/regime/correlation flags; distinct from pipeline `risk: normalize|
   none`). 4. precondition/postcondition with `defined`/`tested` split (Track-2 PRE/POST as claims;
   point 6 write-back now real). 5. two-level `failure_definition` (trade-level invalidation vs
   strategy-level retire → `reject_with_reason()`; never conflate). 6. `performance_record` as
   references only (hypothesis/signal/move/sweep IDs; no duplication). 7. `origin`+`schema_version`
   (agent/human, run/candidate slot; hypothesis-change version distinct from angle `policy_version`
   and schema `contract_version`). 8. `expected_regime` + `news_sensitivity`
   (exclude/include/target per strategy). Design-only reference; storage home, `tested`-flip rule,
   and strategy-level stats bar depend on Phase-3 analysis layer (still missing) — not decided.

### B12. Reverse-engineering 9 points (live-decision loop end goal: precondition-true-right-now +
  last-N evidence → safe decision → execution)
1. schedule (`StrategyConfig.schedule`) — pre-existing. 2. candle-close poller (`CandleClosePoller`,
   watermark on real latest bar not clock, `live_poll_cursor(ticker,timeframe)`, shared fetch,
   `live-decision-cycle/worker`) — built. 3. live detector (`compute_live_snapshot` via blessed
   `apply_indicators` + derived ratios, `warmup_bars_for_features` sizing, `bars_client`) — built;
   divergence risk managed by shared implementation. 4. stage tracker (`must_not_fired→
   fired_awaiting_confirmation→ready_to_execute→executed/expired`, `strategy_stage_state` +
   transitions + `last_snapshot` persisted) — built. 5. deciding agent (`get_live_decision_context`
   one-call tool: stage+snapshot+precondition+evidence+past-decisions; `live_decision_agent` team,
   no execution tool by omission; `POST /agent/live-decision/run` via `run_team_once`; once-per-fresh-
   ready trigger, fail-logged retry; `LiveDecisionRecord` append-only incl. error/unrecognized;
   `GET /live/decisions/...`; prompt uses history anti-flip-flop) — built. 6. precondition
   defined/tested — fully built (see B10). 7. execution handoff (option-1 fold into
   `LiveScheduler.target_weights` via `live_decision_position_size` default 0.0 unsized; gains
   breaker+netting free; unsized = marked-applied+loud-log, fetch-fail = retry; open positions
   re-emitted every cycle from stored size; review cadence re-invokes same team in review mode;
   HOLD keeps, EXIT closes via existing not-targeted→close rule) + #24 fixes + deployment wiring
   (`entrypoint.sh`, `depends_on quant-core-api`) — built. 8. architectural home (poller/detector/
   tracker in `vinu-live`, agent in `vinu-agent`, HTTP contract) — built as designed. 9. bucket table
   (Layer-4 probabilistic trust number) — deliberately deferred, undesigned: zero accumulated rows to
   validate edges/gating/weighting against; agent works off honest raw counts + qualitative
   `confidence_note` meanwhile; revisit on data volume, not date (same rule as `FORWARD_HORIZON_BARS`,
   `floor_multiple`, grace length).

### B13. Explicitly left (05, 3 items) + deferred decisions
1. agent↔research contract stamp (identical pattern to done hop). 2. indicator root cause
   (`get_indicator_module()` documented/enforced, AGENTS.md/lint). 3. `trade_plan_tool.py` coverage
   (~24 methods; own session). Deferred, not gaps: L2 depth (paid tier), crypto on-chain (no
   consumer), mandatory debate gate (declined for latency), REDUCE/ADD sizing, unrealized-P&L/
   confidence for reviewer (needs bucket table), sweep→generation code_hash join, graveyard as
   blocking gate, other-route `as_of` semantics, full 30-angle live snapshots, agent↔research stamp.

---

## PART C — Unified vision (what the system IS when all above holds)

A decision + risk + execution intelligence platform, not a predictor. WAIT-first, regime-first,
confluence-gated, EV-positive after costs, adversarially debated, deterministically risk-capped,
intelligently executed, continuously re-evaluated against a stated thesis with invalidation + time
stops, portfolio-aware (netting, correlation, drawdown, maturity-scaled), kill-switched, fully
audited, and learning closed-loop (hypotheses versioned, evidence unified, degradations detected,
thresholds recalibrated, syntheses consumed). Maturity (`cold_start→mature`) scales confidence
language, prompt weighting, risk limits, and deployable capital — opt-in, fails open, evidence-
backed, never a substitute for the underlying gates. The plan lives in the seams: every signal,
rejection, decision, drift, and consultation is recorded once, queryable everywhere, point-in-time
safe, single-implementation sourced, and never silently dropped.

Recheck 1: all 18 should-be + 17 will-trade + already-built deltas present. Reccheck 2: all 26 items,
8 schema fields, 9 reverse points, 5 patterns, 3 remaining, all 2026-09-28 builds with caveats
present. No case omitted.
