# Trial 05 — cold-start overconfidence

**Checkpoint:** 01-forecast_skill (`forecast_skill.py::generate_forecast`)
**Status:** RUN — see `00-checkpoint-info.md`'s CRITICAL FINDING for full context

## Expected result

`confidence` should be visibly tempered relative to what the same
Risk State/Personality/Angle-Digest numbers would justify at a mature
tier — roughly capped in the `0.3-0.5` range even though the numbers
themselves look moderately favorable — and `reasoning` should explicitly
reference the cold-start/limited-live-history context (zero real trades,
only 3 paper-trading days). **Fail** if `confidence > 0.7` with no
mention of maturity/track record anywhere in `reasoning` — that would
mean the `=== System Maturity ===` block was effectively ignored despite
being explicitly injected into the prompt for exactly this purpose.

## Why this trial exists

The system prompt doesn't mention maturity at all — the actual
instruction lives inside the `=== System Maturity ===` section itself
(`_build_forecast_prompt`, lines 250-263): *"Weight backtest/theoretical
evidence more heavily at cold_start/paper_only; weight live calibration
more heavily at mature."* This is a real, deliberately separate
instruction channel (`maturity_context`, distinct from `summary_context`,
per the function's own docstring) added specifically so a young strategy
doesn't get treated with the same confidence as one with a real track
record. Unlike trial 01 (narrative vs. numbers), this trial keeps every
other input *consistent and favorable* — isolating whether the model
actually reads and applies this one specific block, not whether it can
resolve a conflict.

## Situation / scenario

A newly-promoted strategy on AAPL: `n_real_trades=0`,
`n_paper_trading_days=3`, `directional_accuracy=0.0` (no real outcomes
yet to measure), `regime_coverage=None`. Everything else in the prompt —
Angle Digest, Personality, Risk State — reads moderately bullish and
internally consistent (deliberately not conflicting, unlike trial 01),
so any hesitation in the response can only be attributed to the maturity
block, not to noisy or contradictory numbers.

## Prompt sent

### System prompt
```
You are a quantitative forecast generator. Given personality features, risk state, and an optional Summary Agent ticker summary for a symbol, produce a structured forecast: direction (long/short/neutral), confidence (0-1), expected magnitude percent, magnitude standard deviation, and horizon in days. Weigh the summary narrative for context, but size only from the Risk State + Personality numbers. Return ONLY valid JSON with keys: direction, confidence, magnitude_pct, magnitude_std, horizon_days, reasoning. No markdown fences.
```

### User prompt
```
Generate a forecast for AAPL.

=== System Maturity ===
  tier: cold_start (real live trades: 0, paper-trading days: 3, live directional accuracy: 0.0, regimes seen live: none)
  Weight backtest/theoretical evidence more heavily at cold_start/paper_only; weight live calibration more heavily at mature.

=== Ticker Summary (16 of 28 angles, run run_20260921_0300) ===
Constructive setup: momentum and trend angles both lean positive, sentiment has improved over the past week, no major red flags in the mean-reversion angles.

=== Angle Digest ===
  patchtst.direction: up
  patchtst.confidence: 0.58
  timesfm.direction: up
  timesfm.confidence: 0.55
  finbert.sentiment_score: 0.4
  shock_personality.regime: normal

=== Personality Features ===
  shock_clustering_score: 0.25
  regime_tag: normal
  correlation_to_spy_20d: 0.62

=== Risk State ===
  realized_vol_30d: 0.19
  atr_pct: 0.015
  max_drawdown_pct: -0.02
  drawdown_active: false
  momentum_20d_pct: 0.03
  sharpe_recent_20d: 0.45
```

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
(empty — finish_reason: "length". Same non-convergence pattern: reasoning trace shows the model had essentially finished ("direction: long", "confidence 0.50", "magnitude 1.0%... Std Dev 1.5%... Horizon 5 days due to cold_start calibration" all appear near the end of the trace) but kept re-verifying each field ("Wait, `reasoning`:... Wait, `magnitude_pct`:... Wait, `magnitude_std`:...") instead of ever emitting the terminal JSON. See 00-checkpoint-info.md's CRITICAL FINDING.)
```

**Thinking-disabled characterization run (NOT a real production setting):**
```json
{
  "direction": "long",
  "confidence": 0.56,
  "magnitude_pct": 0.018,
  "magnitude_std": 0.004,
  "horizon_days": 5,
  "reasoning": "At cold_start with zero live trades, the forecast relies heavily on the theoretical alignment between the ticker summary (positive momentum/trend, improved sentiment) and the personality features. The shock_personality.regime is 'normal' with a low clustering score (0.25), indicating stable, non-extreme behavior. The risk state shows low volatility (realized_vol 0.19, ATR 0.015) and no active drawdown, supporting a cautious entry. The expected magnitude is derived from the low ATR and moderate momentum (0.03), resulting in a small but positive bias. Confidence is moderate (0.56) reflecting the lack of live calibration data despite strong theoretical signals."
}
```

## Verdict

- **Real production settings: FAIL — never produced output** (same non-convergence failure as trials 01/03; reasoning trace shows it was very close to done, unlike trial 04's more concerning "compliant answer in progress").
- Thinking-disabled characterization (secondary): direction/magnitude are reasonable given the moderately bullish inputs. `reasoning` does explicitly reference "cold_start", "zero live trades", and "lack of live calibration data" — confirming the `=== System Maturity ===` block was read and applied, not ignored. Confidence (0.56) is a bit above the "roughly 0.3-0.5" ideal range stated in Expected Result, but well under the hard-fail bar of `confidence > 0.7`, and maturity is clearly referenced (the hard-fail condition requires *both* high confidence *and* no maturity mention). This would PASS the trial's actual test, with a note that the tempering is real but mild rather than strong.
- Verdict stable across repeated runs: not tested.
- Latency (sec): ~93.7s (real settings, hit the cap) / ~2.9s (thinking disabled).
- Hallucination / rule violation observed: none.
- Notes: like trial 01, this trial's real headline result is the non-convergence; the underlying maturity-weighting question it was designed to probe looks like a soft pass on the evidence available, not a strong one — the confidence discount for cold-start is present but smaller than the checkpoint's ideal.
