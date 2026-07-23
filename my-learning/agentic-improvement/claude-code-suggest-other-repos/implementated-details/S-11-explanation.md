# S-11: Confidence Scoring — Explanation & Status

## What It Is

Extracts a numeric confidence score from the LLM's reflection and validation outputs, enabling downstream filtering and prioritization of research conclusions.

## Components

1. **`"confidence": 0.0` in prompt schemas** — added to the `REFLECTION` and `VALIDATION` JSON output schemas in `llm.py`. The LLM must now produce a `confidence` field alongside its textual reasoning.

2. **`_reflect()` return type changed** — from `str` to `tuple[str, float]`. The first element remains the reflection text; the second is the parsed confidence value.

3. **Confidence logging** — both `_reflect()` and `_validate_idea()` log the confidence value, making it visible in traces and logs for debugging and analysis.

4. **Call-site updates in `loop.py`** — all locations that called `_reflect()` and expected a single string are updated to unpack the tuple, accessing the text and confidence separately.

## Current Status: ✅ IMPLEMENTED

Reflection and validation outputs include a `confidence` score; all call sites handle the new return type.
