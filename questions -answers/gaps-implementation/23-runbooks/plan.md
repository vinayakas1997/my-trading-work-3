# Plan - 23 Runbooks ATS vs Full

Goal: Rerun rule pinned, no confusion.

Files touched (docs only):
- `new-vision/test-plan/ats-pattern/04-ats-runbook.md:1` ATS 15min.
- `new-vision/test-plan/full-pattern/03-full-runbook.md:1` Full 2022 0-7.
- `05-go-live-gate.md`, `04-edge-cases.md`, `02-preflight`, `01-scope`.
- `04-v2` diagram + `04-full-progress-db-plan.md`.

Steps:
1. Keep ATS docs + scripts. Rerun ATS after docker before Full.
2. Full needs 07-20 fixes to PASS. Build prompt->sweep->top3->paper->risk->monitor->broker.
3. Delete test-status per run_id after green. Keep ledger + 01-25 forever.

Knobs: STAGE1_START ATS short vs Full 2022, TIER2 3mo, SEED AAPL,MSFT,NVDA, timers fast (see 10).
Acceptance: ATS 14min green before Full, Full 30min+ PASS, folder small.
