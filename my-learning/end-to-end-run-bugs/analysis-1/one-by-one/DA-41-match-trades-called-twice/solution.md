# DA-41 🟠 `match_trades` Called Twice With Same Trades

**Component:** `vinu-simulator`
**Files Changed:** `service.py`, `attribution.py`

## Problem

`match_trades()` is a CPU-intensive function that sorts trades and builds round-trips via FIFO matching. It was called twice with the same `result.trades`:

1. `service.py:417` — `match_trades(result.trades)` for validation (Monte Carlo permutation)
2. `service.py:443` → `attribution.py:115` — `by_symbol_stats(result.trades)` called `match_trades(result.trades)` internally

Each call re-sorted and re-matched the full trade list.

## Root Cause

`by_symbol_stats()` had no way to accept pre-computed round-trips. It always called `match_trades()` internally.

## Solution

Added optional `round_trips` parameter to `by_symbol_stats()`:

```python
def by_symbol_stats(
    trades: list[Any],
    *,
    round_trips: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, float]]:
    if round_trips is None:
        round_trips = match_trades(trades)
```

In `service.py`, pass the already-computed `round_trips`:

```python
symbol_attribution = by_symbol_stats(result.trades, round_trips=round_trips)
```

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `attribution.py:114-120` | 7 | Added optional `round_trips` param to `by_symbol_stats()`; skip `match_trades` when provided |
| `service.py:443` | 1 | Pass pre-computed `round_trips` instead of `result.trades` |

## Verification

92 simulator tests pass (0 failures).
