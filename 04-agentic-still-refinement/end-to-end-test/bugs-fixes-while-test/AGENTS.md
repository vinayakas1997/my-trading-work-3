---
name: e2e-bugs-fixes-while-test
status: reference
purpose: index of every bug/inconsistency found while reviewing, preparing, and actually running end-to-end-test/, one file per issue, named after the issue itself.
---

# Bugs & Fixes Found While Preparing and Running the End-to-End Test

Each file here is one issue: what was wrong, why it mattered, exactly what
was changed to fix it, and what that fix actually achieves. Filenames name
the bug, not the fix — consistent with how `implementation-plan-from-04`
logs bugs found while building (see its `status.md` files' "Bugs / Fix Log"
sections), just pulled out into their own files since this folder is
specifically about the testing/verification pass, not the implementation
pass.

## Index

### Found before starting Docker (doc-only, found by cross-reading files)

1. [`research-run-missing-approve-step.md`](research-run-missing-approve-step.md) —
   the one that would have actually broken a real run: `03`'s checklist
   never called `POST /research/runs/{run_id}/approve`, and described
   `POST /research/run` as auto-promoting, which the real code
   (`vinu_research/service.py`) does not do.
2. [`stale-test-counts-in-e2e-agents.md`](stale-test-counts-in-e2e-agents.md) —
   `end-to-end-test/AGENTS.md` cited test counts (266/489) that predated the
   final `implementation-plan-from-04` build (280/500).
3. [`bug-count-mismatch-in-implementation-agents.md`](bug-count-mismatch-in-implementation-agents.md) —
   `implementation-plan-from-04/AGENTS.md`'s summary table said "+3" bugs
   fixed in `vinu-agent`; the detailed log in that component's own
   `status.md` only documents and numbers 2.
4. [`stale-freshness-job-status-initial-analysis.md`](stale-freshness-job-status-initial-analysis.md) —
   `vinu-initial-analysis/status.md` said the freshness recompute job was
   "not started," directly contradicting its own sibling `plan.md` (and
   `vinu-research/status.md`), which both confirm it shipped, hosted
   elsewhere.

### Found while actually bringing the Docker stack up (real infra bugs)

5. [`entrypoint-sh-crlf-line-endings.md`](entrypoint-sh-crlf-line-endings.md) —
   all 7 `entrypoint.sh` files had CRLF line endings on this Windows
   checkout (`core.autocrlf=true`, no `.gitattributes`), corrupting their
   `#!/bin/bash` shebang and crash-looping every container that uses one.
6. [`data-root-docker-path-mismatch.md`](data-root-docker-path-mismatch.md) —
   the shared `.env`/`.env-example` template's per-service data-root
   variables were relative, host-mode paths (`../data/<service>/...`),
   which override each Dockerfile's correct absolute `/data` default and
   land on the container's read-only root filesystem instead of the
   mounted volume — blocked 6 of the 10 services.

### Found while actually running Step 02 (data backfill)

7. [`shared-watchlist-path-not-set.md`](shared-watchlist-path-not-set.md) —
   `VINU_SHARED_WATCHLIST_PATH` was blank, so `vinu-news`/`vinu-stock-price`
   never learned the watchlist; the bulk backfill trigger silently
   processed zero tickers and reported `done`.
8. [`finbert-scoring-not-automatic.md`](finbert-scoring-not-automatic.md) —
   FinBERT sentiment scoring (a `significance_score` input) is a separate,
   manual-only route nothing in the runbook ever calls; run manually this
   pass, not yet added to `02`'s checklist.
9. [`news-price-causality-quadratic-blowup.md`](news-price-causality-quadratic-blowup.md) —
   the big one: `news_price_causality` rebuilt/re-sorted its full
   candle/market-benchmark index on every article instead of once per
   symbol, an O(articles × total_bars) blowup that never finished for
   AAPL/TSLA's real article volume. Fixed and benchmarked at a **304.8x**
   speedup on real production data.

### Found while actually running Step 03 (research generation)

10. [`research-run-null-user-idea-crash.md`](research-run-null-user-idea-crash.md) —
    `POST /research/run` crashed on `"user_idea": null`, the exact payload
    `03`'s own checklist documents, because the auto-propose fallback its
    own request model promised was only implemented on the sibling
    `/research/ensure` route.
11. [`hypothesis-registry-home-dir-crash.md`](hypothesis-registry-home-dir-crash.md) —
    every real (non-`dry_run`) research call crashed constructing
    `HypothesisRegistry()`, whose default path used `Path.home()` —
    non-writable (and nonexistent) in `research-api`'s read-only
    container — across all 11 call sites that rely on that same default.
12. [`simulator-wrong-route-for-research-strategies.md`](simulator-wrong-route-for-research-strategies.md) —
    `03`'s documented `/simulator/simulate` (by `strategy_name`) can never
    work for a research-promoted strategy — it fetches weights from
    `vinu-strategy`, which has zero awareness of research artifacts, a
    structural gap `understanding-project` already named. Fixed in `03`
    itself: use `/simulator/simulate/custom` with the approved run's own
    `strategy_code`.

### Found while actually running Step 05 (one-month agent replay)

13. [`replay-harness-poll-timeout-crash.md`](replay-harness-poll-timeout-crash.md) —
    `run_month_replay.py` crashed after only 4 of 22 days: its status-poll
    request had its own unrelated 30s timeout with no retry, so a poll
    hiccup (while `agent-api` was busy on the actual LLM call) killed the
    whole run well before the real 30-min per-day deadline. Made worse by
    the crash being reported as a clean `exit code 0` by the task runner,
    because the script's output was piped through `tail`.
14. [`agent-api-container-restart-mid-attempt.md`](agent-api-container-restart-mid-attempt.md) —
    after the #13 fix, the replay still failed once more: `agent-api`
    itself cleanly restarted (`ExitCode=0`, not OOM, `docker stats`
    confirmed trivial memory use) mid-attempt on day 2026-06-16, losing
    the in-flight LLM call and dooming the poll to the full 30-min
    timeout. Root cause of the restart trigger itself wasn't pinned down;
    mitigated for free by the harness's existing resume-by-skip design
    rather than new code.

## What these fourteen have in common

#1–4 are documentation-only, found by cross-reading planning files against
each other (and, for #1, against the real `vinu-research` source) before
any container was started. #5–13 are real code/infrastructure bugs (or, for
#12, a real structural gap), only surfaced by actually running the stack
and the checklist end to end — no amount of reading the docs would have
caught them. #13 is also a reminder that a task runner's reported exit
code is only as honest as the command it wraps — piping through `tail`
silently swallowed a real crash. Notably, #7, #10, #11, and #12 all share the same shape: a real feature or fallback (watchlist sync,
auto-proposed ideas, a documented data-root pattern) already existed
*somewhere* in the codebase, just not wired into the exact path this
checklist's first real attempt actually exercised — confirming this
project's own repeated finding (`04-vinu-components-integration-plan.md`'s
"check harder for an existing near-miss before assuming greenfield")
applies just as much to bugs as it does to planning.
