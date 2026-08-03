---
name: replay-harness-poll-timeout-crash
status: fixed
severity: silent-run-failure-reported-as-success
---

# Bug: `run_month_replay.py` crashed after 4 of 22 days, and the background
task runner reported it as a successful exit

## What was wrong

The one-month replay (`vinu-agent/scripts/run_month_replay.py`, step `05`)
was launched piped through `tail -100` to keep the terminal output short.
It died partway through with an uncaught exception:

```
requests.exceptions.ReadTimeout: HTTPConnectionPool(host='localhost', port=8086): Read timed out. (read timeout=30)
```

but the task notification reported `completed (exit code 0)` — because a
shell pipeline's exit code is the exit code of the **last** command in the
pipe (`tail`), not the Python script that actually failed. This made a
crashed run look identical to a clean one unless the actual output was
read.

The real crash site is `ReplayRunner.wait_for_attempt()`
(`run_month_replay.py:160-198`): it polls `GET
/agent/sessions/{id}/messages` every 2 seconds inside an overall 30-minute
per-day deadline (`MAX_WAIT_SEC`), intended as the real timeout safety net
for a slow local-LLM turn. But the poll request itself had a hardcoded
`timeout=30` with no `try/except` around it. When `agent-api` was fully
busy actually running the LLM call (a single worker, blocking on a local
34.7B-parameter model), it was sometimes too slow to service even the
cheap "list messages" status poll within 30 seconds. That poll-level
timeout raised `ReadTimeout`, which propagated straight out of `main()`
and killed the whole 22-day run — after only 4 days — despite the actual
30-minute per-day deadline never being reached.

## Why it mattered

This is not a one-off fluke: any day where the agent is legitimately busy
(more tool calls, slower model response) is exactly the condition that
makes the lightweight poll more likely to time out, so the crash recurs
precisely on the days the harness most needs to keep waiting through. Left
alone, this run would have silently stopped at 4/22 days and been reported
as a clean, complete run by anything relying on the process exit code (as
the task notification did here) — the exact "looks done, isn't" failure
mode this whole testing pass has been hunting for elsewhere in the stack.

## What was fixed

Wrapped the poll request in `wait_for_attempt()` in a
`try/except requests.exceptions.RequestException`: on a transient poll
failure, log a warning and keep polling (respecting the real
`MAX_WAIT_SEC` deadline), instead of letting the exception escape and kill
the process. The actual timeout safety net (30 min/day) is unchanged —
only the previously-fatal, unrelated poll-request timeout is now
survivable.

## What was achieved

Confirmed via the raw script output (not the task-runner's reported exit
code) that the run had actually stopped at day 2026-06-05 of 22, patched
the root cause, and resumed the same run — the harness's existing
resume-by-skip logic (`todo` list built from `response.json` presence)
picks up cleanly from the first incomplete day without redoing 06-01
through 06-04.
