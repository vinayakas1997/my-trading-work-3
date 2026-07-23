# R-C: Callback Order + Evidence Plumbing

Three small correctness fixes bundled.

## Bug 1: Pivot skips `on_iteration`

`loop.py:373-379` appended the pivot record to `history` and then **broke before** calling `self._on_iteration(record)`. Every other exit path (PASS, STOP, AST-failure) called the callback first. The CLI live-progress printer (`cli.py:52`) never saw the iteration that triggered the pivot, making the loop appear to stop silently.

**Fix:** Moved `self._on_iteration` call to right after `history.append(record)`, before the `should_pivot` break.

## Bug 2: `Evidence.run_id` always 0

`loop.py:451` hardcoded `run_id=0` — no DB run id was passed through the chain. All evidence entries were untraceable back to the research run that produced them.

**Fix:**
- Added `run_id: int = 0` parameter to `StrategyResearchLoop.run()`
- Stored on `self._run_id`
- Used `self._run_id` in `Evidence(run_id=self._run_id, ...)` 
- Passed `run_id=record.id` from `service.py`

## Bug 3: AST-failure iterations pollute evidence

`loop.py:449-460` recorded all `history` items as evidence, including iterations that failed AST verification. Those never actually ran a backtest — they hit a static Python parsing error before `run_backtest()` was called — yet their `sharpe=0.0` was recorded as `"contradicts"` evidence for the hypothesis.

**Fix:** Added guard in the evidence loop:
```python
if rec.result.run_id.startswith("failed_verification"):
    continue
```

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py` | ~3 | `on_iteration` moved before pivot break |
| `loop.py` | ~1 | `run_id` field on signature |
| `loop.py` | ~1 | `self._run_id = run_id` in `run()` |
| `loop.py` | ~1 | `run_id=self._run_id` in `Evidence()` |
| `loop.py` | ~2 | Skip AST-failure records in evidence loop |
| `service.py` | ~1 | `run_id=record.id` passed to `loop.run()` |
