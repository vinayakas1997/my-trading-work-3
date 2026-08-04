---
name: agent-api-container-restart-mid-attempt
status: observed-mitigated-by-resume-design
severity: infra-flake-loses-in-flight-work
---

# Observation: `agent-api` container restarted mid-replay, losing one day's in-flight LLM attempt

## What was wrong

During the resumed one-month replay (`e2e-2026-06`, see
[`replay-harness-poll-timeout-crash.md`](replay-harness-poll-timeout-crash.md)
for the earlier, separate poll-timeout bug), the run got 10 days in
(2026-06-01 through 2026-06-15) then failed again on 2026-06-16:

```
2026-08-04 03:15:54 WARNING poll request failed (ReadTimeout), retrying
2026-08-04 03:15:58 WARNING poll request failed (RemoteDisconnected), retrying
2026-08-04 03:16:02 WARNING poll request failed (RemoteDisconnected), retrying
2026-08-04 03:42:19 ERROR attempt 869e3a70caef not completed within timeout
```

This time the already-applied poll-retry fix worked correctly (it survived
the transient failures and kept polling) — but the underlying attempt
itself never completed within the real 30-minute deadline, so the script
correctly gave up and exited(1).

Checked `docker inspect vinu-components-agent-api-1`: the container's
`StartedAt` (`2026-08-03T18:15:58Z`) lines up exactly with the poll
failures, `RestartCount=2`, `ExitCode=0`, `OOMKilled=false`. Confirmed via
`docker stats` right after that memory usage was trivial (89MiB / 2GiB
limit) — this was **not** a memory-pressure/OOM kill, it was a clean
container restart (`restart: unless-stopped` policy), root cause of the
restart trigger itself not further identified. Whatever caused it, the
in-flight attempt for 2026-06-16 (session state held in the old process)
was lost when the new process came up, so the poll could never find a
matching completed message — the 30-minute wait was doomed from the
moment of restart, not a slow LLM call.

## Why it mattered

Any in-flight day's attempt is not durable across an `agent-api` restart
— there's no checkpoint/resume for a single in-progress attempt, only for
already-completed days (`response.json` written). One restart costs up to
the full `MAX_WAIT_SEC` (30 min) of wasted waiting before the harness
notices and exits.

## What was fixed / what wasn't

Not fixed at the code level — no change made to `run_month_replay.py`
beyond the separate poll-retry fix already documented. The existing
resume-by-skip design already handles this correctly at the
process-invocation level: since 2026-06-16's `response.json` was never
written, simply re-running the same command re-sends that day as a fresh
message (new `attempt_id`) rather than waiting on the dead one — no data
loss, no manual cleanup required, just a wasted 30 minutes on this
occurrence.

A more thorough fix (detect a dead attempt mid-run via an `agent-api`
uptime/session check and re-send immediately rather than waiting the full
30 minutes) was deliberately not built — it's speculative engineering for
a failure mode observed once, and the existing resumable design already
tolerates it correctly at zero cost beyond time. Worth revisiting only if
this recurs frequently.

## What was achieved

Verified this was a genuine infra flake, not a data-loss risk or a
memory leak building up over the run (ruled out via real `docker stats`
numbers, not assumption), and confirmed the harness's own resumability
guarantee holds even across an unplanned dependency-service restart, not
just a script-level crash.
