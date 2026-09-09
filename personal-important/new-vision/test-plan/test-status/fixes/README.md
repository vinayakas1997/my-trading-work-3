# Fixes — per-fail mini notes, deletable per run_id

> When a stage `fail` is later fixed, create `2026-09-07_AAPL_sweep_FAIL_retry.md` here:
>
> ```md
> # 2026-09-07 AAPL sweep verdict FAIL → fix
> - Failure: completeness 0.4 <0.7 fail-closed
> - Fix: widened params grid in sweep.py:159, K=3→4
> - Commit: 0c7cbb19
> - Evidence after fix: TickerLedger row 123, run_id abc
> ```
>
> Delete per `test_run_id` (e.g. `rm fixes/2026-09-07_ats_6mo_*`) or whole `test-status/` after gate green is copied to `pending Status`. `decisions/` + `04-v2` stay (permanent).
