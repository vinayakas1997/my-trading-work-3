# Sweep Grid - 7 Inefficiencies + All Timeframes Check (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
Window: `VINU_STAGE1_START_DATE=2022-01-01` (Full)
Related files: `01` to `06` stay as is. This is `07`.

---

## Timeframes check - how many angles per format (one ticker)

- 1min = 28 angles (all support 1min)
- 5min = 28 angles
- 15min = 28 angles
- 1H = 28 angles (dlinear 1H 8309 ok, trend works on 1H)
- 4H = 28 angles
- 1D = 27 angles (27/27 done, not 27/28. trend has no 1D by design)
- 1W, 1M, 6M = 1 angle only (backtesting_44_metrics extra)

Total one ticker all formats where supported = 167 + 3 = 170 runs.
3 tickers AAPL, MSFT, NVDA = 510 runs for full coverage.
Today sweep runs only 1d. Other 5 formats never swept. See No.1 below.

---

## No.1 - Grid search only for 1D, not other formats

What: Sweep runs only `1d`. `1H, 4H, 15min, 5min, 1min` never run.
Proof:
- `vinu-components/vinu-agent/teams/research/agents/backtest_runner/prompt.md:12` says use `interval="1d"`.
- `vinu-components/vinu-research/vinu_research/config.py:67` default `interval 1d`.
- `run_parameter_sweep_tool.py` has no interval choice. Uses same `1d`.
Effect: If edge is intraday, system will miss it. AAPL 1D STOP does not mean 1H STOP.
Fix: Add interval to sweep. Run `1d` first, then `1H` if needed. Keep `1D 27/27`, `1H 28/28` report.
Status: Open.

## No.2 - Your custom strategy gets single test, no grid

What: Your thesis in own words goes to raw code path. Then `run_backtest` tests 1 time only. No grid. No optimal search.
Proof:
- `idea_generator/prompt.md:40` tells RECIPE or raw single code. No `base_code` grid instruction.
- `run_parameter_sweep_tool.py:40` has `base_code` mode built (vary 1 param of your code), but prompt never tells LLM to use it.
Effect: Your `MACD + rsi` mix gets 1 Sharpe only. Lucky or unlucky, no ranking.
Fix: Force LLM to make `base_code + param_name + coarse param_grid` when raw path is used. Example: `rsi_period 10, 14, 20` in one call.
Status: Open.

## No.3 - Grid level small and slow, need vectorbt

What: Today grid is 3 points, 190s, one by one loop. Example: `fast 5 slow 30`, `fast 10 slow 40`, `fast 20 slow 60`.
Proof:
- `vinu-components/vinu-research/vinu_research/sweep_grid.py:37` max is 20 per round, but today uses 3.
- Slow loop `run_sweep_candidate` one by one. No vector parallel.
Effect: 5 tries = 15 min. System stops at 1 try. Always `crossover`.
Fix: Adopt vectorbt logic. Test 10 to 20 points together in about 10s. Same rank, same PBO, same walk_forward. Only speed changes. Then 2 to 3 rounds = 30 tries in 30s.
Status: Open. See `03-vectorbt-not-connected.md`.

## No.4 - base_code mode built but prompt link missing

What: Code exists, wiring missing. Same root as No.2, but separate file link point.
Proof:
- Code: `vinu-components/vinu-agent/vinu_agent/tools/run_parameter_sweep_tool.py:40` supports `base_code + param_name`.
- Prompt: `vinu-components/vinu-agent/teams/research/agents/idea_generator/prompt.md:40` never mentions `base_code`. Only RECIPE or raw single.
Effect: Custom strategy never gets grid even though engine can do it.
Fix: Add 5 lines in prompt. Tell LLM: if raw code, also give `param_name` + 3 to 5 coarse values for one key param. Manager forwards to sweep.
Status: Open. Quick fix, one file.

## No.5 - Single lucky win can still PASS

What: If only 1 of 3 grids succeeds, `PBO` is null. If data is short, `walk_forward` is null. Today null is allowed as "no proof", not auto FAIL.
Proof:
- `vinu-components/vinu-research/vinu_research/sweep_grid.py:39` needs 2+ candidates for real PBO. Below that returns neutral, not error.
- `backtest_runner/prompt.md:53` says null PBO is informative, null walk_forward is not auto FAIL.
Effect: 1 lucky Sharpe can go to risk_critic. Overfit risk hidden.
Fix: Require 2+ succeeds for PASS. If only 1 succeeds, SELF-VERDICT FAIL. State completeness + null reason plainly.
Status: Open.

## No.6 - Planner picks recipe by count, not by angles

What: Planner triage picks start recipe by rotation. Not by `kronos up` or `rsi oversold`.
Proof:
- `vinu-components/vinu-agent/vinu_agent/agent/planner_triage_hook.py:143` does `len(existing) % len(recipes)`.
- Comment says real angle-driven matching is `idea_generator` job downstream. Hook only picks start point.
Effect: Start is often wrong. `idea_generator` must fix later, but today it also picks `crossover` always. So wrong start stays wrong.
Fix: Pass summary `agree/diverge` + 1 top angle to planner. Pick fit: momentum angle -> momentum recipe, mean-reversion angle -> rsi recipe. Keep rotation as fallback only.
Status: Open.

## No.7 - K-cap 3 blocks your human thesis

What: Gate allows 3 distinct candidates per ticker per cycle. Auto 3 tries can fill cap. Then your good human thesis is blocked.
Proof:
- `vinu-components/vinu-agent/vinu_agent/agent/thesis_intake_gate.py:21` K_CAP_DEFAULT = 3.
- `submit_thesis_tool.py:120` returns `blocked_by_thgate` when cap reached. Same shared counter as planner `planner_triage_hook.py:104`.
Effect: Your thesis waits one full cycle even if better than auto tries.
Fix: Priority human first, auto second. Or separate cap 3 human + 3 auto. Or allow human to replace weakest auto PEND. Small change, one file + test.
Status: Open.

---

## What is NOT inefficiency (present correct, keep as is)

- `completeness 0.95` check is good. Never pass on half grid.
- Rank by deflated Sharpe is good. Not raw Sharpe.
- Validation always on 0.7s is good. Monte Carlo + bootstrap + walk_forward in same call. File `vinu_agent/tools/backtest_tool.py:103`.
- Shadow paper store now SQLite persistent. File `vinu_agent/broker/performance_store.py:12`. Restart does not wipe 5 days. G2 fixed.
- THGATE cheap gate before LLM is good. Saves cost. Jaccard simple is ok for now.

---

## Order to fix (one by one, fastest value first)

1. No.4 prompt link for `base_code` (1 file, quick, helps your custom strategy directly).
2. No.2 custom grid via LLM coarse grid (same area as 4, together).
3. No.3 vectorbt fast 10s (bigger, unlocks 5 tries + PBO).
4. No.5 require 2+ succeeds (1 line rule, stops lucky PASS).
5. No.1 add `1H` sweep after `1d` PASS (needs interval plumbing).
6. No.6 planner angle fit (needs summary pass-through).
7. No.7 human priority cap (needs gate rule change).

Next: pick 1 to fix. I suggest 4 + 2 together first.
