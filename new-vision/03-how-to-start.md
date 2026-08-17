---
name: how-to-start
status: operational guide, matches the actual code/scripts as of 2026-08-17
purpose: step-by-step to bring the vinu-components stack up from a clean machine, plus what to check once it's running.
---

# How to start the system

Everything below refers to the real repo at
`/home/somic_cps/Vina/my-trading-work-3/vinu-components`. All commands assume you're
in that directory unless stated otherwise.

## Prerequisites

- Docker + Docker Compose installed.
- Rotated Alpaca API key/secret (**not** the old leaked pair from `alpaca-details/details.md`
  — rotate those at Alpaca first if you haven't yet).
- An LLM provider API key (whichever provider this project's `vinu-infra/llm` config uses).
- Optional: Telegram bot token and/or Discord bot token, only if you want Significance
  Triage to actually deliver alerts (task 03 — code is ready, just needs real credentials).

## Step 1 — copy the env template

```bash
cd vinu-components
cp .env-example .env
```

## Step 2 — set every `VINU_*_DATA_ROOT`

Open `.env` and set a real path for each service's data root
(`VINU_AGENT_DATA_ROOT`, `VINU_INITIAL_ANALYSIS_DATA_ROOT`, and one per other
`vinu-*` package). These have **no default** — `require_data_root()` in
`vinu-infra/config.py` deliberately fails fast if any is missing, so don't skip
this even for a local test run.

## Step 3 — fill in credentials in `.env`

At minimum:
- `ALPACA_API_KEY`, `ALPACA_API_SECRET` — the rotated pair.
- `VINU_LLM_API_KEY` — your LLM provider key.
- `VINU_API_KEY` — pick any strong random string yourself; this is the internal
  service-to-service auth key, not something a provider gives you.

Optional (leave blank if not using yet):
- `TELEGRAM_TOKEN`, `DISCORD_TOKEN`
- `POLYGON_API_KEY`, `FMP_API_KEY`, `TUSHARE_TOKEN`

## Step 4 — bootstrap the secret files

```bash
scripts/setup-secrets.sh --check    # validates only, writes nothing
```

Fix anything it reports as `MISSING ... (required)` by filling it into `.env`,
then actually populate the files:

```bash
scripts/setup-secrets.sh
```

This writes one file per credential under `./secrets/` (mode `600`, gitignored),
which is what Docker Compose actually mounts into each container — `.env`
alone isn't enough. It now exits non-zero if a **required** secret
(`vinu_api_key`, `alpaca_api_key`, `alpaca_api_secret`, `vinu_llm_api_key`) is
still empty after checking `.env` and your shell env — don't proceed to the
next step until it prints `secret files ready`, not a `FAILED` line.

## Step 5 — start the stack

```bash
docker compose up -d
```

## Step 6 — verify it's actually running, not just started

```bash
docker compose ps                        # every service should show "healthy" or "running"
docker compose logs -f vinu-agent         # watch for worker start lines
```

In the `vinu-agent` logs you should see each background worker start:
`skill-audit-worker`, `planner-worker`, `significance-worker`,
`capital-allocator-worker`. In `vinu-live` logs: `trade-plan-worker`,
`feedback-worker`, `shadow-worker`.

Confirm auth is actually enforced, not silently open:

```bash
curl -i http://localhost:<agent-port>/broker/performance/test    # expect 401/403
curl -i -H "X-Internal-Api-Key: <your VINU_API_KEY>" http://localhost:<agent-port>/broker/performance/test   # expect a real response, not 401
```

If the unauthenticated call succeeds, `VINU_API_KEY` didn't make it into
`./secrets/vinu_api_key` — go back to step 4.

## After it's running — what to actually do

1. **Seed a watchlist.** Nothing proposes candidates until the Planner has
   tickers to look at — check whichever config/table the watchlist lives in
   (per the design doc, this is the entry point the change-gate reads from).
2. **Confirm the Kill Switch state is what you expect.** It's meant to be a
   deliberate, explicit gate — check `broker/kill_switch.py`'s current state
   before assuming trades will actually execute or that a halt is active
   when you think it is.
3. **Watch the first full cycle end to end** in the logs: Summary Agent →
   Planner triage → Researcher/Executor sweep → risk_gatekeeper verdict →
   PEND → capital_allocator (now scheduled, runs on its own interval) →
   funded or held. This is the single best way to confirm the pipeline is
   actually doing what the design doc says, not just that processes started.
4. **Check Significance Triage delivery**, if you set Telegram/Discord
   credentials — trigger something notable (or wait for a real one) and
   confirm a message actually arrives, not just that the code path ran.
5. **Sanity-check the TickerLedger** is accumulating real events for tickers
   you're watching — this is the ticker-keyed audit trail everything else in
   the design writes to.

## Ongoing operational checklist

- **Secrets rotation**: follow `docs/secrets-rotation.md` — edit the file
  under `./secrets/<name>`, then `docker compose up -d --force-recreate` for
  the affected service (keys are read once at process start, no live-reload).
- **Structured logs**: worker exceptions are now logged with context (which
  ticker/artifact was being processed) — this is your first place to look if
  something silently stopped producing new candidates or funding decisions.
- **Re-run `scripts/setup-secrets.sh --check`** any time before a redeploy,
  especially after rotating a credential, to confirm nothing required is
  blank.
- **Known follow-up, not urgent**: task 01's capital-allocator-worker test
  doesn't yet exercise the actual scheduling loop (only the cycle function it
  calls) — the worker itself is confirmed working in practice, this is just a
  test-coverage gap to close eventually.
- **If you ever add a new committed file with real credentials in it by
  mistake**, follow the leaked-credential playbook in
  `docs/secrets-rotation.md` immediately — rotate at the provider first,
  don't just delete the file.
