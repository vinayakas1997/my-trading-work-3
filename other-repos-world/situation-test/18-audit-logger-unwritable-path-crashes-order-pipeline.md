# Situation 18: does an audit-log write failure crash the order it's logging?

## Question

`AuditLogger.log()`'s own docstring recounts a previous real incident:
"Before the fix, every order (rejected or executed) raised OSError writing
the audit entry and masked the real trade response with a 500" -- fixed at
the time by pointing `LOG_PATH` at the container's actual writable mount
instead of a hardcoded read-only path. That fixed the *known* cause of a
universal failure. But does `log()` itself tolerate a *transient* one --
disk full, a permissions change, the data directory vanishing at the wrong
moment? And more specifically: are `trade_tool.py`'s many `AuditLogger.log()`
call sites individually protected, or does the method being told to fail
gracefully even matter if nothing calls it inside a `try`?

## Where

`vinu-agent/vinu_agent/broker/kill_switch.py::AuditLogger.log()` +
every one of its call sites in
`vinu-agent/vinu_agent/tools/trade_tool.py::TradeTool.execute()` (most of
which -- the invalid-qty check, the symbol-grounding pause, the guard
rejection, the reauth pause -- are NOT inside the method's one internal
`try/except Exception` block, which only wraps the actual submission
sequence near the end).

## How tested

Real `AuditLogger.LOG_PATH` pointed at a path whose *parent* is an actual
file (not a directory) -- so `Path.mkdir(parents=True)` raises a real,
reproducible `OSError` (`FileExistsError` on Windows,
`NotADirectoryError` on POSIX), not a mocked exception. Then called the
real `TradeTool.execute()` with an invalid qty -- the very first check in
the method, hitting an `AuditLogger.log()` call with zero exception
handling around it anywhere between it and the caller.

```python
with patch.object(AuditLogger, "LOG_PATH", bad_log_path):
    tool.execute(symbol="AAPL", qty=-5, side="buy")
```

## Observed (before the fix)

```
execute() RAISED: FileExistsError: [WinError 183] Cannot create a file
when that file already exists: '...\vinu_situation_bogus_file.txt'
```

A filesystem hiccup on a purely observability-side-effect (writing a log
line) crashed the entire order-rejection response -- the caller (the LLM's
tool call) would see a raw exception / 500 instead of the correct
`{"status": "rejected", "reason_code": "invalid_qty"}`, for an order that
was never even going to reach the guard or the broker.

## Verdict: real bug, fixed

**Fixed**: `AuditLogger.log()` now wraps its own `mkdir` + file write in
`try/except OSError`, logging the failure via the regular application
logger (`logger.exception(...)`) instead of raising -- and the audit
content itself is still emitted via `logger.info("AUDIT: ...")`
unconditionally either way, so a write failure loses durability (it won't
be in the structured audit file) but not the content (it's still in the
process logs). This matches the fail-open-for-non-critical-dependencies
posture already established everywhere else in this codebase
(`order_guard.py`'s override/limit stores, risk-budget fetch, portfolio
concentration check all fail open on their own I/O problems) -- the audit
log had simply never been brought into that same posture, despite being
exactly the kind of secondary side effect that posture exists for.

Fixed at the single shared method rather than patching each of
`trade_tool.py`'s many individual call sites (and every other caller across
the codebase -- `order_guard.py`, `fact_audit.py`, the admin routes) --
one change protects all of them. Re-ran the same failing scenario after
the fix: `execute()` now returns the correct
`{"status": "rejected", "reason_code": "invalid_qty"}` response, with the
write failure logged via `logger.exception` instead of propagating. Added
two permanent regression tests
(`tests/test_kill_switch.py::TestAuditLoggerFailsOpenOnUnwritablePath`): a
direct unit test of `AuditLogger.log()` against a real unwritable path, and
an end-to-end test confirming the real `TradeTool.execute()` invalid-qty
path specifically survives it. Full `test_kill_switch.py` (7 passed),
`test_trade_tool.py` (24 passed), `test_trade_tool_audit_trail.py`,
`test_fact_audit.py`, and `test_kill_switch_reduce_only_exemption.py`
(50 passed combined) all still pass -- no regressions from touching a
method this widely called.

This is the third real bug found in this audit that traces back to
existing code in this session's own area of focus (`vinu-agent`'s trading
pipeline) -- following situation 15 (`order_guard.py`) and situation 17
(my own earlier #6 fix) -- each found by actually running a realistic
failure scenario rather than trusting what the code or its existing tests
implied.
