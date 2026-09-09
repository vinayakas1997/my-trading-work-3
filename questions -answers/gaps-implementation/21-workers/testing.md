# Testing - 21-workers (mute+version)

Command: python3 -m pytest vinu-agent/tests/ -q -k "significance"
Expected: 44 passed, mute true version pinned.
Actual: 44 passed, version test123 muted true.
Status: green for mute+version, red for audit pending.
Proof log: build output 2026-09-09.
Note: audit pending separate.
