# Testing - 17-ui (checkbox+drill+banner+csv)

Command:
- python3 scripts/ui-status.py --symbol AAPL --granularity 1D
- python3 scripts/ui-status.py --csv /tmp/ui-status.csv
- touch HALT + run, expect exit 2 banner
Expected: 27/27, CSV rows, HALT banner exit 2.
Actual: 27/27, CSV ok, banner exit 2 verified.
Status: green for checkbox+drill+banner+csv, red for page pending.
Proof log: build output 2026-09-09.
Note: pipeline 0-7 page pending separate.
