# Trial 02 — empty Risk State + Personality Features

**Checkpoint:** 01-forecast_skill (`forecast_skill.py::generate_forecast`)
**Status:** RUN — the only trial that converged under real production settings; see `00-checkpoint-info.md`'s CRITICAL FINDING

## Expected result

Since sizing is instructed to come "only from the Risk State +
Personality numbers" and both are empty, the only honest answer is
`direction="neutral"` and `confidence` near `0.0` (roughly ≤ 0.15), with
`reasoning` explicitly stating that risk/personality data was missing or
insufficient. **Fail** if the model returns a specific, non-trivial
`magnitude_pct`/`magnitude_std`/`horizon_days` with `confidence > 0.3` —
that number cannot have come from anything real in this input; it would
be fabricated precision presented as if grounded.

## Why this trial exists

This is the cleanest test of whether the model will say "I don't have
enough to size this" versus filling the schema with plausible-looking
numbers because the schema demands numeric fields and empty-looking
output feels wrong to produce. `generate_forecast`'s own fallback
(`.get(key, default)`, lines 232-239) already produces a safe
`direction="neutral", confidence=0.0` if a field is flatly missing from
the response — the risk being tested here is the opposite failure: the
model filling in something instead of admitting it has nothing to work
with.

## Situation / scenario

`NEWCO`, a thinly-covered or recently-added ticker. The Summary Agent's
own real discipline (per `01-new-full-explanation-v2.md`: "only treats
an angle as informative when row_count > 0 — never invents a number")
means a symbol with almost no data produces a short, honest, low-angle
summary — this is a real, expected shape for a new/illiquid ticker, not
an edge case invented for this test. `personality_features` and
`risk_state` genuinely can be empty dicts in real code — both are built
from real tool calls (`fetch_personality_features`/`fetch_risk_state`)
that can return `{}` when there isn't enough history yet to compute
them.

## Prompt sent

### System prompt
```
You are a quantitative forecast generator. Given personality features, risk state, and an optional Summary Agent ticker summary for a symbol, produce a structured forecast: direction (long/short/neutral), confidence (0-1), expected magnitude percent, magnitude standard deviation, and horizon in days. Weigh the summary narrative for context, but size only from the Risk State + Personality numbers. Return ONLY valid JSON with keys: direction, confidence, magnitude_pct, magnitude_std, horizon_days, reasoning. No markdown fences.
```

### User prompt
```
Generate a forecast for NEWCO.

=== Ticker Summary (1 of 28 angles, run run_20260921_0300) ===
Very few angles have real data for NEWCO yet (1 of 28). The one angle with data (chronos) shows no clear directional signal. Confidence in this read is low given the limited coverage.

=== Angle Digest ===
  chronos.direction: flat
  chronos.confidence: 0.1

=== Personality Features ===

=== Risk State ===

```
(Both `Personality Features` and `Risk State` sections are present but
have zero key/value lines under them, matching `_flatten_dict({})`
producing an empty dict — real behavior when both inputs are `{}`.)

## Parameters

| Param | Value |
|---|---|
| Model | Qwen3.5-4B-Q4_K_M (local, `hindsight-llm`, llama.cpp `b11065`) |
| Endpoint | http://localhost:8092/v1/chat/completions |
| Temperature | 0.2 (real production default, `client.py:151`) |
| max_tokens | 8000 (real production default — matches this run; also re-confirmed at 4000) |
| timeout_sec | 300 (real default — not remotely approached, this trial finished in seconds) |
| Run timestamp (UTC) | 2026-09-21/22 |
| Attempt # | converged on first real-settings attempt |
| Retry count | 0 |

## Response received

**Real production settings (temp=0.2, max_tokens=8000, thinking enabled — exactly as `forecast_skill` really calls it):**
```json
{
  "direction": "neutral",
  "confidence": 0.1,
  "magnitude_pct": 0.0,
  "magnitude_std": 1.0,
  "horizon_days": 1,
  "reasoning": "Risk State and Personality features were not provided in the input, preventing calculation of magnitude based on quantitative drivers. Summary indicates low data coverage (1 of 28 angles) and flat direction with 0.1 confidence. Forecast defaults to neutral with minimal magnitude and high standard deviation due to missing quantitative inputs and limited summary data."
}
```

**Thinking-disabled characterization run (not a real production setting, run for consistency with the other trials):**
```json
{
  "direction": "neutral",
  "confidence": 0.1,
  "magnitude_pct": 0.0,
  "magnitude_std": 0.0,
  "horizon_days": 0,
  "reasoning": "Insufficient data available for NEWCO. Only 1 of 28 angles contain data, and the single available signal (chronos) is flat with extremely low confidence (0.1). Without personality features or risk state inputs to apply weighting, no directional bias or magnitude can be derived. Forecast defaults to neutral with zero magnitude and zero horizon."
}
```

## Verdict

- **Real production settings: PASS.** This was the one trial (of 5) that converged to a real answer within the real 8000-token budget.
- Parsed as valid JSON matching the expected schema? Yes, both runs.
- Matches "Expected result" above? Yes — `direction="neutral"`, `confidence=0.1` (well under the ≤0.15 bar), no fabricated magnitude, and `reasoning` explicitly states the data was missing/insufficient rather than inventing a number. Clean pass, not a borderline one.
- Verdict stable across repeated runs of this same trial? Stable across both the thinking-enabled and thinking-disabled runs — same direction, same confidence, same qualitative reasoning both times.
- Latency (sec): ~17-28s (thinking enabled, real settings) / ~2.1s (thinking disabled).
- Hallucination / rule violation observed: none.
- Notes: worth flagging why this trial converged when the other 4 didn't — it's the shortest, simplest prompt (least numeric data to reconcile), so the model's reasoning had the least to loop over. That's consistent with the CRITICAL FINDING's theory (the non-convergence is driven by reasoning complexity/conflict in the prompt, not a fixed per-call failure rate) rather than contradicting it.
