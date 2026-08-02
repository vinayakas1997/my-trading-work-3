# peer-cross-asset-comparison — Test Log

**Status:** Not started.

## What will be tested / Expected output

- `POST /analysis/run/{ticker}?angle_names=<new angle name>` returns
  `{"status": "completed", "row_count": N}` with `N > 0` for AAPL, TSLA,
  and JNJ (run sequentially, not concurrently).
- `GET /analysis/angle/<new angle name>/AAPL` returns correlation values
  bounded in [-1, 1], not constant across the whole series.
- JNJ (chosen in Stage 1 specifically to break the tech correlation)
  should show visibly lower correlation to AAPL/TSLA than they show to
  each other. If it doesn't, the computation is suspect, not JNJ.
- Full detail: [../../scope-responsibilities/01-peer-cross-asset-comparison.md](../../scope-responsibilities/01-peer-cross-asset-comparison.md)

## Bug / Fix Log

_Nothing logged yet — testing has not started._
