# Testing - 21-workers (mute+version+audit)

Command: python3 -m pytest vinu-agent/tests/ -q -k "skill_audit or significance"
Expected: 51 passed, mute true version + hash snapshot.
Actual: 51 passed.
Status: green for mute+version+audit, red for notify pending.
Proof log: build output 2026-09-09.
Note: notify protocol pending separate.
