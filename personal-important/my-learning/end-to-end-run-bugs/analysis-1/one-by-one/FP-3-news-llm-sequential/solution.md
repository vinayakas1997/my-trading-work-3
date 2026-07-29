# FP-3 🟡 News LLM Calls Are Sequential

**Component:** `run_pipeline.py`
**Files Changed:** `run_pipeline.py`

## Problem

`step_news()` called `/news/analyze` in a sequential for-loop, one article at a time. Each call blocks 5-10s for the LLM response. With the default `--news-articles=5`, this added 25-50s of wall-clock time. With higher article counts, the penalty scaled linearly.

## Root Cause

The pipeline looped over articles individually instead of parallelizing the independent HTTP calls:
```python
analyzed = 0
for article in articles[:article_count]:
    ...
    _req("POST", f"{base}/news/analyze", json={"url_or_id": url_or_id}, timeout=300)
    analyzed += 1
    ...
```

## Solution

Replaced the sequential for-loop with a `ThreadPoolExecutor`. Each article analysis is an independent HTTP call — no shared state, no ordering requirements.

### Files changed

| File | Change |
|------|--------|
| `run_pipeline.py` | Added `from concurrent.futures import ThreadPoolExecutor`; replaced sequential for-loop with `pool.map()` (max_workers=5) |

### Verification

1. `python -c "import ast; ast.parse(open('run_pipeline.py').read()); print('OK')"` ✓
2. `import run_pipeline` ✓
