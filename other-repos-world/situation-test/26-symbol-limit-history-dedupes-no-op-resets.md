# Situation 26: does re-setting a limit override to the same value spam the audit history?

## Question

`SymbolLimitStore.set()`'s docstring claims "every field that actually
*changes* value gets one `symbol_limit_history` row" -- implying a
redundant `.set()` call with the same values (e.g. an idempotent API
retry, or an operator re-confirming a limit that's already in place)
should NOT add a spurious history row. Real question: does the actual
comparison correctly no-op on a genuine repeat, or does every `.set()`
call log unconditionally regardless of whether anything changed?

## Where

`vinu-agent/vinu_agent/broker/symbol_limits.py::SymbolLimitStore.set()`,
the `if old != new: history_rows.append(...)` check.

## How tested

Real `SymbolLimitStore` against a temp SQLite file: set `max_order_value`
to $1000 (a real change from nothing), set it to $1000 again (no real
change), then to $500 (a real change).

## Observed

```
{'field': 'max_order_value', 'old_value': None, 'new_value': 1000.0, 'reason': 'initial'}
{'field': 'max_order_value', 'old_value': 1000.0, 'new_value': 500.0, 'reason': 'tightened'}
total history rows: 2
```

The redundant middle `.set()` call (same value, different `reason` text)
produced zero history rows -- only the two calls that actually changed the
stored value did.

## Verdict: matches the documented design

Confirms `set()` is genuinely idempotent from an audit-trail perspective:
"AAPL's max_order_value went from $1000 to $500" stays answerable without
noise from operationally-redundant re-confirmations, even though the
`reason`/`set_by` metadata on the *current* record (from `upsert`) is still
updated on every call regardless.
