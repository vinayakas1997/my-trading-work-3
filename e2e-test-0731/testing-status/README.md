# Testing Status — Convention

Each component under `vinu-components/` has a folder here (same 10 names
as [../scope-responsibilities/](../scope-responsibilities/)), containing
one running file: **`test-log.md`**.

## `test-log.md` structure

Every component's file has the same two sections, in order:

1. **What will be tested / Expected output** — written up front, before
   any testing happens, so there's a concrete definition of "pass" to
   check real results against instead of judging after the fact.
2. **Bug / Fix Log** — starts empty (`_Nothing logged yet_`). As testing
   actually runs, numbered entries get appended here in the order found:

```markdown
## Bug / Fix Log

### Bug-1 — <one-line summary>
- **Found during:** <what test/step surfaced this>
- **Date:** <YYYY-MM-DD>
- **Symptom:** <what was observed — error, wrong output, crash>
- **Reproduction:** <exact command/request that triggers it>
- **Severity:** blocker / major / minor

### Fixed-1
- **Root cause:** <confirmed, not guessed>
- **Fix applied:** <files changed, what changed>
- **Verification:** <how it was confirmed fixed>
- **Status:** fixed / wontfix (why) / deferred (why, to when)

### Bug-2 — <...>
...
```

- Numbers are per component, not global.
- `Fixed-N` always follows the matching `Bug-N` in the same file, so the
  full story for one issue reads top-to-bottom in one place.
- A bug that turns out not to need a fix (expected behavior, or resolved
  as a side effect of something else) still gets a `Fixed-N` entry
  explaining that, not silence.
- Cross-component bugs (e.g. a bad response from `vinu-stock-price`
  breaking `vinu-tools`) get logged in the component that owns the root
  cause, with a one-line cross-reference added to the affected
  component's file.

## Current state

Every component's "What will be tested / Expected output" section is
filled in based on [../full-plan.md](../full-plan.md) and
[../scope-responsibilities/](../scope-responsibilities/).

**As of 2026-07-31, the Docker Compose stack is up and all 10 services
report healthy** (`docker compose ps`). Getting there surfaced 8 real
Bug-1/Fixed-1 pairs (logged in each affected component's file) — bad
`.env` data paths, host-directory permissions, and a missing
`vinu-agent` data-root default. See [../AGENTS.md](../AGENTS.md)'s
"Known environment facts" for the full list and the exact fix commands,
so nobody re-discovers the same three failure classes from scratch.

No actual component-level testing (hitting real endpoints against real
market data) has started yet — the stack being healthy just means every
service starts cleanly, not that its behavior has been verified. That's
the next step, per each component's "What will be tested" checklist.
`vinu-live` and `vinu-agent`'s broker layer remain out-of-scope for
Stage 1 and stay untouched until Stage 2.
