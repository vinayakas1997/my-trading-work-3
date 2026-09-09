# Agent Instructions - Gaps Implementation (2026-09-09)

Simple English. Every agent must follow this.

## Folder
`questions -answers/gaps-implementation/`
Top: this file + `00-STATUS-ALL.md`.
Subs: `02-llm-400/` to `25-money-gate/` (21 folders).
Each sub has `plan.md`, `status.md`, `testing.md`.

## Rules
1. Read source doc first. Example `03` reads `../03-vectorbt-not-connected.md` + `../07-sweep-grid-7-inefficiencies.md` + `../08-advanced-sweep-adopt.md`.
2. Small steps, one gap at a time. Do not mix gaps.
3. Fail-closed. Never guess money, size, or PASS. Missing data = STOP + reason.
4. No secrets in code. Keys only in `secrets/*`. URLs + intervals only in `.env`.
5. Never commit `data/*`, `*.db-shm`, `*.log`, `.env` values. Docs + code only.
6. Update `status.md` same day. Update `testing.md` with command + green/red.
7. Update top `00-STATUS-ALL.md` when folder status changes open/doing/done.

## Order
1. Prompt link `07 No.4+No.2` + vectorbt fast `08 step1` + writer 1 to 9 `09 step5`. Unlocks PASS.
2. Paper-days + promote best `11`, 7-day honest `12 1-4`, risk tail vol `13 Now`, storage full `14 1-4`.
3. Monitor HALT entries-only + time-stop `15 1-2`, broker fills parity + kill `16 1-2`, UI checkbox `17 1-2` + `04` DB.
4. Data PIT + gap + failover `18 1-3`, portfolio DD + regimes `19 1-2`, learning lesson + calibration `20 1-2`.
5. Workers/infra/runbooks `21,22,23`, corners `24 Sec2-5`, money gate enforce `25`.

## plan.md template (each folder)
- Goal 1 line.
- Files touched file:line.
- Steps 1-4.
- Knobs added.
- Acceptance: what proves done.

## status.md template
- Date, doing/done.
- Bug found + fix.
- Other files touched.

## testing.md template
- Command run.
- Expected vs actual green/red.
- Proof log path.

## Git per gap (agreed, not add .)
1. `git status --short`, `git diff --stat`, `git log --oneline -5`.
2. Stage only that folder + code: `git add questions\ -answers/gaps-implementation/<folder>/plan.md ...`.
3. Commit: `git commit -m "docs(gaps): finish XX <what> + tests green"`.
4. Push `git push origin main` only when testing green. Hooks reject = fix + new commit, no amend.
