# Proper-Project-Implementation

- `00-project-understanding/` : project aim, and the vision (with Part D, the 24-hour system).
- `01-sequence-diagrams/` : 8 sequence diagrams and the vision-to-diagram coverage matrix.
- `02-functional-and-non-functional-requirements/` : one file, one section per service.
- `03-guards-configs-and-settings/` : `current-settings.md` (every setting by component and kind, with reasons) and `target-settings-real-system.md` (how it should look for the real 24-hour system).
- `04-problem-log-and-guard-tests/` : `problem-log.md` (28 entries, each with its guard test), `how-to-use-this-log.md` (the rules), checked by `vinu-components/scripts/check_problem_log.py`.
- Still to do: the 8 unguarded fixes in the log, the controlled-versus-default mark in `03`, `.env` sync into `.env-example` (needs permission).
