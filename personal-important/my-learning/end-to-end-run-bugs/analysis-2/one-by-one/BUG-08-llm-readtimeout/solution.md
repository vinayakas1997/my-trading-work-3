# BUG-08 🟠 LLM ReadTimeout on Refinement Prompts

**Component:** `vinu-research`, `vinu-infra`
**Files Changed:** None yet (root cause identified, fix pending)
**Date Found:** 2026-07-23
**Date Fixed:** Pending

## Problem

The LLM refinement prompts (iteration 2+) consistently time out with `ReadTimeout`
after 363 seconds (120s timeout × 3 retries + backoff). The first iteration's
generation prompts succeed (~90s), but refinement fails every time.

## Root Cause

The refinement prompt is **7x larger** than the generation prompt:

| Phase | Prompt Size | Response Time | Result |
|-------|------------|---------------|--------|
| Iteration 1 gen | 764 chars | 87-98s | ✅ Success |
| Iteration 1 critic | 1,242 chars | 13-15s | ✅ Success |
| Iteration 2+ refine | 5,517 chars | 363s (timeout) | ❌ Failed |

The extra 4,700+ chars come from sending the **full previous strategy code** (~3,500 chars)
back to the LLM in the refinement prompt:

```python
def _build_refinement_prompt(...):
    ...
    "Previous strategy code:"
    "```python"
    previous_code  # ← Full code: 3,500 chars
    "```"
    ...
```

The LLM server (qwen36-35B) processes requests sequentially (single-threaded).
Each request takes:
- 764-char prompt: ~30s per concurrent call 
- 5,517-char prompt: >120s (timeout)

With 3 concurrent refinement calls, they queue up at the server and each one times out.

## Suggested Fix (Pending)

**Option A: Remove full code from refinement prompt**
Send only the logic summary, not the full implementation:
```python
# Before: Sends 3,500 chars of code
"Previous strategy code:\n```python\n" + previous_code + "\n```"

# After: Sends 200 chars of summary
"Strategy logic: RSI mean-reversion with SMA filter, params: rsi_period=14"
```

**Option B: Increase LLM timeout**
Change `llm_timeout_sec` from 120.0 to 300.0 or 600.0.

**Option C: Sequential LLM calls instead of concurrent**
With sequential calls, each gets full server attention (no queueing).

## Verification (Pending)

1. Run research pipeline with shortened refinement prompts
2. Confirm refinement succeeds (iteration 2+)
3. Compare response times: ~90s gen vs <60s refine
4. Check `llm_calls.jsonl` for success=true on all calls

## Lessons Learned

- LLM prompt size directly impacts response time
- Sending full code back for refinement is wasteful — LLM knows the structure
- Always check LLM call logs (`/data/llm_calls.jsonl`) for prompt sizes
- Make timeout configurable per-call, not just globally
- Concurrent LLM calls to a single-threaded server queue up, don't parallelize
