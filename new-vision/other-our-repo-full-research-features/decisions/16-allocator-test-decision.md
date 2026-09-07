# Decision — Row 16 capital-allocator-worker test gap (acknowledged 2026-09-07)

> `04:394` only `run_capital_allocator_cycle` tested, not `while True: cycle(); sleep(900)` loop.

## Status

- Worker proven in practice (`tests/test_capital_allocator_worker.py:5` pass). Loop scheduling remains manual `logs -f vinu-agent` check per `03-how-to-start.md:82`.
- Backlog: add `tests/test_capital_allocator_worker_loop.py` mocking interval and kill-switch to reach 80%.

## Dated

- 2026-09-07 — acknowledged, not blocking gate.
