# S-12: Live-Trading Kill Switch — Explanation & Status

## What It Is

A simple file-based circuit breaker for the live-trading order execution path.

## Components

1. **`_execute_plan()` in `vinu_live/scheduler.py`** — before submitting any orders, checks for the existence of a HALT file at `~/.vinu-live/HALT`.

2. **Behavior when HALT file exists**:
   - Logs a warning: `"HALT file detected at {path} — skipping order execution"`
   - Returns an empty list immediately
   - No orders are submitted to the exchange

3. **Behavior when HALT file is absent**:
   - Execution proceeds normally

## Usage

```bash
# Halt all order execution
touch ~/.vinu-live/HALT

# Re-enable execution
rm ~/.vinu-live/HALT
```

## Current Status: ✅ IMPLEMENTED

Wired into `_execute_plan()` and active in the live-trading scheduler.
