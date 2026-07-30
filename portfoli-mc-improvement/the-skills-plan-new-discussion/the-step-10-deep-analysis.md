# Step 10, substeps 2-4: Regime-read, outcome-memory, probability-weighted daily allocation

## Context

Step 10 (Focus 3) is the last item in the 10-step implementation plan for this
agentic quant trading system. Substep 1 (re-confirm the baseline) is done —
in the process a real bug was found and fixed in `allocate_risk_parity()`
(it was computing "volatility" from a correlation matrix instead of actual
returns). Substeps 2-4 ask for a **resolved design** of: (2) which of
`vinu-initial-analysis`'s 11 angles constitute a regime read and how to query
it, (3) where "yesterday's actual performance" is read from, and (4) the
probability-weighting model itself — explicitly flagged in the plan file as
"the core research question of this step."

Per this session's established pattern (every prior step produced real
code + tests + a skill doc, not just prose), this plan builds a genuine,
working v1 rather than only a design document — while being explicit that
the probability-weighting formula is a defensible first cut, not a solved
research problem, consistent with the plan's own "progressive... improves
as outcomes accumulate" framing.

**Deliberately out of scope**, per substep 5 and the live-safety doc: no
wiring into a background scheduler and no path to real capital. The new
logic is exposed as an on-demand route + CLI command only — mirroring the
codebase's own precedent (`vinu_research/cli.py::promote_scan_main`, which
stays a manually-invoked command specifically because "auto-promoting... is
a bigger consequence than auto-triggering more research," not a silent
loop). Allocation-weight changes are comparably consequential.

## Key findings from research that shape the design

