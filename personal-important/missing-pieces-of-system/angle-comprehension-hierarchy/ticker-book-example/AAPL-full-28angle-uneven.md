# AAPL — full 28-angle book, deliberately UNEVEN input (live LLM run)

**All input data is FABRICATED**, deliberately corrupted from the clean
version (`AAPL-full-28angle-clean.md`) to test whether the prompt/model
handle real-world-shaped messiness — not random noise, five specific,
realistic problem shapes. **The LLM response is real**, same
`hindsight-llm` endpoint, same run, 2026-09-22.

## What was made uneven, and why each shape is realistic

Starting from the clean 28-angle/173-row dataset, five deliberate,
independent corruptions (145 rows remain):

1. **`trend_session_structure` → zero data anywhere** (`row_count: 0`).
   Realistic shape: an angle that simply hasn't run yet for this ticker
   — the same `row_count=0` case every existing checkpoint/trial in this
   project already treats as the baseline "no data" scenario.
2. **Cluster B given asymmetric, non-overlapping coverage**: `chronos`/
   `dlinear`/`moment` truncated to intraday-only (`1min`-`1H`);
   `moirai`/`lag_llama`/`tft` truncated to daily-only (`4H`/`1D`).
   Realistic shape: different models finish their runs on different real
   cadences — nothing guarantees every model in a 14-member cluster has
   the same timeframe coverage at read time.
3. **`kronos` replaced with a real angle-runner failure shape**:
   `{"error": "model checkpoint load failed: CUDA OOM"}` instead of
   data. Realistic shape: a real GPU-memory failure, not a missing-data
   case — distinct from `row_count=0`.
4. **`garch.1min` given a malformed value**: `forecast_volatility: "NaN"`
   (a string, not a float) while every other `garch` timeframe has a
   normal numeric value. Realistic shape: the same "one bad field among
   otherwise-good siblings" pattern checkpoint 01's trial 03 used.
5. **`arima.1D` given a stale-looking duplicate**: `forecast_price:
   171.40` (a real outlier vs. its own `4H` neighbor of 188.85) plus an
   explicit `_note_run_id` flagging it as "3 days stale." Realistic
   shape: a staleness/race condition, not a clean gap — the kind of bug
   `run_id.py`'s traceability work (see the main project's `01-plan.md`
   history) exists to help catch, not something a flat digest would ever
   surface on its own.

Full input: `AAPL-full-28angle-uneven-digest.txt` (145 lines, same
directory). Same prompt/settings as the clean run — see
`AAPL-full-28angle-clean.md`'s "Prompt sent" section, not repeated here.

## Real response received

Converged cleanly, `finish_reason: "stop"`, **17.1s** (faster than the
clean run despite the added complexity of flagging anomalies — the
corrupted dataset is also 28 rows shorter). Full response in
`full_book_results.json` under key `"uneven"`.

## Verdict — the planted anomalies vs. a new one the model introduced on its own

**All five planted anomalies were caught, correctly, specifically:**

1. `trend_session_structure`'s `row_count=0` — correctly excluded from
   synthesis and named explicitly ("Only `trend_session_structure`
   returned `row_count=0` and was excluded").
2. Cluster B's uneven coverage — correctly narrated per-model ("Kronos
   failed to load due to CUDA OOM... Lag Llama/Moirai/Moment relied on
   fallback proxies"), not smoothed over.
3. `kronos`'s CUDA OOM error — quoted correctly and separated from the
   "no data" case, matching this checkpoint-project's own established
   distinction between "errored" and "empty."
4. `garch.1min`'s `NaN` — caught precisely: *"a sharp anomaly where the
   1-minute forecast volatility is `NaN` while all other timeframes
   report valid values"* — correctly localized to the one bad field, not
   generalized to distrust the whole angle.
5. `arima.1D`'s staleness — caught and correctly reasoned about: *"the
   ARIMA daily forecast is flagged as 3 days stale"*, and recommended as
   a next-step check ("Verify the recency of the `arima.1D` data").

This is a genuinely good result for the intended stress test — five
independent, realistically-shaped data problems, all five caught and
described accurately with real quoted values, none smoothed over into a
falsely confident synthesis.

**But a sixth, unplanted problem appeared — a real rule violation, not
a data-quality catch:** Cluster B's synthesis lists *"Chronos, DLinear,
iTransformer, **Kalman Filters**, LPatchTST, LSTM, PatchTST, TFT, Timer
TimerXL, TimesFM, and Tips Regime Aware Transformer"* as the 11
Cluster-B models contributing to the consensus. **`kalman_filters` is a
Cluster A member** — the system prompt's own verbatim cluster list
states this explicitly ("A -- Classical statistical forecasts: arima,
exponential_smoothing, kalman_filters"). The model contradicted an
explicit instruction it was given directly in-context, not an inference
it had to derive. The same run also repeats the clean run's
`timer_timerxl`/`timesfm` fabricated-`direction` issue (neither has a
`direction` field in this data either) — so the "11 of 14" figure is
built from one wrong-cluster member plus two members credited with a
field they don't have, meaning the real, defensible number is smaller
than either 10 or 11.

## Net read across both runs

The model reliably catches **planted, realistic data-quality problems**
(errors, NaNs, staleness, coverage gaps) when they're the kind of thing
its system prompt explicitly told it to watch for — that part of the
design works. But it independently introduces **its own** hallucinations
(miscounting coverage, inventing fields, misassigning cluster
membership) at a similar rate in both the clean and uneven runs,
unprompted by anything in the input. That means the fix implied by
`01-plan.md`'s Step 3 (giving the model a glossary and a cluster scheme)
is necessary but not sufficient — a real per-cluster-membership
double-check or a programmatic validator on the `cluster_digest` output
(e.g. confirm every named model is actually a real member of the
cluster it's attributed to, confirm every cited field name actually
exists in that angle's real schema) looks like real, justified follow-up
work, not speculative hardening.