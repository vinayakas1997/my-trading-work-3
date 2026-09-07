# Decision — Row 7 Untuned caps (decided provisional 2026-09-07)

> `04:406-408` N/K/completeness/interval — chosen provisional, tunable without redeploy via env.

## Chosen (first-pass, unvalidated — same category as every other threshold)

- **N sweep-refine rounds:** `max_iterations=5` `vinu-research/config.py:16` (loop tries up to 5 refinements, early-stop on STOP/PASS)
- **K per ticker per cycle:** shared counter `planner_triage_hook.py` `K=3` (watchlist + Thesis Intake share) — cheap gate before LLM call
- **Completeness threshold:** implicitly `completeness >=0.7` via sweep `validation` fail-closed below threshold (treat partial grid as FAIL `04:243`)
- **capital_allocator cadence:** `900s` `vinu-agent/config.py:89` (5-15min band `04:410`), `planner 1800s`, `significance 900s`, `skill_audit/shadow 3600s` — inside design doc open band, not settled as final
- **Holdout 20% + gap 5d**, **walk_forward 3 windows expanding**, **rehearsal 7d lookback degradation 0.5**

## Why provisional acceptable now

- All are env knobs (`VINU_RESEARCH_MAX_ITERATIONS`, `VINU_AGENT_PLANNER_INTERVAL`, etc.) — tuning against real cost/latency/data-reliability numbers can happen live without code change.
- Track in `other-our-repo-full-research-features/02-adoptable` hyperopt backlog for future tightening.

## Status

- Decided provisional 2026-09-07 — not untuned anymore, but expect retuning after first full cycle logs.
