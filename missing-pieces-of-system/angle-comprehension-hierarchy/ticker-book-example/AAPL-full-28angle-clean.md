# AAPL — full 28-angle, all-real-timeframes book (clean input, live LLM run)

**All input data is FABRICATED** (generated programmatically, not sampled
from any real run) but **the LLM response is real** — sent to the live
`hindsight-llm` container (Qwen3.5-4B-Q4_K_M, local, via
`docker-compose-hindsight.yml`) on 2026-09-22. This supersedes
`AAPL.md`'s 15-of-28 hand-authored example for the comprehension
question specifically: instead of me writing Chapters 2-3 by hand, the
real model wrote them, so this file can show where it actually gets
things right and where it actually hallucinates.

## Input construction

Every one of the 28 real angles, at every one of *its own* real
`time_formats` from `angles.yaml` (most get the standard 6:
`1min/5min/15min/1H/4H/1D`; `backtesting_44_metrics` also gets
`1W/1M/6M`; `regime_analysis` also gets `1W/1M`; `trend_lifecycle` also
gets `1W`; `trend_session_structure` stops at `4H`, no `1D`) — **173
total data rows**, every one populated, no gaps. Values follow one
consistent fictional story across the whole book (daily bullish trend,
gradually weakening at shorter timeframes) so a reader/model could in
principle notice the same cross-timeframe pattern `AAPL.md` already
demonstrated for 15 angles, now at full scale. Full input:
`AAPL-full-28angle-clean-digest.txt` (173 lines, same directory).

Generation script kept for reproducibility:
`missing-pieces-of-system/angle-comprehension-hierarchy/ticker-book-example/gen_full_book.py`.

## Prompt sent

Single-shot adaptation of the real
`vinu-agent/teams/screener/agents/angle_synthesizer/prompt.md` — same
rules (only treat real data as informative, cite real numbers, never
invent a signal), same verbatim 7-cluster membership list, same
Cluster-B-consensus-rate instruction, same `cluster_digest` JSON output
shape. **Adapted, not byte-for-byte**: this is a direct `chat_json`-style
call, not run through the actual vinu-agent tool-calling harness, so the
`explain_angle`/`compare_angles`/`find_trade_plan_artifact` tool-call
steps are omitted — flagged explicitly, not silently dropped. Full
system prompt: see `run_full_book_test.py` in this folder.

`temperature=0.2`, `max_tokens=6000`, `chat_template_kwargs:
{enable_thinking: false}` — **thinking disabled, not a real production
setting**, used because checkpoint 01 already established (see
`vigrous-llm-testing/checkpoints/01-checkpoint-forecast_skill/`) that
this model doesn't reliably converge within a real token budget once
prompt complexity rises; a 28-angle, 173-row synthesis is far more
complex than any checkpoint-01 trial, so thinking-enabled wasn't
attempted here (would almost certainly not converge, consistent with
that checkpoint's finding).

## Real response received

Converged cleanly, `finish_reason: "stop"`, **22.0s**, well-organized
prose covering all 7 clusters plus an anomalies section, ending with a
valid `cluster_digest` JSON block. Full response saved in
`full_book_results.json` (same directory) under key `"clean"`.

## Verdict — real, verified findings

**Two confirmed hallucinations, despite good surface-level organization:**

1. **Wrong angle-data-coverage count.** The model reported *"Out of the
   28 requested angles, **27** have real data across multiple
   timeframes."* Verified against the actual generated dataset: **all
   28** angles have `row_count > 0` — there is no missing angle in this
   input at all. The model invented a gap that doesn't exist, and never
   said which angle it thought was missing.

2. **Fabricated a `direction` field for angles that never had one.**
   Cluster B synthesis claims *"10 of 14 models... showing an 'up'
   direction on the 1D timeframe"* and names `timer_timerxl` and
   `timesfm` among them. Verified against the real input: neither angle
   ever has a `direction` field in this dataset — both only report
   `point_forecast`/`model_backend` (that's their real schema per
   `angles.yaml`'s `outputs` description: a point/quantile forecast, not
   a categorical direction). The real count of Cluster-B angles with an
   actual `direction: "up"` value at 1D is **8**, not 10. This is a
   direct violation of the system prompt's own explicit rule — "Never
   invent a number, trend, or signal that isn't actually in the returned
   data" — not a borderline judgment call.

**What it got right:** the per-cluster prose is otherwise well-grounded
— real cited numbers (ARIMA 187.44→189.2, GARCH 0.021-0.024,
regime_analysis bull-probability 0.43→0.63) match the actual input
exactly. It also correctly noticed a real, intentional pattern in the
data (Cluster G's `backtesting_44_metrics`/`pnl_attribution` being
byte-identical across every timeframe) and reasoned sensibly about why
that's structurally expected (backward-looking track-record stats, not
live readings) — matching `AAPL.md`'s own Chapter 2 reasoning for the
same pattern, arrived at independently.

**Net read**: at 28-angle/173-row scale, this model produces
genuinely useful, well-cited synthesis prose *and* introduces confident,
specific, checkable-and-wrong claims in the same response — the two are
not visually distinguishable without independently checking the
underlying data, which is exactly the risk a "vigorous testing"
discipline exists to catch. A shorter or more structured digest (fewer
than 173 rows, or a pre-aggregated per-angle summary rather than raw
per-timeframe rows) is a real candidate mitigation worth testing next,
not assumed to fix it.