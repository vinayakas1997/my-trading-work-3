# Status - 17-ui

Date: 2026-09-09
State: done (CLI v1: checkbox+drill+banner+csv+pipeline; web v2 later)
Owner: agent build
Doing: read-only CLI done. Next pipeline 0-7 page + HALT banner.
Done:
- scripts/ui-status.py: --all checkbox, --symbol/granularity 1 SELECT, --run-id drill, read-only mode=ro.
- 1D excludes trend_session_structure by design -> AAPL 1D 27/27.
Bugs found while implementing: AAPL 1D raw 28 includes trend_session_structure row, excluded per spec.
Other files touched:
- scripts/ui-status.py (new)
Next: web UI v2 (freqUI tables, plots, 10s refresh) after proofs.
Done2:
- ui-status.py: HALT banner (exit 2) + --csv export, verified.
Done3:
- ui-status.py: --pipeline 0-7 ledger view, AAPL real ATS stages verified.
