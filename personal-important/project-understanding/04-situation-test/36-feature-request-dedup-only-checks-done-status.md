# Situation 36: identical concurrent feature requests all run, none deduped

**Question**: `vinu-tools`'s `service.py::submit()` computes a `request_hash`
and checks `storage.get_by_hash(request_hash, status=STATUS_DONE)` before
inserting a new row — dedup against an already-*completed* identical
request. What happens when several identical requests arrive while the
first is still pending/running (or arrive at the exact same instant)?

**Where**: `vinu-tools/vinu_tools/service.py` (~line 124-129, the
submit-time hash check) and `vinu_tools/storage/sqlite_backend.py`
(`insert_request` — a plain `INSERT`, no uniqueness constraint on
`request_hash`, no `WHERE NOT EXISTS` guard).

**How tested**: real `SqliteBackend` instances (one per simulated caller,
mirroring separate real processes/threads), 10 real `threading.Thread`s all
racing to submit the identical `request_hash` against the same on-disk
SQLite file, synchronized with a `threading.Barrier` so all 10 check-then-
insert at effectively the same instant:

```python
def worker():
    b = SqliteBackend(db_path)
    barrier.wait()
    existing = b.get_by_hash("samehash", status="done")
    if existing is None:
        b.insert_request(req, request_hash="samehash", features=["SMA_9"])
```

**Observed**: **10 out of 10** threads inserted a separate row (ids 1-10) —
zero deduping, every one of the ten identical requests becomes its own
PENDING job the worker will independently compute. Notably, this isn't
purely a race-timing artifact: even two plain sequential calls to `submit()`
(no threading at all) produce the same outcome, because the *existing*
production code only ever checks for a match with `status == STATUS_DONE` —
a duplicate that's merely PENDING or RUNNING was never deduped in the first
place, race or not.

**Verdict**: **real gap, flagged rather than fixed** (unlike situations
33-35, this is a genuine design-intent ambiguity, not an unambiguous
defect). Two readings are both plausible and neither is clearly wrong:
(a) a bug — the same identical request submitted twice in quick succession
should reuse the in-flight job rather than doing the same compute-heavy
feature calculation twice, or (b) intentional — a caller might want to
force a fresh recomputation of a request that appears stuck, and the
service has no way to distinguish "genuinely stuck" from "still
legitimately running" without a staleness/timeout policy this file doesn't
have. No existing test in `tests/test_service.py` or a dedicated
`test_sqlite_backend.py` pins either behavior as intended — this is
genuinely undecided, not documented-and-deliberate the way `order_guard.py`'s
fail-open checks are. Consistent with `research-discussion-v2`'s posture on
findings that are real but require a policy decision, not a code fix (its
#2, #4, #10, #18, #19) — flagging for the user rather than unilaterally
picking a dedup policy for a service outside the live-trading path. If the
user wants (a), the fix is straightforward: broaden the `get_by_hash` check
to `status IN (PENDING, RUNNING, DONE)`, or better, make `insert_request`
itself an atomic `INSERT ... SELECT ... WHERE NOT EXISTS (...)` so the
check-and-insert can't race even under true concurrency (the same
architectural fix as situation 1's `daily_limits.py`).

Confirms `vinu-tools` (400+ alpha-factor files plus this service/storage/
worker layer) was untouched by both prior audits (`situation-test`'s own
1-35 and `research-discussion-v2`) — not named in either audit's scope at
all.
