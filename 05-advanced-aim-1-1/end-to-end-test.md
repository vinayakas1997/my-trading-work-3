---
name: e2e-telemetry-verification
status: definition-phase
purpose: the runbook for verifying steps 1-5 in AGENTS.md/status.md against the real Docker stack — not a new pipeline test, an overlay on 04-advanced-aim-1/end-to-end-test's existing runbook, checking that telemetry records land with real numbers at each step that already exists there. Nothing here has been run yet.
---

# End-to-End Verification — the Telemetry Layer, Against the Real Stack

## Why this file is thin

`05-advanced-aim-1-1` didn't build a new pipeline — it instrumented the
one `04-advanced-aim-1/end-to-end-test/01-05` already exercises. Re-running
that whole runbook from scratch here would duplicate it for no reason. This
file is the **overlay**: run `04`'s runbook exactly as written, and at each
step below, also run the telemetry check next to it. If a `04` step's own
verification fails, stop there and fix it per `04`'s own files — this file
assumes `04`'s runbook already passes and is only checking the new layer
on top.

**Prerequisite**: rebuild the stack first (`docker compose up --build -d`
from `vinu-components/`) so the `vinu-agent`/`vinu-research` containers
actually run this session's code, not a stale image. If this is a fresh
rebuild, also do `04-advanced-aim-1/end-to-end-test/01-setup-and-rebuild.md`
in full first — its `[schedule-decay]`/`[schedule-freshness]` log check is
a separate, already-landed fix from the previous session, not part of this
one, but still worth confirming while the stack is freshly up.

## How to read the telemetry tables directly

Every check below reads from `{data_root}/telemetry.db` for whichever
service just ran. Inside the containers this is
`/data/telemetry.db` (bind-mounted from `./data/<service>/` on the host,
same as every other per-service SQLite store in this stack). From the host:

```bash
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT ts, model, prompt_tokens, completion_tokens, token_count_source, retry_count, latency_sec, outcome FROM llm_calls ORDER BY id DESC LIMIT 10;"
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT ts, step_name, outcome, duration_sec FROM steps ORDER BY id DESC LIMIT 20;"
```

Swap `data/agent/` for `data/research/` to check `vinu-research`'s calls
(wired via `vinu-infra/llm/client.py`/`client_async.py`, not `vinu-agent`'s
own client — see `status.md` §2).

## 1. During `04`'s step 3 (`vinu-research` strategy generation)

`03-strategy-research-and-simulation.md` triggers real LLM calls
(`POST /research/run`, real `generate → backtest → validate`, not
`dry_run`). Right after triggering it for at least one symbol:

```bash
sqlite3 vinu-components/data/research/telemetry.db \
  "SELECT COUNT(*), SUM(success), AVG(retry_count) FROM llm_calls;"
```

- [ ] At least one row exists — if zero, the telemetry wiring in
      `vinu-infra/llm/client.py` isn't actually being hit; check
      `vinu-research` is calling `LlmClient`/`AsyncLlmClient`, not some
      other path.
- [ ] `token_count_source` is present and non-null on every row (it's
      always `"provider"` for this client — `vinu-infra`'s client only ever
      reports real API-returned usage, never falls back to an estimate;
      if this assumption turns out wrong for some response shape, that's
      a real finding, write it up).
- [ ] `retry_count` is `0` for a healthy run against a reachable LLM
      endpoint — a consistently nonzero average here, with the LLM server
      confirmed up, would itself be worth investigating (not necessarily a
      bug in this layer, but real information the old JSONL-only log
      never surfaced this easily).

## 2. During `04`'s step 5 (one-month `vinu-agent` replay)

This is the step the whole investigation in `04-advanced-aim-1/
end-to-end-complete-status.md` centers on — the real test of whether this
layer actually explains what happens during a multi-day replay, not just
whether it compiles. Run `05-one-month-agent-verification.md`'s replay
(`run_month_replay.py`) as documented there. **Do not wait for all 22 days
to check this** — query after the first few days complete, so a broken
telemetry path is caught early, not after a multi-hour run:

