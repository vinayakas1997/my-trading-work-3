# Trial 03 — malformed / out-of-range numeric inputs

**Checkpoint:** 01-forecast_skill (`forecast_skill.py::generate_forecast`)
**Status:** RUN — see `00-checkpoint-info.md`'s CRITICAL FINDING for full context

## Expected result

`reasoning` should flag that the Risk State/Personality inputs contain
anomalous values (a `"NaN"` string where a number is expected, a
`max_drawdown_pct` of `999.0` which isn't a plausible drawdown, a
negative `atr_pct`) rather than silently computing a normal-looking
forecast as if the numbers were valid. Confidence should be low
(roughly ≤ 0.3) given the model has no way to know which, if any, of the
malformed numbers are trustworthy. **Fail** if the response reads as a
completely ordinary, moderate-to-high-confidence forecast with no
acknowledgment that anything in the input was unusual.

## Why this trial exists

Nothing between the shared client and this prompt validates numeric
field ranges or types before they're flattened into the prompt text
(`_flatten_dict`, `forecast_skill.py:290-298`, does a pure structural
flatten — no type/range check at all). If a real upstream computation
(a bug in `fetch_risk_state`, a NaN slipping through a division, a
mis-scaled percentage) ever produces a value like these, this is exactly
what the model would actually see. Whether it notices and flags that, or
quietly launders garbage into a confident-looking JSON forecast, is a
real production-correctness question, not a synthetic one.

## Situation / scenario

AAPL. Simulates a real upstream computation bug: `realized_vol_30d` came
back as a string `"NaN"` instead of a float (e.g. a `0/0` in the
computation, serialized as a string before reaching this prompt),
`atr_pct` is negative (structurally impossible — ATR is a non-negative
measure of range), and `max_drawdown_pct` reads `999.0` (also
structurally impossible — a drawdown percentage should be a negative
fraction, not a number three orders of magnitude too large).

## Prompt sent

### System prompt
```
You are a quantitative forecast generator. Given personality features, risk state, and an optional Summary Agent ticker summary for a symbol, produce a structured forecast: direction (long/short/neutral), confidence (0-1), expected magnitude percent, magnitude standard deviation, and horizon in days. Weigh the summary narrative for context, but size only from the Risk State + Personality numbers. Return ONLY valid JSON with keys: direction, confidence, magnitude_pct, magnitude_std, horizon_days, reasoning. No markdown fences.
```

### User prompt
```
Generate a forecast for AAPL.

=== Ticker Summary (14 of 28 angles, run run_20260921_0300) ===
Mixed signals across momentum and mean-reversion angles this cycle. No strong directional consensus.

=== Angle Digest ===
  patchtst.direction: flat
  patchtst.confidence: 0.34
  timesfm.direction: down
  timesfm.confidence: 0.29

=== Personality Features ===
  shock_clustering_score: 15.0
  regime_tag: 
  correlation_to_spy_20d: 0.55

=== Risk State ===
  realized_vol_30d: NaN
  atr_pct: -0.5
  max_drawdown_pct: 999.0
  drawdown_active: true
  momentum_20d_pct: 0.01
  sharpe_recent_20d: 0.4
```

(Note: `shock_clustering_score: 15.0` is also deliberately out of the
plausible `~0-1` range these scores use elsewhere in this checkpoint's
other trials — a second, independent anomaly in the same trial, on
purpose, to see if the model catches either/both or neither.)

## Parameters

| Param | Value |
|---|---|
| Model | Qwen3.5-4B-Q4_K_M (local, `hindsight-llm`, llama.cpp `b11065`) |
| Endpoint | http://localhost:8092/v1/chat/completions |
| Temperature | 0.2 (real production default, `client.py:151`) |
| max_tokens | 8000 (real production default — `vinu-infra/llm/config.py:15`) |
| timeout_sec | 300 (real default — not hit; ran to its own token-budget end at ~94s) |
| Run timestamp (UTC) | 2026-09-21/22 |
| Attempt # | 1 of 1 (real settings run) + 1 thinking-disabled characterization run |
| Retry count | 0 |

## Response received

**Real production settings (temp=0.2, max_tokens=8000, thinking enabled — exactly as `forecast_skill` really calls it):**
```
(empty — finish_reason: "length". Same non-convergence pattern as trial 01: model's reasoning repeatedly re-checked each malformed field ("NaN", -0.5 ATR, 999.0 drawdown, 15.0 clustering score) without ever settling on a final answer, burning the full 8000-token budget. See 00-checkpoint-info.md's CRITICAL FINDING.)
```
Same real consequence as trial 01: `LlmParseError` → retried up to 3x → very likely `LlmCallFailed` raised as a hard error.

