# Test Status Ledger — human-readable

> Append-only, one row per `(test_run_id,ticker,stage)` — mirrors `TickerLedger` `04:128` discipline but for test harness. `UNIQUE(test_run_id,ticker,stage)` — re-running same ticker/stage same run updates same row, never duplicates, so `kill -9` resume is `get_pending(test_run_id)`.

| test_run_id | ticker | stage | status | timestamp | evidence_ref | notes | fixed_by | fixed_how |
|---|---|---|---|---|---|---|---|---|
| `2026-09-07_ats_6mo` | AAPL | watchlist_gate | pass | `2026-09-07T...` | `TickerSummaryStore AAPL source_run_id abc` | | | |

- `status`: `pass` | `fail` (never `pending` on write — pending is absence of row)
- `evidence_ref`: real store row it produced (`artifact_id art_...`, `run_id ...`, `flag_id`, `TickerLedger row id`)
- `notes`: only on `fail` — specific enough to turn directly into bug report, not "didn't work"
- `fixed_by`: `commit <sha> <file:line>` when fail later fixed
- `fixed_how`: what widened / wired / tuned (e.g. `loop.py:_run_paper_rehearsal 7d` / `K=3→4`)

Delete whole folder after gate `green` is copied to `pending Status`, or per `test_run_id` individually.