```bash
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT model, token_count_source, COUNT(*) FROM llm_calls GROUP BY model, token_count_source;"
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT outcome, COUNT(*) FROM steps WHERE step_name='agent_loop_run' GROUP BY outcome;"
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT step_name, outcome, COUNT(*) FROM steps WHERE step_name LIKE 'tool:%' GROUP BY step_name, outcome ORDER BY 3 DESC LIMIT 15;"
```

- [ ] `token_count_source = 'provider'` for the real `qwen36-35B` calls —
      **if every row instead says `'estimated'`**, the backing llama.cpp
      server isn't returning a `usage` object on its
      `/chat/completions` responses, and `agent/llm.py`'s real-usage path
      is silently falling back to the same char/4 heuristic this whole
      layer exists to replace. Confirm directly:
      `curl -s http://host.docker.internal:8009/v1/chat/completions -d '...'`
      and check the response body for a top-level `"usage"` key before
      concluding this is a code bug versus a server-capability gap.
- [ ] `agent_loop_run` outcomes are visible and varied — expect to see
      `completed`, and, per `04`'s prior findings, likely also
      `max_iterations` and possibly `error`. **If every row says
      `completed`**, that contradicts `04`'s finding that 13/22 days ended
      without a real decision — worth specifically re-checking against a
      raw trace for one of those days before trusting the aggregate,
      exactly the kind of "looks done, isn't" gap this whole project keeps
      finding.
- [ ] At least one `tool:get_stock_price`/`tool:get_fundamentals`/etc. row
      exists with `outcome != 'completed'` if `04`'s §2.3 finding
      (9/22 days had real tool-call flakiness) still reproduces — if the
      backend APIs are healthy this time and nothing fails, that's a
      legitimate, different outcome from last time; document which one
      actually happened, don't assume.
- [ ] Whatever the loop's real terminal status turns out to be for a given
      day, cross-check it against that day's own `thinking.json` trace
      (same file `04`'s investigation used) for at least one day — this is
      the actual acceptance test for step 5 in `AGENTS.md`'s design: does
      the telemetry table's `outcome` column match what the raw trace
      shows really happened, without needing to read the raw trace to find
      out.

## 3. Retry-count sanity check — the specific gap this session's `llm.py`
   rewrite targeted

`04`'s replay hit a real `LLM call failed at iteration N: ... Request
timed out` on 2026-06-18 and a hard `Context size has been exceeded` on
2026-06-29. If the replay reproduces either during this run:

```bash
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT ts, retry_count, outcome, error FROM llm_calls WHERE success=0 ORDER BY id DESC LIMIT 10;"
```

- [ ] `retry_count` is a real, nonzero number on a call that failed after
      retries were exhausted — before this session's fix, this number was
      unobservable for `OpenAIChatLLM` (the provider path this project's
      config actually uses against the local llama.cpp server). If it's
      still always `0` on a known-retried failure, the explicit retry loop
      in `agent/llm.py` isn't actually being exercised — check
      `_is_transient_openai_error` is correctly classifying the real error
      type raised in this environment.

## What "done" looks like

Every checkbox above checked, for at least one real (not dry-run) pass
through `04`'s steps 3 and 5. If any checkbox reveals telemetry isn't
capturing something it should (wrong outcome, missing rows, `estimated`
where `provider` was expected), that's a real bug — write it up in
[`bugs-fixes-while-test/`](bugs-fixes-while-test/AGENTS.md), one file per
issue, same pattern `04` used, then fix it and re-check before moving on.

## What this file does not cover

- Re-verifying anything `04-advanced-aim-1/end-to-end-test` already checks
  on its own (data backfill correctness, strategy promotion, portfolio
  sync, etc.) — this file only adds the telemetry overlay on top of an
  already-passing `04` run.
- `vinu-research`/`vinu-initial-analysis` tool-call-level telemetry — per
  `status.md`'s "what was deliberately not done," only `vinu-agent`'s own
  tool calls are instrumented this pass. Not checked here because it
  doesn't exist yet.
- A dashboard — the `sqlite3` queries above are the only interface this
  layer has right now, by design (see `AGENTS.md`).
