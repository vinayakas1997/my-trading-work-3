# Enhancement 5: Replace Keyword-Matched Filter Injection with Structured, Data-Aware Filters

## Current State Score: 3/10

`_generate_filters()` in `loop.py:430-451` is the mechanism that turns a critique ("add ADX filter", "add London session exclusion") into actual code injected into a strategy's `generate_weights()`. It works by raw substring matching on the critique text:

```python
if "adx" in suggestion_text: ...
if "session" in suggestion_text and "london" in suggestion_text: ...
if "cool" in suggestion_text or "news" in suggestion_text: ...
if "volatil" in suggestion_text: ...
```

Two concrete problems, both already visible in the current implementation:

## Problem 1: False-positive keyword matches inject irrelevant filters

`"cool"` matches "news cooldown" (intended) but will also match any unrelated LLM-generated suggestion that happens to contain that substring (e.g., "this strategy could benefit from..." — hypothetically, and more realistically once free-text LLM suggestions from the risk-critic LLM call flow into this same matcher, since `_merge_feedback` (`loop.py`, [see how-it-works.md §3](../project-overall-explanation/how-it-works.md)) appends LLM suggestions to the same `additional_suggestions` list that `_generate_filters` reads from). Once the LLM risk critic's free-text suggestions are in the same pipeline as the rule-based ones, keyword matching against LLM prose is fragile — LLMs don't reliably use the exact five trigger substrings, and when they do use one incidentally, an unwanted filter gets spliced in.

## Problem 2: Injected filters reference columns that may not exist in real data

The filter templates reference synthetic default columns, e.g. an ADX filter along the lines of `signal[adx < 20] = 0` assuming an `adx` column is present on the strategy's `data` frame. Nothing checks that the actual OHLCV data passed to `generate_weights()` for this run has an `adx` column computed — if it doesn't, this either raises a `KeyError` at backtest time (loop breaks, `best_result` falls back to an earlier iteration silently) or, if a default/synthetic fill was added defensively somewhere (worth auditing — a `pd.Series(25.0, ...)` style default was found in at least one filter path), the filter is evaluated against a **constant fake value**, meaning the "ADX filter" doesn't filter anything at all — every day has the same fake ADX, so the mask is either always-true or always-false regardless of real market conditions. Either failure mode is silent: the loop reports the filter as "applied," the report lists it as a refinement, and the metrics change (because *some* filter logic executed) — but the strategy didn't get the risk control the report claims it has.

## What to Build

### 1. Structured suggestion objects instead of free text matching

Move away from matching prose. Have `_rule_based_check` (and, when parsed, the LLM critic) emit a typed suggestion, not just a string:

```python
@dataclass
class FilterSuggestion:
    kind: Literal["adx", "session_exclusion", "volatility_guard", "news_cooldown"]
    params: dict[str, Any]  # e.g. {"threshold": 20} for adx, {"session": "london"} for exclusion
    source: Literal["rule", "llm"]
    confidence: float = 1.0  # rule-based = 1.0; LLM-parsed = lower unless it maps cleanly to a known kind
```

For LLM suggestions, add a small classification step (not free-text keyword matching, but a constrained call: "does this suggestion map to one of these 4 known filter kinds, and if so with what parameters? Answer JSON or 'none'"). If it doesn't map cleanly, don't inject a filter — surface it in the report as an unactioned suggestion for a human to consider, rather than guessing.

### 2. Verify required data exists before injecting a filter

```python
def _apply_filter(strategy_code: str, suggestion: FilterSuggestion, available_columns: set[str]) -> str:
    required = FILTER_REQUIRED_COLUMNS[suggestion.kind]  # e.g. {"adx": {"adx_14"}}
    missing = required - available_columns
    if missing:
        LOG.warning("Skipping %s filter: data missing columns %s", suggestion.kind, missing)
        return strategy_code  # no-op, don't silently fake it
    ...
```

`available_columns` should come from whatever indicator computation actually ran for this backtest (`vinu-features` per the architecture), not be assumed present.

### 3. Report what was actually applied vs. skipped

`report.py`'s refinement history should distinguish "filter applied" from "filter suggested but skipped (missing data)" — currently a skipped/no-op filter and a genuinely applied one both show up identically in the "Refinements Applied" list (per the example output in `how-it-works.md` §4, Stage 8), which misrepresents what changed between iterations.

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `loop.py:430-451` | REPLACE | `_generate_filters` takes typed `FilterSuggestion` objects, not raw critique strings |
| `loop.py` (rule-based check) | MODIFY | Emit `FilterSuggestion` objects directly instead of free text for the 4 known filter kinds |
| `loop.py` (LLM merge) | MODIFY | Add a constrained classification step mapping free-text LLM suggestions to `FilterSuggestion` or `None` |
| `loop.py` | NEW | `FILTER_REQUIRED_COLUMNS` mapping + existence check before injecting any filter |
| `report.py` | MODIFY | Refinement history shows applied vs. skipped-for-missing-data separately |
| `tests/test_loop.py` | NEW | Test that a suggestion mentioning "cool" but unrelated to news doesn't trigger the news-cooldown filter; test that a missing `adx` column skips the filter instead of injecting a no-op |

## Complexity & Verdict

- **Difficulty:** Medium — the structural change (typed suggestions) touches both the rule-based and LLM-merge paths.
- **Priority:** **P2** — real correctness issue (silent no-op filters misreported as applied), but scoped to the refinement step rather than the core backtest/validation methodology in [01](01-lookahead-bias-critical-fix.md)/[02](02-overfitting-and-walkforward-gating.md).
- **Time estimate:** 3-4 days.
