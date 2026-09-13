# Situation 2: does the ingest-loop crash-isolation fix actually survive a real crash?

## Question

A background agent (delegated during the deep pipeline audit,
`other-repos-world/research-discussion-v2/`) claimed to fix finding #20: the
live ingest `while True` loop in `vinu-stock-price/vinu_stock/cli.py` had no
exception handling, so one bad cycle killed the entire worker. It reported
"51→57 tests passed." That's the agent's self-report — does the actual fixed
loop survive a real crash, end to end, or does it just look right in a diff?

## Where

`vinu-stock-price/vinu_stock/cli.py::ingest_main()`, the `while True:` loop
(lines 113-122).

## How tested

Called the REAL `ingest_main()` function directly (not a reimplementation of
its logic) with a fake `StockService` whose `run_live_cycle()` raises a
`KeyError` on the first call (exactly the shape of crash finding #21 was
about — `_parse_bar_row`'s raw `row["o"]` indexing on a malformed response)
and succeeds on later calls. `time.sleep` was faked to raise `SystemExit`
after 3 calls, purely to stop the intentionally-infinite loop for the test.

```python
def run_live_cycle(self):
    calls["run_live_cycle"] += 1
    if calls["run_live_cycle"] == 1:
        raise KeyError("'o'")
    ...
```

## Observed

```
ERROR:root:Ingest cycle failed (will retry next interval): "'o'"
Traceback (most recent call last):
  File ".../cli.py", line 116, in ingest_main
    run_cycle(service)
  ...
KeyError: "'o'"
cycle 2 ok
cycle 3 ok
Loop stopped as expected: test: stop after 3 cycles
run_live_cycle was called 3 times
sleep was called 3 times
PASS: loop survived the KeyError and kept cycling
```

The crash on cycle 1 is logged with a full traceback (`exc_info=True`, so an
operator watching logs sees exactly what broke), then the loop proceeds to
sleep and retry on cycle 2, which succeeds normally.

## Verdict: fix confirmed working, as claimed

This one matches expectations — worth recording anyway, because "the agent
said it passed its own tests" and "the fix actually survives a real crash
end-to-end when driven through the real entry point" are different levels of
confidence, and only the second is what an auditor should sign off on.
