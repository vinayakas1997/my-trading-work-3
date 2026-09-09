# Implementations — Batch Evidence Index for A-J

> Each `batch-*.md` here proves one batch of A-J fixes: `source file:line → dest file:line` + commit SHA + `pytest` green line + how to verify (store `TickerSummaryStore` / `TickerLedger` `ref_id`). Create one file per batch when it merges; update `inefficiencies-A-J.md` Status `open → built <sha>`.

## Planned batches (cost first)

| Batch file | Covers | When |
|---|---|---|
| `batch-cost-BDE.md` | `B` planner batch + `D` feature/angle cache + `E` vectorized sweep | First — saves most LLM $ for next `2026-10-01` 28-angle harness |
| `batch-latency-FG.md` | `F` allocator retry window + `G` auto `cycle_shock_batch` wiring | Second — latency |
| `batch-ledger-HJ.md` | `H` TickerLedger `ref_id` join verify + `J` portfolio double-fetch cache | Third — ledger/I/O |
| `batch-infra-AI.md` | `A` double-write dedupe + `I` final `env_file` gap remove (if you later drop `env_file` for secrets) | Last — infra |

## Template per batch file

```md
# Batch Cost B+D+E — 2026-09-07

## Source → Dest

- B: `planner_triage_hook.py:K=3` → `scheduler_workers.py:batch_triage` …
- D: `loop.py:236 get_angle_context` + `244 get_feature_snapshot` → `cache_key research_from:research_to` …
- E: `sweep.py:135 POST loop` → `VectorBT` matrix `03/vectorbt-sweep.md` …

## Commits

- `sha` `feat(planner): batch triage`

## Tests

- `pytest vinu-research/tests/test_loop.py -q` 57 green
- `pytest vinu-agent/tests/test_{...}` pass

## How to verify

- `TickerSummaryStore` last-write-wins no longer duplicates; `features-api:8082` called once per `research_from:research_to`
```

Delete `test-plan/test-status/` per `run_id` after gate green; keep this folder forever (like `04-v2`).
