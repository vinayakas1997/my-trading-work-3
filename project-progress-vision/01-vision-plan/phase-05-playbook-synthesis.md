# Phase 5 — Trading Playbook Synthesis (Stage 3)

Status: **not started** · Depends on: Phase 1 (regime/attribution data), Phase 4 (comparison angles) · Blocks: Phase 6

## What it is

Extends the existing `TradePlanTool` into the full live-trading dossier the user described:
for a validated, refined, and critiqued strategy, produce concrete guidance on expected
drawdown and under what conditions it occurs, key risk points to watch for live, entry
conditions split by long vs. short, which news types should make you wait, how to handle
clustered/consecutive news events, and timing considerations (time of day, day of week).

`vinu-agent/vinu_agent/tools/trade_plan_tool.py` already implements a strong partial version:
an Entry Checklist (`_render_entry_checklist`, trend direction, signal confirmation, session
structure, a liquidity check via `_fetch_liquidity_check`, drawdown context), staged
profit-booking tranches by trend strength (`_render_tranches`), and an Exit/Invalidation
checklist (`_render_exit_checklist`: stop-loss, trend reversal, max-drawdown, a Monte Carlo
p-value line via `_fetch_validation`, regime shift, gap risk). This phase adds the missing
sections and fixes the ones that currently render "N/A" because their data source was broken
(fixed in Phase 1) or never wired up.

## Impact

**Before this phase:** The playbook covers entries, tranches, and exits, but has no
regime-conditioned drawdown guidance, no explicit long/short split, no news-sensitivity
guidance, and no timing-of-day/week guidance. Its one Monte Carlo line has always read "N/A"
(fixed by Phase 1, but not yet *displayed* meaningfully until this phase renders it well).

**After this phase:** A trader reading the playbook for an approved strategy sees the full
dossier the user asked for — including any Stage 2 comparison angles as explicit caveats
("this strategy could refine toward X — watch for that regime").

## Where changes occur

All changes are in `vinu-agent/vinu_agent/tools/trade_plan_tool.py`, following the tool's
existing pattern: a `_fetch_*` async helper returning a `status`/`available` dict, feeding a
`_render_*` pure-formatting function, assembled at the tool's main markdown-building call site
(locate where `_render_entry_checklist`/`_render_exit_checklist`/`_render_tranches` are
currently composed before adding new calls alongside them).

- **Drawdown-by-regime section** — new `_render_drawdown_expectations`, sourced from
  attribution data (`attribution["by_regime"]`, already computed server-side by
  `_run_validation_and_attribution` in `vinu-simulator/vinu_simulator/service.py`, but not
  returned by any route until Phase 1 extends `GET /results/{run_id}` to include it) and
  `vinu-simulator/vinu_simulator/engine/regime.py`'s `classify_regime`/`per_regime_performance`
  output. Renders expected drawdown ranges keyed by regime (bull/bear/high-vol).
- **Long vs. short entry condition split** — extend `_render_entry_checklist` to branch
  explicitly on trade direction (checking `allow_short` and whatever directional signal
  thresholds are available from strategy metadata — check `strategy_store`/`Artifact` records
  first; if no structured entry-condition metadata exists there, this needs the underlying
  strategy code's documented conditions, most naturally surfaced via Stage 1's refinement
  reasoning/notes rather than reverse-engineered from raw code at render time).
- **News-sensitivity + consecutive-news handling** — new `_fetch_news_sensitivity(client,
  base_url, symbol)` following the exact same pattern as the existing
  `_fetch_liquidity_check` (lines ~216-270): call whichever service exposes
  `angle_context`/`news_price_causality` data (this data is already used by the risk critic in
  `vinu-research/vinu_research/loop.py` around lines 1283-1296 — confirm the exact serving
  route at implementation time, since it wasn't pinned down by the prior architecture research
  beyond "exists elsewhere"). New `_render_news_checklist` covers (a) news categories
  historically correlated with adverse moves for this symbol, (b) a rule for spacing entries
  around clustered/consecutive same-day catalysts.
- **Timing profile (time of day, day of week)** — new `_compute_timing_profile`, aggregating
  historical trade performance by hour-of-day/day-of-week from backtest trade logs (`GET
  /results/{run_id}/trades`). New `_render_timing_profile` section.
- **Comparison-angle surfacing** — new `_fetch_comparison_angles` querying Phase 4's
  `research_comparisons` table (via whatever HTTP surface `vinu-research`'s service exposes
  for reading it — add a route if none exists yet for this specific read). Rendered as explicit
  caveats/watch-items in the playbook, not silently dropped after Stage 2 runs.

## How to test it

- Unit tests for each new `_fetch_*`/`_render_*` pair, following whatever test pattern already
  covers `_fetch_liquidity_check`/`_render_entry_checklist` (check
  `vinu-agent/tests/` for the existing `trade_plan_tool.py` test file and mirror its mocking
  approach for the HTTP client).
- A test asserting the drawdown-by-regime section is empty/gracefully omitted (not erroring)
  when attribution data isn't available for a given run (e.g. an older run predating Phase 1).
- A test asserting comparison angles from a seeded `research_comparisons` fixture render as
  distinct bullet items in the final markdown output, each retaining its `supporting_evidence`
  reference.
- End-to-end smoke test (manual or scripted): generate a full playbook for a strategy that has
  been through Stages 0–2, and visually confirm every new section renders real data rather than
  "N/A"/placeholder text.
