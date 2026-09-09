# Testing - 09-top3-9 (diversity+writer)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "comparison or rank"
- python3 -m pytest vinu-agent/tests/ -q -k "artifact_writer or research_pass"
Expected: 24 + 9 passed, top3 per interval capped.
Actual: 24 + 9 passed, 4->3 cap verified 5 ids.
Status: green for diversity+writer, red for regime pending.
Proof log: build output 2026-09-09.
Note: regime+freeze+corr pending separate.
