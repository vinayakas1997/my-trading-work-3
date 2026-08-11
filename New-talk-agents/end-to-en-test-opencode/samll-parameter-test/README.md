# vinu-components Test Documentation

Folder for documenting the full end-to-end testing of the vinu-components stack, with an emphasis on capturing **when components do not behave as documented**.

## Navigation

| Path | Purpose |
|---|---|
| `plan.md` | The test plan (parameters, phases 0–5, service table) |
| `run-summary.md` | One-page verdict per run (date, env, totals) |
| `results/` | Curated pass/fail per phase and block |
| `deviations/` | "Didn't work like that" — expected vs actual behavior (one file per item) |
| `issues/` | Real bugs/defects worth fixing (one file per item) |
| `logs/` | Raw console output, one file per phase/service |
| `evidence/` | Raw proof: HTTP responses, logs, parquet/JSON samples |
| `open-gaps-for-future.md` (parent folder) | Known gaps from architecture.md §8 + things still to fix |

## Workflow

1. Run a phase per `plan.md`.
2. Capture raw output into `logs/` and raw payloads into `evidence/<phase>/`.
3. Record the outcome in `results/<block>.md` and the master `results/results-table.md`.
4. If behavior differs from docs: create `deviations/DEV-NNN-<slug>.md` and add a row to `deviations/index.md`.
5. If a real defect is found: create `issues/ISSUE-NNN-<slug>.md` and add a row to `issues/index.md`.
6. Update `run-summary.md` at the end of the run.

## Naming

- Deviations: `DEV-001-<short-slug>.md`
- Issues: `ISSUE-001-<short-slug>.md`
- Evidence: `evidence/<phase>/<service-or-block>-<description>.<ext>`
