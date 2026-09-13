# situation-test

Acting as an auditor walking the live pipelines end to end: whenever a real
"what actually happens if..." question comes up, don't just reason about it
from reading the code -- actually exercise the real modules (a small script
against the repo's own classes/functions, or the real test suite) and record
the observed behavior. Each file here is one situation.

## Format

Each `NN-short-name.md` file has:
- **Question** -- the concrete "what if" scenario.
- **Where** -- the file/function this concerns.
- **How tested** -- the actual script/command run against the real code
  (not a mock of the thing being tested, unless the mock is external to the
  system under test -- e.g. mocking a broker HTTP call is fine, mocking the
  concurrency primitive being tested is not).
- **Observed** -- what actually happened, verbatim where useful.
- **Verdict** -- matches the intended design / surprising / a real bug found.

## Summary

36 situations recorded. 14 real bugs found and fixed (1, 15, 17, 18, 19,
22, 24, 28, 29, 31, 32, 33, 34, 35); one real gap flagged but deliberately
not fixed pending a policy decision (36); the rest confirm the code
matches its own documented design, several with a precise number attached
where the design was only previously an argument (3, 6, 23, 25). Four of
the fixes (15, 22, 29, 32) turned out to be the same underlying pattern --
one specific call site skipping a protection every sibling call site in
the same file already applies (a `reduce_only` exemption in three
different `OrderGuard` checks; a `book_lock()` in one of nine
book-mutating calls in `orchestrator.py`) -- situation 30 confirms the
pattern doesn't apply everywhere (a market-closed check correctly blocks
both directions). Situations 28 and 31 are the two most severe: 28 is a
real, unmocked limit order silently failing at the final pre-submission
step, invisible to the entire test suite because every test of a
successful submission mocked that exact step directly; 31 is a
risk-budget safety gate (`OrderGuard`'s `RISK_BUDGET_HALT`) that could
spuriously halt a perfectly healthy, unchanged position purely from being
checked often enough -- and had an existing test explicitly asserting the
broken behavior as intended, from an earlier fix that moved in the wrong
direction. Situation 32 is a real, reproducible lost-update race
(confirmed 5/5 runs) in `vinu-live`'s trade-plan book, of the exact same
shape `book_lock()` was built to prevent elsewhere in the same file.

Situations 33-36 move into `vinu-strategy` and `vinu-tools` -- confirmed,
by reading a separate, larger prior audit (`../research-discussion-v2/`,
findings #1-#39 across every other `vinu-*` package), to be the only real
gaps in coverage: `vinu-strategy` was named in that audit's scope but every
actual finding landed in `vinu-simulator`/`vinu-research` instead, and
`vinu-tools`/`vinu-quant-core` were never named at all. 33 is a real,
reproducible `TypeError` crash in `WeightPipeline.run()`'s risk-params
merge (currently unreachable via the one production caller, but a genuine
landmine for a second one). 34 is the same "missing data silently stands in
for a real value" root cause as situation 31, this time letting a symbol
with zero computed feature data pass a threshold selection and receive
real capital via equal-weight allocation. 35 is an observability severity
bug: a total expression-config typo degrades an entire strategy to
equal-weight allocation with only WARNING-level logging, indistinguishable
from a legitimate flat-signal day. 36 is a real dedup gap in
`vinu-tools`'s feature-request queue (confirmed 10/10 duplicate inserts
under real concurrent submission) flagged rather than fixed, since it's a
genuine policy ambiguity (force-resubmit vs. bug) rather than an
unambiguous defect, in a service outside the live-trading path.

## Index

1. [Daily order-limit race](01-daily-order-limit-race.md) — 30 concurrent
   orders for one symbol against `max_daily_orders=5`: **bug found**. Not the
   documented "occasionally too-permissive cap" — real
   `sqlite3.OperationalError`/`IntegrityError` crashes on most legitimate
   orders, unhandled all the way up to the LLM as a spurious `"status":
   "error"`.
2. [Ingest loop survives a real crash](02-ingest-loop-survives-a-real-crash.md)
   — drove the real `ingest_main()` through an induced `KeyError` mid-cycle:
   confirmed the earlier fix works, not just its own unit tests.
3. [Portfolio correlation cache staleness, quantified](03-portfolio-correlation-cache-staleness-quantified.md)
   — forced a real +0.995 → -0.994 correlation flip between two calls inside
   the 60s TTL: confirmed the cache serves the stale value, exactly as
   designed; now a measured number instead of an argument.
4. [Symbol grounding end-to-end](04-symbol-grounding-end-to-end.md) — drove
   the real `AgentLoop` → `ToolRegistry` → `TradeTool` pipeline with a
   scripted mismatched-symbol conversation: confirmed my own #6 fix holds
   for confirmation exactly as intended, and doesn't add friction to a
   correctly-grounded order.
5. [Risk-budget fetch memoized per instance](05-risk-budget-fetch-memoized-per-instance.md)
   — matches design: one real network call serves both
   `position_size_multiplier()` and `check()` on the same `OrderGuard`.
6. [Reauth-band env var is boot-time only](06-reauth-band-env-var-is-boot-time-only.md)
   — matches design, but a real operational trap: editing the env var on a
   running process silently does nothing until restart.
7. [Portfolio-wide daily cap exempts reduce_only](07-portfolio-wide-daily-cap-exempts-reduce-only.md)
   — matches design, confirmed against a real exhausted cap.
8. [Kill switch reduce_only exemption end-to-end](08-kill-switch-reduce-only-exemption-end-to-end.md)
   — matches design, driven through the real filesystem-based kill switch,
   not a mocked halt check.
9. [Risk-budget "no equity" fails closed](09-risk-budget-no-equity-fails-closed.md)
   — matches design: the one deliberate fail-closed branch in an otherwise
   fail-open file really does take the opposite path.
10. [Unpriceable order value check](10-unpriceable-order-value-check.md) —
    matches design: rejected outright for a normal order, allowed for
    reduce_only.
11. [Symbol-override IGNORED vs REDUCE_ONLY precedence](11-symbol-override-ignored-vs-reduce-only-precedence.md)
    — matches design (and is the *right* design, unlike situation 15's bug):
    `IGNORED` blocks even reduce_only orders on purpose.
12. [Order-throttle sliding window, real time](12-order-throttle-sliding-window-real-time.md)
    — matches design, using a real clock; also documents a test-methodology
    trap (unmocked network latency silently defeated the first attempt).
13. [Concentration check is buy-only](13-concentration-check-buy-only.md) —
    matches design: a sell for an over-concentrated symbol skips the check
    entirely, zero network calls.
14. [Symbol-limit override replaces the global default](14-symbol-limit-override-replaces-global-default.md)
    — matches design: a per-symbol override changes behavior for that
    symbol only.
15. [Reduce-only sell blocked by the short-selling check](15-reduce-only-sell-blocked-by-short-check.md)
    — **bug found and fixed**: under the mandate's own default
    (`allow_short=False`), a `reduce_only` sell (the normal way to close a
    long) was rejected as short-selling, with no exemption at all — unlike
    every other check in `OrderGuard`. A position opened via a normal buy
    could never be exited through `submit_order`'s reduce_only path.
16. [Kill switch global vs per-symbol precedence](16-kill-switch-global-vs-per-symbol-precedence.md)
    — matches design, on the real filesystem: a global halt beats a scoped
    resume, and a global resume doesn't clear an unrelated symbol's own
    separate halt.
17. [Symbol-grounding substring false negative](17-symbol-grounding-substring-false-negative.md)
    — **bug found and fixed** (in my own earlier #6 fix): a plain substring
    match treated ticker `CAT` as grounded whenever the turn merely
    mentioned "Caterpillar" — the ticker itself was never said. Fixed with
    word-boundary matching.
18. [AuditLogger unwritable path crashes the order pipeline](18-audit-logger-unwritable-path-crashes-order-pipeline.md)
    — **bug found and fixed**: a filesystem hiccup writing the audit log
    (a purely observability side effect) raised straight out of
    `TradeTool.execute()`, crashing order rejection/pause responses that
    never even reached the guard or broker.
19. [Corrupted mandate loosens the ticker allowlist](19-corrupted-mandate-loosens-ticker-allowlist.md)
    — **bug found and fixed**: an unparseable (but present) mandate.yaml
    fell back to `allowed_tickers: {"*"}` — every ticker allowed — silently
    discarding a real operator restriction. Now fails closed instead.
20. [Consent-expiry exact boundary](20-consent-expiry-exact-boundary.md) —
    matches design: `>=`, so a mandate is treated as expired starting at
    the exact configured instant.
21. [CVaR gate boundary and garbage inputs](21-cvar-gate-boundary-and-garbage-inputs.md)
    — matches design: exclusive threshold, and fails open on `nan`, `inf`,
    and non-numeric garbage alike.
22. [Ticker allowlist blocks reduce-only exits](22-ticker-allowlist-blocks-reduce-only-exits.md)
    — **bug found and fixed** (found while fixing situation 19): a symbol
    falling out of `allowed_tickers` blocked even a `reduce_only` exit.
    `blocked_tickers` was tested too and correctly does *not* get the same
    exemption (same reasoning as `IGNORED` in situation 11).
23. [Notification dedup is permissive by default](23-notification-dedup-permissive-by-default.md)
    — matches design, quantified: my own #8 reconciliation-drift alert
    would re-page every channel every 300s (the default cycle interval)
    indefinitely on a default deployment, same as every sibling notify
    route — an operator should configure `VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC`.
24. [Reconciliation-drift comment promised dedup that didn't exist](24-reconciliation-drift-comment-promised-dedup-that-didnt-exist.md)
    — **bug found and fixed** (found by testing my own earlier comment
    against situation 23): I had written "deduped... doesn't re-notify
    every cycle" for my #8 fix, but no such dedup existed anywhere in that
    path. Added real edge-triggered per-instance dedup to make the claim
    true.
25. [require_confirmation defaults to holding every order](25-require-confirmation-defaults-to-holding-every-order.md)
    — matches design, precisely quantified: a real, guard-approved, trivial
    $1 order is still held for human confirmation on a totally default
    deployment. Not a bug — the human-in-the-loop-by-default posture is
    deliberate — but easy to miss given how many of this audit's own test
    scripts set `require_confirmation=False` to get past it.
26. [Symbol-limit history dedupes no-op resets](26-symbol-limit-history-dedupes-no-op-resets.md)
    — matches design: re-setting a limit override to its current value
    produces zero spurious audit-history rows.
27. [Breaker halt engagement is edge-triggered and fails open](27-breaker-halt-engagement-edge-triggered-and-fails-open.md)
    — matches design, confirmed still holding after this session's other
    edits to the same file: a fresh breach engages the real kill switch
    once, an already-halted state makes no further calls, and a failed
    kill-switch call still leaves the local breaker halted.
28. [pre_approve drops price, re-checks with zero value](28-pre-approve-drops-price-rechecks-with-zero-value.md)
    — **the most severe bug found in this audit, fixed**: the real,
    unmocked `TradeTool.execute()` → `OrderGuard.pre_approve()` path
    silently re-rejected any correctly-priced limit order or already-held-
    symbol market order right before submission, because `price`/
    `estimated_value` were never forwarded to the pre-submission re-check.
    Uncaught by the entire existing suite because every test of a
    successful submission mocks `pre_approve` directly.
29. [Active-artifact check blocks reduce-only exits](29-active-artifact-check-blocks-reduce-only-exits.md)
    — **bug found and fixed**: the third occurrence of the same
    missing-`reduce_only`-exemption pattern as situations 15 and 22, this
    time in `require_active_artifact` — a retired/archived strategy
    trapped any position it had opened.
30. [Market-closed check correctly blocks reduce-only too](30-market-closed-check-correctly-blocks-reduce-only-too.md)
    — matches design, and closes the loop: unlike the three policy-type
    checks above, `require_market_open` is a hard trading-mechanics fact,
    not a sanctioning decision, so both directions are correctly blocked
    alike.
31. [Risk budget accumulates repeated unrealized-P&L snapshots](31-risk-budget-accumulates-repeated-unrealized-pnl-snapshots.md)
    — **bug found and fixed, arguably the most severe in this audit**: a
    perfectly healthy, unchanged position would drift into `TIER_HALT`
    purely from being risk-checked often enough (every order, every
    dashboard refresh) — an existing test explicitly asserted this
    accumulation as the intended design, from an earlier fix that moved in
    the wrong direction. Replaced with sticky worst-case tracking (a real
    breach latches through a recovery; an unchanged reading no longer
    inflates).
32. [Rebalance-honor reduce_position missing book_lock](32-rebalance-honor-reduce-position-missing-book-lock.md)
    — **bug found and fixed**: the one book-mutating call site (of nine)
    in `orchestrator.py` not wrapped in `book_lock()` — confirmed as a
    real, reproducible lost-update race (5/5 runs) via a direct
    concurrency test, the exact bug shape `book_lock()`'s own docstring
    says it exists to prevent (and cites a real prior live incident of).
33. [Risk params None crashes weight pipeline](33-risk-params-none-crashes-weight-pipeline.md)
    — **bug found and fixed**: `WeightPipeline.run()`'s risk-params merge
    inserted an explicit `None` via `setdefault` whenever a caller's params
    dict omitted `max_weight`/`cash_floor`, shadowing `risk.py`'s own
    default and crashing with `TypeError` on the very next `min()`/`max()`
    call. Unreachable via the one current caller (always supplies both
    keys) but a real landmine for any second one.
34. [select_threshold missing feature passes as neutral](34-select-threshold-missing-feature-passes-as-neutral.md)
    — **bug found and fixed**: a symbol with *no* computed value at all for
    a threshold-filtered field defaulted to `0.0` and silently passed any
    `min <= 0` threshold, then received full equal-weight capital
    allocation purely from a data gap — the same "missing data stands in
    for a real value" root cause as situation 31.
35. [Expression failure blends into equal-weight silently](35-expression-failure-blends-into-equal-weight-silently.md)
    — **bug found and fixed** (observability/severity, not math): a
    strategy-config typo that breaks an allocation expression for every
    candidate degrades to equal-weight with only WARNING-level logging,
    indistinguishable from a legitimate flat-signal day. Bumped to ERROR;
    left the equal-weight fallback policy itself untouched.
36. [Feature-request dedup only checks DONE status](36-feature-request-dedup-only-checks-done-status.md)
    — **real gap, flagged not fixed**: `vinu-tools`'s feature-request queue
    never dedupes an identical request that's still PENDING/RUNNING —
    confirmed 10/10 duplicate inserts under real concurrent submission via
    `threading.Barrier`. Genuinely ambiguous whether resubmitting a stuck
    request should reuse it or is intentional force-resubmit; no existing
    test pins either as intended, so flagged rather than deciding a policy
    question in a service outside the live-trading path.
