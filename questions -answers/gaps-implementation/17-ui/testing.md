# Testing - 17-ui (checkbox)

Command:
- python3 scripts/ui-status.py --symbol AAPL --granularity 1D
- python3 scripts/ui-status.py --all
Expected: AAPL 1D 27/27, all [x].
Actual: AAPL 1D 27/27, all [x] for 6 tickers.
Status: green for checkbox+drill, red for page/banner pending.
Proof log: build output 2026-09-09.
Note: page/banner/CSV pending separate.
