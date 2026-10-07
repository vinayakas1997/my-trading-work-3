# Situation 1: what actually happens when many orders for the same symbol race for `max_daily_orders`?

## Question

`vinu-agent/vinu_agent/broker/daily_limits.py`'s own docstring already admits
a check-then-act race exists between `OrderGuard.check()` reading
`count_today()` and `pre_approve()` later calling `record_order()` (an
UPDATE-or-INSERT), and explicitly reasons about the worst case: *"two orders
for the same symbol in the same instant both undercounting by one) is an
occasionally-too-permissive daily cap, not money moving while halted."*

That's a reasoned guess, not a measurement. So: what does it actually do
under real concurrency — does the cap actually get exceeded, by how much,
and is "a slightly too-permissive cap" really the worst outcome?

## Where

- `vinu-agent/vinu_agent/broker/daily_limits.py::record_order()`
- `vinu-agent/vinu_agent/broker/order_guard.py::check()` / `pre_approve()`

## How tested

Real code, not mocks of the thing under test: a temp SQLite file, a real
`TradingMandate(max_daily_orders=5)`, and 30 threads each constructing their
own fresh `OrderGuard` + `DailyLimitStore` pointed at the same DB file (this
mirrors production exactly — `trade_tool.py` constructs a fresh `OrderGuard`
per `execute()` call) and calling `guard.pre_approve("AAPL", "buy", qty=1,
price=100.0)` concurrently. Only the broker (`get_account`) was mocked;
everything else — the guard, the mandate, the real SQLite store, real
threads — is the genuine code path.

```python
threads = [threading.Thread(target=worker) for _ in range(30)]
# worker(): DailyLimitStore(same db path) -> OrderGuard(...) -> guard.pre_approve(...)
```

## Observed

```
max_daily_orders = 5
concurrent submissions attempted = 30
approved (guard said yes) = 1
rejected (guard said no) = 0
final order_count persisted in DB = 1
OVERSHOOT = 0
```

But that summary hides the real story — 28 of the 30 threads didn't cleanly
approve *or* reject. They crashed with unhandled exceptions:

```
sqlite3.OperationalError: database is locked
  File ".../order_guard.py", line 787, in pre_approve
    self._increment_daily_count(symbol, value)
  File ".../order_guard.py", line 154, in _increment_daily_count
    self._daily_limit_store.record_order(symbol, value)
  File ".../daily_limits.py", line 97, in record_order
    conn.execute("UPDATE daily_limits SET order_count = ?, ...")
```

and, more precisely — a genuine logical race in `record_order()`'s own
read-then-write, not just SQLite file-lock contention:

```
sqlite3.IntegrityError: UNIQUE constraint failed: daily_limits.symbol, daily_limits.date
  File ".../daily_limits.py", line 102, in record_order
    conn.execute("INSERT INTO daily_limits (symbol, date, order_count, volume) VALUES (?, ?, 1, ?)")
```

That `IntegrityError` is the smoking gun: two threads' `record_order()` both
ran the `SELECT ... WHERE symbol = ? AND date = ?`, both got zero rows back,
and both then tried to `INSERT` — the exact TOCTOU race the module's
docstring anticipated, just caught in the act with a real stack trace instead
of reasoned about.

Neither exception is caught anywhere between `record_order()` and
`trade_tool.py`'s outer `except Exception as exc:` — which means, traced all
the way up: a burst of *legitimate, already-guard-approved* concurrent orders
for the same symbol would come back to the LLM as `{"status": "error",
"error": "database is locked"}`, indistinguishable from a real infrastructure
outage, for orders that never violated any actual limit.

## Verdict: surprising — the code's own risk assessment was wrong about the failure mode

The docstring's reasoning ("worst case is an occasionally-too-permissive
cap") assumed the race would manifest as *silent overcounting*. It doesn't —
SQLite's own locking turns the race into *loud, unhandled crashes* instead,
and the measured overshoot was actually **zero** (undershoot, if anything:
only 1 of 30 legitimate orders got through cleanly). So the actual risk
isn't "the cap is slightly too soft," it's "a burst of legitimate concurrent
orders for the same symbol mostly come back as spurious errors" — a
reliability problem, not a safety one (no order was ever double-approved or
approved-while-over-cap in this run), but a real gap in exactly the kind of
burst-trading scenario (several strategies or a strategy + a human both
acting on the same symbol at once) this system is meant to handle.

## Update: fixed and re-verified against the same 30-thread harness

The user asked for this one to actually be fixed rather than just recorded.
Two layered fixes were needed — the second only showed up once the first was
in place, which is itself worth recording:

1. **`record_order()` rewritten as a single atomic upsert**
   (`INSERT ... ON CONFLICT (symbol, date) DO UPDATE SET order_count =
   order_count + 1, volume = volume + excluded.volume`) instead of
   `SELECT` then conditional `INSERT`/`UPDATE`. This removed the
   `IntegrityError` completely — zero occurrences across 30+ re-runs.

2. **The `OperationalError: database is locked` survived fix #1.**
   Diagnosed with a real per-thread timing script
   (`diagnose_lock.py`/`diagnose_lock2.py`): the failing threads errored in
   under 3ms, far too fast to be a genuine 5-second `busy_timeout`
   exhaustion — so the busy handler wasn't actually covering the failure.
   Two changes closed it:
   - `vinu_infra/sqlite.py::_get_conn()`: pass `timeout=5.0` to
     `sqlite3.connect()` and set `PRAGMA busy_timeout=5000` *before*
     `PRAGMA journal_mode=WAL`, so the busy handler is armed before any
     other statement runs on a fresh connection (this alone did not fully
     close the gap on Windows, but is a correct fix in its own right and
     was kept).
   - `daily_limits.py::record_order()`: a small retry loop (5 attempts,
     exponential backoff + jitter) around the upsert, catching only
     `sqlite3.OperationalError` whose message mentions "locked"/"busy" —
     the standard, well-known mitigation for this exact SQLite pattern,
     needed because the observed sub-3ms failures indicate OS-level lock
     contention on Windows that isn't always routed through SQLite's own
     internal retry.

**Re-verified**: the same 30-thread real-SQLite harness (both a
brand-new/never-initialized db file and a pre-existing one, the harder and
easier cases respectively) run 15+ times each after the fix, plus a new
permanent regression test
(`tests/test_daily_limits.py::TestRecordOrderUnderRealConcurrency`) added to
the suite — zero errors, correct final count (30) and volume every time.
Confirmed via `git stash` that the fix touches nothing else: the vinu-agent
suite's 17 pre-existing unrelated failures (`test_llm.py`,
`test_order_guard.py::TestOrderThrottle`, `test_service.py`,
`test_capital_allocator_hook.py`) are identical with and without this
change.

Kept the original "surprising" verdict above as the historical record of
what was actually found — this section is the fix that followed it.
