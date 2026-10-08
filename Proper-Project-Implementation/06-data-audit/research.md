# Data audit: vinu-research

Checked 2026-10-08 on the running stack (`research-api`; `/data` is 78 MB: `research_meta.db`, `strategy_store.db`, `signal_evidence.db`, `sweep_grid.db`, `strategy_validations.db`, `telemetry.db`, `llm_cache.db`, `hypotheses.json`, `llm_calls.jsonl`).

## What triggers it
- **Research run** (`POST /research/run`): the loop writes or takes a strategy, backtests it through the simulator, has a critic judge it, repeats up to the iteration limit, then runs the validation steps and writes a report. Called by the agent and by the validation scripts.
- **Sweep** (`POST /research/sweep/grid`): tries a grid of parameters for a recipe.
- **Signal evidence** (`POST /research/signal-evidence/trigger`): initial-analysis records every time a "must condition" fired and what the price did next.
- **Hypotheses** (`POST /research/hypotheses`): the registry of ideas and their evidence.

## Data items

### X1 Research runs  `research_meta.db: research_runs` (44 rows)
- **Format:** `user_idea, symbol, from/to, status, total_iterations, best_sharpe, best_max_dd, report_md, strategy_code, approved, deflated_sharpe, ...`. All 44 are "validate <SYMBOL> strategy on <bar size>" runs of 1 iteration (AMD 20, MSFT 8, AVGO/CAT/LIN/META 4 each), made between 2026-10-06 and 2026-10-07.
- **Access:** `GET /research/runs`, `/runs/{id}`, `POST /runs/{id}/approve`. **Consumers:** the validation script, agent tools, the bar-validation gate (`bar_validation.py` reads finished runs to decide eligibility).
- **Results (read from the 44 reports):**
  - 24 runs (55%) ended because the strategy's own code crashed; the report said "Fix the error above" and did not contain the error. Fixed (problem-log P64).
  - 20 runs (45%) ran and were stopped by the significance tests. Reasons (a run can have several): block-bootstrap p-value too high 19, BCa bootstrap interval includes zero 17, bootstrap Sharpe interval includes zero 17, placebo test 17, price-path resample 11, trade-permutation 11, walk-forward consistency below 0.6 in 9.
  - 15 of 44 had a positive Sharpe (best 1.30). None passed.
- **Verdict:** `used` (gate, agent); the stored report was `missing its main fact` (fixed).

### X2 Strategy artifacts  `strategy_store.db: artifacts` (3 rows, all DISABLED)
- **Format:** `artifact_id, name, universe, status (CREATED -> ... -> ACTIVE/MONITORING -> DISABLED), signal/entry/exit rules, strategy_code, initial_sharpe, deflated_sharpe, holdout_passed, stress test, ...`. Rows: LIN (research run) and SPY, AAPL (my gatekeeper drill of 2026-10-08).
- **Access:** `GET /research/artifacts`, `/promote`, `/paper-return`. **Consumers:** portfolio (which strategies to allocate), live (6 files), agent (4 files). **Verdict:** `used well` by design, but empty of active strategies, so every downstream stage idles.

### X3 Empty stores (features built, no data)
`strategy_validations`, `iteration_checkpoints`, `research_catalog`, `bench_history`, `decay_snapshots`, `calibration_entries`, `angle_calibration_entries`, `proposed_decay_actions`, `telemetry.steps`, and `research_runs.db` (a file with no tables). Decay, calibration and bench history need an ACTIVE strategy, so empty is expected; `strategy_validations`, `iteration_checkpoints` and `steps` should have rows after 44 runs and do not (DA-X5).

### X4 Sweeps  `sweep_grid.db: sweep_runs` (100), `sweep_grid_points` (530)
- **Format:** per sweep: requested vs succeeded, completeness, PBO and walk-forward JSON; per point: params, score, failure reason.
- **Results:** 219 of 530 points succeeded (41%); 311 failed. Reasons: no weight data (all symbols empty) 87, no numeric `fast_period` to substitute 38, unknown recipe `ma_crossover` 36 and `sma_crossover` 24 (the registry has `crossover`), class `UserStrategy` not found 32, unknown params for a recipe 22. Scores of the successes run 0 to 154.8 (mean 88); the scale is not a Sharpe.
- **Consumers:** agent (3 files) calls it; `GET /sweep/grid` reads back. **Verdict:** `used`, but 59% of the work is thrown away on name mismatches between the caller and the recipe list (DA-X4).

### X5 Signal evidence  `signal_evidence.db: signal_triggers` (8,188), `signal_evidence_indicators` (470,162), 75 MB
- **Format:** a trigger (symbol, time, the must-condition text, bar size) with its forward outcome (max favourable/adverse excursion, return at horizon); the indicator values at trigger time.
- **Spread:** 15min 6,243, 1H 1,714, 1D 231; 50 symbols; **one** distinct must-condition; every trigger has its outcome recorded.
- **Consumers:** research (5 files), live (4: pre-trade check and evidence lookup); initial-analysis writes it. **Verdict:** `used well`; with a single condition it cannot tell conditions apart (DA-X7).

### X6 Hypotheses  `hypotheses.json` (30)
- 24 exploring, 5 validated, 1 testing. **Access:** `/research/hypotheses`. **Consumers:** agent (9 files), live (2). **Verdict:** `used`; five are "validated" while no strategy has passed (DA-X8).

### X7 LLM records  `telemetry.db: llm_calls` (86), `llm_cache.db` (83), `llm_calls.jsonl`
- A log of model calls and a cache. **Consumers:** none found beyond the cache. **Verdict:** `single use` (diagnostic).

## Where research reaches a decision
research -> artifact status (ACTIVE) -> portfolio allocation -> live scheduler. Today nothing is ACTIVE, so this is the stage the whole chain waits on.
