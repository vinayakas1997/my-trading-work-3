# Testing Status — Convention

Identical convention to `e2e-test-0731/testing-status/README.md`. Each
item under [../scope-responsibilities/](../scope-responsibilities/) has a
folder here with the same name, containing one running file:
**`test-log.md`**.

## `test-log.md` structure

1. **What will be tested / Expected output** — written up front, before
   any implementation happens (already filled in per item, copied from
   the corresponding `scope-responsibilities/` file's "Expected output /
   how to verify" section).
2. **Bug / Fix Log** — starts empty (`_Nothing logged yet_`). As work
   actually happens, numbered entries get appended in the order found,
   same format as `e2e-test-0731`:

```markdown
## Bug / Fix Log

### Bug-1 — <one-line summary>
- **Found during:** <what step surfaced this>
- **Date:** <YYYY-MM-DD>
- **Symptom:** <what was observed>
- **Reproduction:** <exact command/request>
- **Severity:** blocker / major / minor

### Fixed-1
- **Root cause:** <confirmed, not guessed>
- **Fix applied:** <files changed, what changed>
- **Verification:** <how it was confirmed fixed>
- **Status:** fixed / wontfix (why) / deferred (why, to when)
```

- Numbers are per item, not global.
- A finding that turns out not to need a fix (expected behavior, already
  resolved, or a documentation error rather than a code bug — see how
  the two false "Stage 2 blockers" were handled in
  `e2e-test-0731/scope-responsibilities/`) still gets logged, not
  silently dropped.

## Current state

**As of 2026-08-02, nothing in this plan has been implemented yet.** This
folder exists so the "what will be tested" definition is locked before
work starts, same discipline as Stage 1.
