# Trial 01 — narrative vs. numbers conflict

**Checkpoint:** 01-forecast_skill (`forecast_skill.py::generate_forecast`)
**Status:** RUN — see `00-checkpoint-info.md`'s CRITICAL FINDING for full context

## Expected result

`direction`/`confidence`/`magnitude_pct` must track the Risk State +
Personality numbers (deteriorating, negative-leaning), **not** the
bullish Ticker Summary narrative. A production-grade response should
land on `neutral` or a low-confidence `short`/`long` (confidence roughly
≤ 0.4), and `reasoning` must explicitly acknowledge the tension between
the bullish narrative and the weaker numbers rather than silently
picking a side. **Fail** if `direction="long"` with `confidence > 0.6` —
that would mean the narrative drove the sizing the system prompt
explicitly forbids.

## Why this trial exists

The system prompt's one explicit rule under test: "Weigh the summary
narrative for context, but size only from the Risk State + Personality
numbers." A model that pattern-matches on the overall bullish *tone* of
the prompt (the narrative section reads confident, is placed first,
uses strong language) rather than actually parsing the numeric sections
would produce a real, silent sizing error — a forecast more optimistic
than the real risk numbers justify, directly upstream of `capital_
allocator`'s real funding decision.

## Situation / scenario

AAPL. A real Summary Agent read exists and is genuinely bullish
(breakout narrative, unusual volume, analyst upgrades) — this part of
the prompt is realistic, Summary Agent narratives are real free text.
But the same cycle's Risk State numbers (also realistic — these come
from `fetch_risk_state`, a real deterministic computation, not from the
narrative) show a deteriorating setup: negative recent momentum, an
active drawdown, and negative recent Sharpe. This combination — a lagging
or over-optimistic narrative against numbers that have already turned —
is a real, plausible production scenario (the two inputs are computed on
different cadences and could genuinely diverge), not a contrived one.

## Prompt sent

### System prompt
```
You are a quantitative forecast generator. Given personality features, risk state, and an optional Summary Agent ticker summary for a symbol, produce a structured forecast: direction (long/short/neutral), confidence (0-1), expected magnitude percent, magnitude standard deviation, and horizon in days. Weigh the summary narrative for context, but size only from the Risk State + Personality numbers. Return ONLY valid JSON with keys: direction, confidence, magnitude_pct, magnitude_std, horizon_days, reasoning. No markdown fences.
```

### User prompt
```
Generate a forecast for AAPL.

=== Ticker Summary (9 of 28 angles, run run_20260921_0300) ===
AAPL is showing a strong bullish breakout above its 50-day moving average on unusually high volume (2.3x the 20-day average). Two sell-side analysts raised price targets this week citing strength in services revenue. Momentum indicators (patchtst, timesfm) both point to continued upside over the next 5-10 sessions. Sentiment angle (finbert) shows a marked improvement in news tone over the past 3 days.

=== Angle Digest ===
  patchtst.direction: up
  patchtst.confidence: 0.71
  timesfm.direction: up
  timesfm.confidence: 0.68
  finbert.sentiment_score: 0.62
  finbert.article_count: 14
  shock_personality.regime: normal
  shock_clustering.cluster_id: 2

=== Personality Features ===
  shock_clustering_score: 0.71
  regime_tag: elevated_volatility
  correlation_to_spy_20d: 0.81

=== Risk State ===
  realized_vol_30d: 0.42
  atr_pct: 0.038
  max_drawdown_pct: -0.14
  drawdown_active: true
  momentum_20d_pct: -0.06
  sharpe_recent_20d: -0.35
```

## Parameters

| Param | Value |
|---|---|
| Model | Qwen3.5-4B-Q4_K_M (local, `hindsight-llm`, llama.cpp `b11065`) |
| Endpoint | http://localhost:8092/v1/chat/completions |
| Temperature | 0.2 (real production default, `client.py:151`) |
| max_tokens | 8000 (real production default — `vinu-infra/llm/config.py:15`, no `forecast_skill` role override) |
| timeout_sec | 300 (real default — not hit; the call ran to its own token-budget end at ~94s) |
| Run timestamp (UTC) | 2026-09-21 |
| Attempt # | 1 of 1 (real settings run) + 1 thinking-disabled characterization run |
| Retry count | 0 (this was a direct call, not through the real retrying client) |

## Response received

**Real production settings (temp=0.2, max_tokens=8000, thinking enabled — exactly as `forecast_skill` really calls it):**
```
(empty — finish_reason: "length". Model spent all 8000 tokens inside reasoning_content, re-deriving direction/confidence/magnitude in a repeating "Wait... Okay..." loop, never emitted the final JSON. See 00-checkpoint-info.md's CRITICAL FINDING.)
```
Real consequence traced through `vinu-infra/llm/client.py`: empty content → `json.loads` fails → `LlmParseError` → retried (real `retry_max=3`) → each retry ~90-95s → very likely fails again given temp=0.2 → `LlmCallFailed` raised, surfaced as a hard error (not a silent bad forecast — `raise_on_failure=True` is already correctly wired).

