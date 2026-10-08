# Proper-Project-Implementation

- `00-project-understanding/` : project aim, and the vision (with Part D, the 24-hour system).
- `01-sequence-diagrams/` : 8 sequence diagrams and the vision-to-diagram coverage matrix.
- `02-functional-and-non-functional-requirements/` : one file, one section per service.
- `03-guards-configs-and-settings/` : `current-settings.md` (every setting by component and kind, with reasons) and `target-settings-real-system.md` (how it should look for the real 24-hour system).
- `04-problem-log-and-guard-tests/` : `problem-log.md` (28 entries, each with its guard test), `how-to-use-this-log.md` (the rules), checked by `vinu-components/scripts/check_problem_log.py`.
- `05-handling-system-portfolio-allocator/` : `plan.md` (the self-isolated allocator: real-money base, capital ledger, the maths, paper/real tagging, implementation status).
- `06-data-audit/` : per component, every kind of data (producer, store, format, route, consumers, verdict) and `findings.md` (news done as the pilot; the rest follows the pipeline order).
- `07-news-layers/` : `plan.md` (the five-layer news system: sources, per-source duplicates, cross-source stories, facts per story, the table consumers read; layer 1 built).
- Still to do: the 8 unguarded fixes in the log, the controlled-versus-default mark in `03`, `.env` sync into `.env-example` (needs permission).
