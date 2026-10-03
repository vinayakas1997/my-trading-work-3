# The inconsistencies v2

The main file is **01**. The rest support it.

| File | What it is |
|---|---|
| `01-inconsistencies-v2.md` | **Main.** The list of inconsistencies found in the system, with fixes proposed. |
| `02-logic-audit-2026-10-02.md` | Audit notes; dated UPDATE blocks record what was checked and fixed. |
| `03-implementation-plan.md` | The order the fixes are built in. |
| `04-implementation-status.md` | Progress: per item, the files touched, tests and known limits. |
| `05-fail-open-fail-closed-matrix.md` | For each check, whether it lets an order through or stops it when its input is missing. |
| `06-live-behavior-flags.md` | Every opt-in switch that changes live behavior, and a suggested order to turn them on. |

Fixes go into `vinu-components/`. When every point in a file is fixed, its name gets a `(comp)-` prefix.
