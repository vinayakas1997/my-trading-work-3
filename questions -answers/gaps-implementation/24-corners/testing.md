# Testing - 24-corners (Sec1+Sec2)

Command:
- cat vinu-agent/entrypoint.sh + vinu-live/entrypoint.sh (workers wired)
- python3 run_pipeline.py --help
- bash scripts/setup-secrets.sh --check
Expected: workers present, help works, secrets ok.
Actual: agent/live workers wired, help works, secrets all present.
Status: green for Sec1+Sec2, red for Sec3-5 pending.
Proof log: build output 2026-09-09.
Note: Sec3-5 pending separate.