**Thinking-disabled characterization run (NOT a real production setting):**
```json
{
  "direction": "short",
  "confidence": 0.62,
  "magnitude_pct": -1.8,
  "magnitude_std": 0.95,
  "horizon_days": 5,
  "reasoning": "The Risk State indicates a severe drawdown event (999.0% max drawdown, active=true) with negative ATR percentage (-0.5), signaling extreme stress and potential mean-reversion pressure. While the momentum is flat (0.01%) and the summary notes mixed signals, the active drawdown state combined with the negative ATR suggests the asset is oversold or in a correction phase. The personality's shock clustering score of 15.0 implies high sensitivity to regime shifts, reinforcing the likelihood of a short-term bounce or continued downside if the drawdown persists. Given the active drawdown and negative volatility metric, a short position with moderate confidence is warranted to capture potential mean-reversion or continued weakness until the drawdown status clears."
}
```

## Verdict

- **Real production settings: FAIL — never produced output** (same non-convergence failure as trial 01).
- Thinking-disabled characterization (secondary — and this one is a genuine, separate FAIL on its own terms, not just "would have passed if it converged"): the model treated every malformed value as literally true rather than flagging any of them as anomalous. It read `max_drawdown_pct: 999.0` as "a severe drawdown event (999.0%)" — accepting a structurally impossible number at face value instead of noticing a drawdown can't exceed 100%. It read `atr_pct: -0.5` as "negative ATR percentage... signaling extreme stress" — treating a value that's impossible by definition (ATR is non-negative) as a meaningful signal instead of an error. It read `shock_clustering_score: 15.0` as "high sensitivity to regime shifts" with zero acknowledgment that every other trial in this checkpoint uses a ~0-1 scale for that field. It never mentioned `realized_vol_30d: NaN` at all. Confidence came out at 0.62 — well above the ≤0.3 expected-result bar. This is exactly the "quietly launders garbage into a confident-looking JSON forecast" failure mode the trial was designed to catch.
- Verdict stable across repeated runs: not tested.
- Latency (sec): ~93.9s (real settings, hit the cap) / ~3.2s (thinking disabled).
- Hallucination / rule violation observed: yes, quote — "signaling extreme stress" applied to a negative ATR value, and "999.0% max drawdown" treated as a real number rather than flagged as impossible.
- Notes: this is the most concerning trial in the checkpoint once thinking is disabled — independent of the convergence problem, the underlying business-logic answer to "does it catch malformed numeric input" is a clear no.

## Step 6 re-test (2026-09-22) — real improvement, confirmed

Re-ran through the real, unmodified `_build_forecast_prompt` (Steps 4-5
now live), thinking disabled, same live 9B model:

```json
{
  "direction": "neutral",
  "confidence": 0.25,
  "magnitude_pct": 0.0,
  "magnitude_std": 0.05,
  "horizon_days": 14,
  "reasoning": "The forecast is neutral due to conflicting and low-confidence signals. The Cluster Digest indicates mixed, low-confidence data with only 2 of 14 models active (patchtst flat at 0.34, timesfm down at 0.29), providing no strong directional consensus. The Risk State is highly degraded: realized_vol is NaN, max_drawdown is 999.0 (indicating a data anomaly or extreme outlier), and drawdown is active, while momentum is near zero. The Personality features show moderate correlation to the S&P 500 (0.55) but a high shock clustering score (15.0), suggesting the asset is prone to erratic moves during stress. Given the active drawdown, data anomalies in volatility, and the absence of a clear momentum or mean-reversion signal, no actionable long or short bias can be established."
}
```

**Verdict: PASS — a genuine, confirmed improvement over the original
run.** The original thinking-disabled run treated `max_drawdown_pct:
999.0` and `atr_pct: -0.5` as literally true ("severe drawdown event,"
"signaling extreme stress") and landed on `direction="short",
confidence=0.62` — exactly the "quietly launders garbage into a
confident-looking forecast" failure this trial exists to catch. This
re-run explicitly names `max_drawdown is 999.0 (indicating a data
anomaly or extreme outlier)` and `realized_vol is NaN` as anomalies
rather than real signals, correctly flags `shock_clustering_score=15.0`
as out-of-range ("high... suggesting the asset is prone to erratic
moves during stress" rather than a real 0-1-scale reading), and lands
on `direction="neutral", confidence=0.25` — squarely inside the
trial's own `≤0.3` expected bar. No new anomaly-flagging mechanism was
added for this trial specifically (no `cluster_anomalies` were set up
here) — this improvement traces to the Cluster Digest section itself
giving the model an explicit, pre-digested "mixed, low-confidence
signals" framing to reason from, rather than just the 28-line flat
digest alone. Worth treating as encouraging but not over-claimed as
proven-causal without a repeated-run check. Reproduction:
`step6_remaining_trials.py` (same directory).
