# Prompt Building vs Initial Analysis - Used or Not (2026-09-08)

Simple English.

## Question: In prompt building, is initial analysis taken in consideration or not?
Answer: Yes in prompt text, No in practice today.

Prompt text says yes:
- `idea_generator/prompt.md:10` says Call get_all_angles and ground idea in real data row_count>0.
- `prompt.md:16` says angle for reasoning only, never for code.
- `prompt.md:40` says Why recipe fits: state specific real angle you gathered, e.g. trend up row_count=140.
So words say consider 27/27 1D kronos 1125 ok. Yes in text.

Practice says no, not effective today:
- get_all_angles was reading tier2 2026 no_data, not tier3 2022 ok.
- So 27 computed but angles_used [].
- AAPL 190s STOP, MSFT [], NVDA [].
- Picked crossover fast 5 slow 30 always, not grounded in kronos up.
- This is angle-blind gap 1. Manager not forwarding angle.
- Considered in words, not in result.

## How to make it really taken (plan, not built yet)
1. Wiring done: angles_tool now tries v1 tier3 2022_2026 1day/1H first. kronos 1125 ok, dlinear 8309 ok. Now 27/27 1D ok available for prompt.
2. Prompt mature: recipe-first -> recipe-diverse + raw MACD+rsi combining.
   Require ground in one real angle row_count>0.
   Example: kronos up -> crossover for momentum, RSI oversold -> rsi recipe, else raw code MACD+rsi.
   Write angles_used [kronos,arima] not [].
   If no ground, say so, do not invent.
3. Verify next research AAPL team_run: angles_used not [], and Why fits has kronos up 1125 in text. That proves taken.

## As of now, in which steps used and not used, there need to fix?
Used properly:
- Step 1 Screener: get_all_angles 27/27 ok -> summary. Yes. Fix reporting to 27/27 1D.
- Step 2 Planner triage: reads summary. Yes.
- Step 8 Shadow: reads via calibration when ACTIVE. Yes.

Not used properly, fix there:
- Step 3 idea_generator (AGENT tools get_all_angles): 27 ready but [] . Fix 1: angles_tool tier3 + prompt mature grounded in 1 real angle.
- Step 3 backtest_runner: gets ungrounded idea -> 1 iter crossover always, no PBO. Fix 2: same prompt mature + vectorbt fast 5 tries 10s.
- Step 4 risk_critic: STOP due to Step 3. Will fix when Step 3 fixed.
- Steps 6,7,9 risk, capital, monitor: blocked, no PEND/ACTIVE. Wired but idle. Will run when PASS comes.

Where to fix one by one:
- Fix 1 idea grounded in 1 real angle first (quick, one file prompt.md + angles_tool done). Verify next AAPL angles_used.
- Fix 2 vectorbt fast next (bigger). Do after Fix 1, else vectorbt still tests ungrounded crossover.

Tradeoff: force one angle ground always (clear, angles_used never []) vs optional (sometimes [] ok, looser). Choice: force one angle ground always for Full.
