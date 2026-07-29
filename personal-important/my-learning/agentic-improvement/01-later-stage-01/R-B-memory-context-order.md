# R-B: Memory Context — Exclude In-Flight Run

## Bug

`service.py:96-108` inserted the new `ResearchRunRecord` (status=`RUNNING`) into SQLite *before* querying `get_past_run_summaries()`. The underlying `list_runs()` only filters by `status != STATUS_DELETED` — so the current `RUNNING` run appeared in the past-run results with Sharpe 0.00 and 0 iterations:

```
Your past runs for JPM:
  Run #3: <this same idea> → Sharpe 0.00, 0 iters, status=running
  Run #2: momentum → Sharpe 0.82, 3 iters
  Run #1: breakout → Sharpe 0.35, 2 iters
```

The LLM saw the current run listed as a prior failure, wasting one of the 5 memory slots and injecting misleading context.

## Fix

Moved the `get_past_run_summaries()` call **before** `insert_run()` + `update_run()`. The past-run query now only sees runs that completed before this one started.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `service.py` | 96-108 | Block of 13 lines relocated: memory query before insert |