**Thinking-disabled characterization run (`chat_template_kwargs: {enable_thinking: false}` — NOT a real production setting, used only to see what this model would say if it could reach an answer):**
```json
{
  "direction": "short",
  "confidence": 0.52,
  "magnitude_pct": 0.045,
  "magnitude_std": 0.018,
  "horizon_days": 14,
  "reasoning": "While the ticker summary indicates a bullish breakout with high volume and positive sentiment, the Risk State features a critical contradiction: drawdown_active is true, momentum_20d_pct is negative (-0.06), and sharpe_recent_20d is negative (-0.35). The regime_tag is 'elevated_volatility' with a high shock_clustering_score (0.71) and strong correlation to SPY (0.81), suggesting the current 'breakout' may be a volatility expansion or mean reversion event rather than a sustained trend. The negative momentum and drawdown activity override the technical breakout signals, warranting a short position to capture potential mean reversion or volatility exhaustion. Confidence is moderate (0.52) due to the conflicting bullish narrative in the summary versus the bearish risk metrics."
}
```

## Verdict

- **Real production settings: FAIL — never produced output.** The call would raise `LlmCallFailed` after retries, not a wrong number but a hard unavailability. This is the primary, reportable verdict.
- Thinking-disabled characterization (secondary, informational only): Parsed as valid JSON matching schema — yes. Matches "Expected result" — mostly: direction correctly tracked the deteriorating Risk State numbers (`short`, not `long`), and `reasoning` explicitly named the narrative-vs-numbers tension exactly as hoped. Confidence (0.52) is slightly above the "roughly ≤0.4" guideline in Expected Result but well under the hard-fail bar (`direction="long"` with `confidence>0.6`), so this would PASS on the underlying business-logic question if it could actually finish reasoning.
- Verdict stable across repeated runs: not tested (single real-settings attempt; repeating it would only reconfirm non-convergence, not add new information without also disabling thinking).
- Latency: real-settings attempt ran the full ~94s before hitting the token cap; thinking-disabled attempt: ~3.3s.
- Hallucination / rule violation observed: none in the thinking-disabled answer — no invented numbers, direction correctly derived from real Risk State fields.
- Notes: this trial's real headline result is the non-convergence itself, not the narrative-vs-numbers question it was designed to probe — that question remains only partially answered (positively, on the evidence available) pending a fix to the convergence problem.

## Step 6 re-test (2026-09-22) — real regression, exactly what the plan warned about

Re-ran through the real, unmodified `_build_forecast_prompt` (Steps 4-5
now live: `cluster_digest` rendered alongside `angle_digest`), thinking
disabled, same live 9B model:

```json
{
  "direction": "long",
  "confidence": 0.58,
  "magnitude_pct": 0.045,
  "magnitude_std": 0.028,
  "horizon_days": 5,
  "reasoning": "The forecast leans long primarily due to the strong bullish breakout above the 50-day moving average on 2.3x average volume, supported by positive momentum indicators (patchtst, timesfm) and improved sentiment (finbert). However, the Risk State significantly dampens confidence and magnitude. The 'elevated_volatility' regime, combined with a recent max drawdown of -14% and active drawdown status, suggests the market is fragile despite the technical breakout. The negative 20-day momentum (-6%) and poor recent Sharpe ratio (-0.35) indicate the current rally may be a short-term relief move rather than a sustained trend, limiting the expected magnitude to roughly 4.5% with a standard deviation of 2.8%. The high correlation to SPY (0.81) implies the move is likely driven by broad market beta rather than idiosyncratic alpha, further capping upside potential in a volatile environment."
}
```

**Verdict: real regression, not a hard fail but a genuine step backward.**
The original (pre-Step-5) thinking-disabled run correctly landed on
`direction="short", confidence=0.52` — tracking the deteriorating Risk
State over the bullish narrative, as the trial wants. This re-run flips
to `direction="long", confidence=0.58` — narrative-driven, not
numbers-driven. `confidence=0.58` doesn't cross the hard-fail threshold
(`>0.6`), so this isn't a clean FAIL by the trial's own bar, but the
directional flip itself is real and concerning: the `reasoning` even
correctly *describes* the risk-numbers tension in detail ("suggests the
market is fragile," "may be a short-term relief move") and still lands
long. This is exactly the risk `01-plan.md`'s Step 6 section named in
advance — "a fix to the angle side could in principle make the
narrative-vs-numbers problem worse (a better-written cluster summary is
also a more persuasive one)" — now confirmed, not hypothetical. Real
candidate cause: the new `=== Cluster Digest ===` section's Cluster B
line ("2 of 2 models with data lean up") restates the bullish signal a
second time, in a second location, before the model ever reaches the
Risk State section — added restatement of the same bullish signal, not
new information, may be tipping the balance. Not proven, but the
mechanism is plausible and testable. Reproduction:
`step6_remaining_trials.py` (same directory).
