# Testing - 22-infra (retry+secrets)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "tool"
- bash scripts/setup-secrets.sh --check
Expected: 2 passed, all secrets present.
Actual: 2 passed, all present.
Status: green for retry+secrets, red for slim pending.
Proof log: build output 2026-09-09.
Note: slim pending later window.
