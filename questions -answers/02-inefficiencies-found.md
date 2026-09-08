# Inefficiencies Found - From Discussion (2026-09-08)

Simple English. You can read any time.

## 1. LLM 400 - No user query (Fixed)
What: Research failed at iteration 15. Error `400 No user query found in messages chat:79`.
Why: Compaction in `loop.py` removed user message. Only system + tool left.
LLM needs at least one user. So it failed.
Fix: Keep user in `_auto_compact` + guard in `_call_llm`. File `vinu-agent/vinu_agent/agent/loop.py`.
Image `agent-api 8e1c13d` rebuilt 06:24. Now NVDA gives 200, not 400.
Status: Fixed.

## 2. Idea generator always crossover (Open - critical)
What: Always `RECIPE: crossover fast 5 slow 30`. Never tries RSI, Bollinger, MACD+RSI mix.
Why: Prompt `idea_generator/prompt.md:40` says recipe-first. It picks first fit.
No diversity rule. Raw code path rarely used.
Effect: `angles_used []`, Sharpe -1.06, STOP. No effective search.
Next: Make prompt mature. Force diverse recipe on iter 2+. Allow raw MACD+RSI combining.
Status: Open, juncture 1.

## 3. 28 angles computed but not used (Fixed partly)
What: 27 angles ready `kronos 1125 ok`, but research said `angles_used []`.
Why: `get_all_angles` read old tier2 2026 `no_data`. Not tier3 2022 `ok`.
Fix: `angles_tool.py` now tries v1 tier3 `2022-01-01_2026-07-01` first. Restart 06:51.
Now `27 with_data ok`.
Status: Fixed wiring, need verify next research uses it.

## 4. Only 1 iter, not 5 + no PBO (Open)
What: AAPL 1 iter MACD STOP. MSFT STOP. NVDA fail. No 5 iters.
No `deflated 0.95, holdout 20%, walk_forward 3, PBO, stress 2020/2022, completeness 0.7`.
Why: Stopped early due to 400 + STOP + K-cap block. Slow loop 190s per try.
Next: Diverse prompt + fast sweep (vectorbt) + 5 iters.
Status: Open, juncture 3.

## 5. Simulator circuit flap (Open)
What: AAPL 102 trades ok. MSFT same time says `simulator down or circuit open`.
Why: Circuit breaker flaps. Health is ok but tool call fails.
Effect: MSFT STOP with no metrics.
Next: Check circuit retry, timeout 30 to 10s, retry logic.
Status: Open.

## 6. dlinear CUDA OOM (Fixed)
What: `dlinear` error `CUDA out of memory` on Full 1125 bars.
Why: Tried GPU on shared host. Model is tiny (<1k params).
Fix: Force CPU `torch.device(cpu)` in `dlinear/compute.py`. Live via bind mount.
New trigger 1H 8309 obs ok 06:42.
Status: Fixed.

## 7. trend_session_structure 1D confusion (Clarified)
What: Showed as `27/28 err`. Looked like inefficiency.
Why: By design it has no 1D. Only `1min,5min,15min,1H,4H`. Needs session info.
Fix in report: Say `27/27 for 1D done`. Say `28/28 for 1H done`. Not error.
Status: Clarified, not a bug.

## 8. Initial image 6.52 GB heavy (Open - low priority)
What: `initial-analysis-api 240afd8cc 6.52 GB`.
Why: Torch + transformers + chronos + timesfm. Code only 3.5 MB.
Models are already dynamic `data/models:/models:ro`, not in image.
Next: Slim with CPU torch, no dev, no-cache. Warm models once on host.
Status: Open, keep as is for Full run.

## 9. Kronos fallback proxy (Known)
What: `fallback_reason: Kronos weights unavailable, OSError 30 Read-only`.
Uses small MLP proxy, not real pretrained.
Why: Weights not downloaded or read-only mount.
Effect: Forecast works but not real Kronos.
Next: Warm `data/models` on host before up.
Status: Known, not blocker.

## 10. Planner K-cap block, no new research 23 min (Open)
What: Planner cycles every 60s `complete`, but no new team_run after 05:51.
Why: Prior STOP + shared K-cap + summary not refreshed.
Effect: Stage 4 to 7 blocked, no PEND to ACTIVE.
Next: After prompt fix, force new idea with different recipe.
Status: Open.

## 11. Reporting 27/28 shows false inefficiency (Fixed in rule)
What: We said `27/28` for 1D. User said say `27/27`.
Why: 1D expects 27. 1H expects 28.
Rule now: Report per format expected count.
Status: Rule set.

## 12. No shadow / monitor yet (Blocked)
What: No ACTIVE, no paper 5 days, no monitor hold/exit.
Why: Blocked by 2,4,5 STOP.
Need: PASS -> PEND -> ACTIVE -> shadow -> monitor.
Status: Blocked, juncture 5.
