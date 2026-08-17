# Logs

Raw console output, one file per phase/service. Create files during runs:

- `00-preflight.log` — Phase 0
- `01-unit-<service>.log` — Phase 1 (per service)
- `02-smoke-<block>.log` — Phase 2 (per block)
- `03-e2e.log` — Phase 3

Logs here are raw; curated summaries live in `../results/`.