1. **`regime_analysis` (the one true regime-classifying angle) does not
   expose a "current regime" scalar.** Read in full:
   `vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/compute.py`.
   Its stored output is a **window-aggregate**: for the whole analyzed
   history it buckets days into bull/bear/high_vol/sideways and reports
   per-bucket stats (win rate, Sharpe, `pct_of_time`) plus an unordered
   transition-count table — there is no row meaning "today's/yesterday's
   regime is X." Pulling "the current regime" out of this angle's stored
   parquet rows isn't possible as-is.
   **Resolution:** reimplement the angle's own `classify_regime(ret, vol,
   vol_thresh)` thresholding (bull/bear/high_vol/sideways, same 21-day
   rolling vol window, same 0.7 quantile threshold) directly in
   `vinu-portfolio`, applied to just the most recent observation of a
   benchmark symbol's returns. This mirrors real, working logic already
   proven in the codebase rather than inventing a new classifier, and is
   documented as a deliberate reimplementation (with the reason above) in
   the new skill doc, not a silent duplication.

2. **`tags.yaml`'s regime vocabulary (`trending`/`ranging`/`mean_reverting`)
   does not match `regime_analysis`'s vocabulary (`bull`/`bear`/`high_vol`/
   `sideways`).** No code anywhere reconciles these two taxonomies today —
   confirmed by grep, `strategy-tags/SKILL.md`'s matching rule is prose for
   an LLM to apply, not executable. This design adds one explicit mapping
   constant and documents the ambiguity (bull/bear both plausibly mean
   "trending"; tags.yaml doesn't encode direction) rather than pretending
   it's a clean 1:1 match.

3. **Outcome-memory: reuse `vinu-research`'s `calibration_entries` table
   (`vinu_research/storage/strategy_store.py`), don't build new storage.**
   It's real, keyed by `artifact_id` (matches how `vinu-portfolio` already
   identifies LLM strategies), and already wired end-to-end: `vinu-live`'s
   `FeedbackLoopWorker` posts realized returns to `vinu-research`'s
   `POST /research/trade-plan/{artifact_id}/record-outcome` on every
   closed position with an `artifact_id`. **Gap:** no GET route exists to
   read it back. **Also a real, documented limitation, not silently
   inherited:** this only populates for `type == "trade_plan"` artifacts.
   YAML strategies (`vinu-strategy`'s registry) have **zero** outcome
   tracking anywhere in the codebase — confirmed via `MetaStorage`'s schema
   (`name, description, schedule, enabled` only). The design must treat
   these as "untracked," not silently assume a value.

4. **Still true, unaddressed by this design, and explicitly flagged rather
   than hidden:** `ShadowEvaluator` (Stage 2 of the live-safety chain) never
   runs, so no ACTIVE strategy has been paper-validated. This design uses
   calibration track-record (finding #3) as a rough, weaker proxy for "has
   this strategy been checked against reality since promotion" — a
   documented partial mitigation, not a fix for the underlying gap.

5. **`vinu_portfolio/sizing.py`'s `apply_position_sizing()` /
   `vol_targeting_position_size()` are real, tested-shape-compatible, dead
   code** — never called from anywhere in `vinu_portfolio`. This design
   wires them in as the final step of the new allocation pipeline (turning
   % weights into $ position sizes), closing another "built but never
   called" gap in the same spirit as this session's earlier fixes.

## What gets built

### 1. `vinu-research`: one new read route (small, additive)

- `vinu_research/server/routes_trade_plan.py`: add
  `GET /trade-plan/{artifact_id}/calibration`, returning
  `compute_calibration(store.get_calibration_entries(artifact_id))`
  (`CalibrationResult`: `n_entries`, `accuracy`, `brier_mean`,
  `magnitude_mape`, `passed`) as JSON. Reuses `forecast_skill.py`'s
  existing `compute_calibration()` — no new computation logic.
- Test: extend `vinu-research/tests/test_routes_trade_plan.py` with a case
  covering an artifact with recorded outcomes and one with none.

### 2. `vinu-portfolio`: the core of substeps 2-4

- **`vinu_portfolio/regime.py` (new)** — `classify_current_regime(returns:
  pd.Series) -> dict`, a direct, documented port of
  `regime_analysis/compute.py`'s own `classify_regime` thresholding
  (21-day rolling vol, 0.7 quantile threshold, same bull/bear/high_vol/
  sideways labels), applied to the latest observation only. Returns
  `{"regime": ..., "as_of_return": ..., "as_of_vol": ..., "n_observations":
  ...}` or an `insufficient_data`/`no_data` status dict matching the
  angle's own status vocabulary for consistency.

- **`vinu_portfolio/config.py`** — add `analysis_api_url` (default
  `http://127.0.0.1:8083`, same default `vinu-research` uses for this
  service), `stock_api_url` (default `http://127.0.0.1:8081`, matching
  `vinu-stock-price`'s real default), `benchmark_symbol` (default `"SPY"`),
  `regime_tilt_bound` (default `0.3`), `outcome_tilt_bound` (default
  `0.3`), `min_calibration_entries_for_tilt` (default `5`), `tags_path`
  (default pointing at `project-understanding/skills/strategy-tags/
  tags.yaml`, resolved relative to repo root, overridable via env var) —
  all following the existing `from_env()` / `VINU_PORTFOLIO_*` pattern
  already in this file.

- **`vinu_portfolio/service.py`** — add to `PortfolioService`:
  - `_fetch_benchmark_regime()` — `GET {stock_api_url}/stock/candles/
    {benchmark_symbol}` (same route shape `vinu-research`'s
    `get_benchmark_data` already uses), computes returns, calls
    `classify_current_regime`. Fails open (returns `None`/`status:
    unavailable`) on any error — this is a weighting tilt, not a safety
    gate, so it must never block allocation the way `OrderGuard`'s checks
    correctly do block orders.
  - `_fetch_outcome_confidence(strategy)` — for `kind == "llm_python"`:
    calls the new calibration route; returns the accuracy + n_entries if
    `n_entries >= min_calibration_entries_for_tilt`, else an explicit
    `"insufficient_data"` marker. For `kind == "yaml"`: always returns an
    explicit `"not_tracked"` marker — never fabricates a value.
  - `_regime_alignment_multiplier(strategy_name, regime)` — loads
    `tags.yaml` once (cached on the instance), maps `regime` to the tag
    vocabulary via one explicit constant (documented per finding #2),
    returns a bounded tilt (`1 ± regime_tilt_bound`) on overlap/mismatch,
    or neutral `1.0` when the strategy has no tags entry or regime is
    `high_vol`/unavailable (no directional tag dimension to compare).
  - `_outcome_confidence_multiplier(confidence)` — linear map of accuracy
    `[0,1]` to `1 ± outcome_tilt_bound` around neutral at `accuracy=0.5`;
    neutral `1.0` when untracked/insufficient — a new/untracked strategy
    keeps its risk-parity base weight, it isn't penalized for lacking data,
    matching `allocate_risk_parity`'s own existing "fall back to neutral
    when data is missing" convention.
  - `compute_daily_allocation()` — orchestrates: run `build_portfolio()`
    for the base weights (reuses the now-fixed risk-parity calc as-is, no
    changes to it), fetch regime once, fetch each strategy's outcome
    confidence, apply both multipliers to `target_weight`, renormalize to
    sum to 1.0, then fetch live equity from `GET {agent_api_url}/agent/
    broker/account` (the exact same call `drawdown_scheduler.py` already
    makes) and — only if that succeeds — run the result through
    `sizing.py::apply_position_sizing()` for `position_size` in dollars.
    Returns full transparency per strategy: `base_weight`,
    `regime_multiplier`, `outcome_multiplier`, `target_weight`, optional
    `position_size` — not just the final number, so the reasoning is
    inspectable (matches this project's "skills are a knowledge library,
    agent should understand why" philosophy).

- **`vinu_portfolio/server/app.py`** — add `GET /portfolio/daily-allocation`.
- **`vinu_portfolio/cli.py`** — add a `daily-allocation` one-shot subcommand
  (mirrors `build_main`'s existing shape). **Not added to `entrypoint.sh`**
  — on-demand only, by design (see Context).

- **Tests** (following this session's established
  `asyncio.run(...)` + `AsyncMock`/`MagicMock` pattern, no new test
  dependency):
  - `vinu-portfolio/tests/test_regime.py` — deterministic bull/bear/
    sideways/high_vol/insufficient_data cases for `classify_current_regime`.
  - Extend `vinu-portfolio/tests/test_service.py` — `_fetch_benchmark_regime`
    (success + failure-open), `_fetch_outcome_confidence` (llm_python with
    data / insufficient data, yaml always untracked),
    `_regime_alignment_multiplier` (aligned / mismatched / untagged /
    high_vol-neutral), `_outcome_confidence_multiplier`, and
    `compute_daily_allocation()` end-to-end with mocked HTTP, including a
    case with no equity available (weights only, no `position_size`).

### 3. New skill doc (matches every prior step's deliverable shape)

- `project-understanding/skills/daily-allocation/SKILL.md` — documents:
  why regime is self-computed rather than read from the `regime_analysis`
  angle's stored output (finding #1), the tags.yaml/regime vocabulary
  mapping and its documented ambiguity (finding #2), the outcome-confidence
  source and its trade_plan-only/YAML-blind-spot limitation (finding #3),
  how this design partially — and only partially — compensates for
  Stage 2/`ShadowEvaluator` never running (finding #4), and the deliberate
  choice to keep this on-demand rather than scheduled.

## Plan/tracking file updates

- `10-focus3-portfolio-intelligence.md`: substeps 2-4 marked done with
  findings + what was built; Definition of Done checklist items 2-3
  checked; status stays `In Progress` (substep 5 — confirm against
  live-safety doc before any live wiring — is explicitly a human/design
  checkpoint, not something this pass can self-certify).
- `AGENTS.md`: new dated entry under `10-focus3-portfolio-intelligence`
  documenting files touched, tests run, and the findings above — same
  format as every other entry this session.

## Verification

- `pytest vinu-research/tests/test_routes_trade_plan.py -q` — new route test passes.
- `pytest vinu-portfolio/tests/ -q` — new + existing tests pass, no regressions.
- Full cross-service run (`pytest -q` in each of the 10 service dirs) —
  confirm no regressions anywhere, matching the tally already tracked in
  AGENTS.md (1382 passed / 3 skipped before this change).
- Manual smoke check: with `vinu-portfolio serve` and its dependent
  services running locally, hit `GET /portfolio/daily-allocation` and
  confirm the response shape (regime + per-strategy multiplier breakdown +
  weights) is sane against whatever strategies/artifacts exist locally.
