---
name: how-to-start
status: operational guide, matches the actual code/scripts as of 2026-09-11 (v3 — adds the pretrained-model-download step, verified against the real vinu-infra/models.py + docker-compose.yml mounts)
purpose: step-by-step to bring the vinu-components stack up from a clean machine, plus what to check once it's running.
note: the "After it's running" and "Ongoing operational checklist" sections below are unchanged from v2 (2026-09-07) and reference some older decision/row IDs from that phase of the project that weren't re-verified in this pass -- Steps 1-8 above them (through the model-download and auth-verification steps) ARE freshly re-verified against the current code as of this edit.
---

# How to start the system

Everything below refers to the real repo at
`/home/somic_cps/Vina/my-trading-work-3/vinu-components`. All commands assume you're
in that directory unless stated otherwise.

## What you'll need from the user before starting (ask for these first)

Before touching any file, get these from whoever is standing the system up
— nothing past Step 2 works without them:

1. **Alpaca API key + secret** — must be a freshly rotated pair, never the
   old leaked one in `alpaca-details/details.md`. Paper or live — either
   works, `ALPACA_PAPER=true` (default) picks paper.
2. **An LLM provider API key** — whichever provider `vinu-infra/llm/config.py`
   is pointed at for this deployment.
3. **A `VINU_API_KEY` value** — this one is NOT provided by any external
   service; it's an internal service-to-service auth secret the user (or
   you) invents. Any strong random string works — generate one if they
   don't already have one:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
4. **Optional, only if wanted now**: Telegram bot token
   (`TELEGRAM_TOKEN` + the chat id to deliver to,
   `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID` — the token alone isn't enough)
   and/or Discord bot token (`DISCORD_TOKEN` +
   `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID`), for Significance Triage alerts
   + the `/rank`/`/track` commands. Plus `POLYGON_API_KEY`/`FMP_API_KEY`/
   `TUSHARE_TOKEN` (extra data-provider fallbacks — the stack runs fine on
   Alpaca alone).

Everything else below (data-root paths, ports) has a working default or is
generated, not something to ask the user for.

## Step 1 — copy the env template

```bash
cd vinu-components
cp .env-example .env
```

## Step 2 — put the credentials into `.env`

Open `.env` and fill in what was gathered above:
- `ALPACA_API_KEY`, `ALPACA_API_SECRET`
- `VINU_LLM_API_KEY`
- `VINU_API_KEY`
- `TELEGRAM_TOKEN` + `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`, `DISCORD_TOKEN` +
  `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID`, `POLYGON_API_KEY`, `FMP_API_KEY`,
  `TUSHARE_TOKEN` — only if provided, leave blank/commented otherwise
  (all four channel vars are commented out by default in `.env-example`).

Also set every `VINU_*_DATA_ROOT` (`VINU_AGENT_DATA_ROOT`,
`VINU_INITIAL_ANALYSIS_DATA_ROOT`, one per `vinu-*` package). These have
**no default** — `require_data_root()` in `vinu-infra/config.py`
deliberately fails fast if any is missing, so don't skip this even for a
local test run.

New env knobs added 2026-09-07 (defaults already safe, no need to set unless tuning):
- `VINU_RESEARCH_PAPER_REHEARSAL_ENABLED=true`, `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS=7`, `VINU_RESEARCH_PAPER_REHEARSAL_MAX_DEGRADATION=0.5` — trailing 7-day bar-by-bar rehearsal before `risk_gatekeeper` (Row 1 `c3d94756`)
- `VINU_AGENT_POSITION_SIZING_METHOD=fractional_kelly`, `VINU_AGENT_KELLY_FRACTION=0.25`, `VINU_AGENT_RISK_PER_TRADE_PCT=0.02`, `VINU_AGENT_ATR_STOP_MULTIPLE=2.0` — quarter-Kelly decided (Row 5)
- `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL=900`, `VINU_AGENT_PLANNER_INTERVAL=1800`, `VINU_RESEARCH_MAX_ITERATIONS=5` — caps `N/K` decided provisional (Row 7)
- `VINU_STAGE1_START_DATE=2022-01-01` must stay — freeze manifest `vinu_infra/freeze.py` hashes `VINU_*` env + `*_DATA_ROOT` for lineage

## Step 3 — bootstrap the secret files

```bash
scripts/setup-secrets.sh --check    # validates only, writes nothing
```

Windows (PowerShell) hosts: use the equivalent script instead —
`setup-secrets.sh` needs bash, which plain PowerShell doesn't run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-secrets.ps1 -Check
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

## Step 4 — download the pretrained models (do this BEFORE `docker compose up`)

Verified against the real code (`vinu-infra/models.py`,
`docker-compose.yml`): `vinu-news` (FinBERT sentiment) and
`vinu-initial-analysis` (Chronos, TimesFM, Timer-XL, Kronos +
Kronos-Tokenizer — 4 of the 28 angles) load pretrained weights from
`./data/models/` on the **host**, mounted into both containers
**read-only** (`./data/models:/models:ro`, `VINU_MODELS_DIR=/models`).
Read-only means the container cannot download anything itself — if the
weights aren't already on the host before the container starts, that
angle/model fails at load time every cycle, not just once.

```bash
make models          # downloads every registered model into ./data/models/
```

This can take a while the first time (Chronos-T5-large alone is a few GB)
— it's a real `huggingface_hub.snapshot_download()` per model, not
instant. Check status any time, before or after:

```bash
make models-list
```

```
Models dir: ./data/models
  chronos-t5-large             downloaded  <- amazon/chronos-t5-large
  chronos-t5-tiny              missing     <- amazon/chronos-t5-tiny
  finbert                      downloaded  <- ProsusAI/finbert
  kronos                       downloaded  <- NeoQuasar/Kronos-base
  kronos-tokenizer             downloaded  <- NeoQuasar/Kronos-Tokenizer-base
  lag-llama                    missing     <- time-series-foundation-models/Lag-Llama
  moirai                       missing     <- Salesforce/moirai-1.0-R-small
  moment                       missing     <- autonlab/MOMENT-1-small
  timer-timerxl                downloaded  <- thuml/timer-base-84m
  timesfm-2.5-200m-pytorch     downloaded  <- google/timesfm-2.5-200m-pytorch
```

`missing` on `lag-llama`/`moirai`/`moment` is expected and fine to leave —
their weights ARE downloadable (`make models` will pull them too if you
let it finish), but their angle loaders aren't wired up yet (each needs a
conflicting shared-env change — see `vinu-infra/models.py`'s own comment)
and they run on an honest fallback proxy instead. Only worry if one of
the other 7 (`finbert`, `chronos-t5-large`, `timesfm-2.5-200m-pytorch`,
`timer-timerxl`, `kronos`, `kronos-tokenizer`) stays `missing` after
`make models` finishes — that's a real gap, not an expected one, and
`vinu-news`/`vinu-initial-analysis` will error on that specific
model/angle at runtime.

To download only what you actually need right now (e.g. skipping the
large, currently-unwired ones):

```bash
vinu-models --model finbert --model chronos-t5-large --model timesfm-2.5-200m-pytorch --model timer-timerxl --model kronos --model kronos-tokenizer
```

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

### Confirm the models actually loaded inside the containers, not just on disk

`make models` puts the weights on the host; this checks the *containers*
can actually see and load them (a wrong mount, permission issue, or a
model that finished downloading after the container already started can
still leave a service silently failing per-angle):

```bash
docker compose exec initial-analysis-api ls /models
# expect: chronos-t5-large  finbert  kronos  kronos-tokenizer  timer-timerxl  timesfm-2.5-200m-pytorch
# (finbert only needs to be visible to news-api, not this one, but no harm either way)

docker compose logs initial-analysis-api | grep -iE "model|checkpoint|download" | tail -20
# watch for a load error here, not a download attempt -- a download
# attempt from inside the container means Step 4 was skipped or the
# mount didn't take, since the mount is read-only and can't self-heal
```

If a specific angle keeps failing (check `vinu-initial-analysis` logs for
`Angle <name> failed`), re-run `make models-list` and confirm that
angle's specific model shows `downloaded`, not `missing`.

### How the API key actually works

Every service reads the same `VINU_API_KEY` (via `vinu-infra/auth.py`) and
requires it on every route **except** `/health` endpoints, which are
deliberately left open so Docker's own healthcheck (and any orchestrator's
liveness probe) can reach them without credentials — that's not a gap,
it's intentional.

The key goes in a real `Authorization: Bearer` header — **not** a custom
header name, and there's no other accepted form:

```bash
Authorization: Bearer <the value in ./secrets/vinu_api_key>
```

Get the actual value with:

```bash
cat ./secrets/vinu_api_key
```

Confirm auth is actually enforced, not silently open, against a real
protected route (health routes will always return 200 with or without a
key, so don't use one to test this — e.g. vinu-agent's
`/agent/broker/performance/{artifact_id}`, port 8086 by default):

```bash
KEY=$(cat ./secrets/vinu_api_key)

curl -i http://localhost:8086/agent/broker/performance/test
# expect 401 Unauthorized (no header sent)

curl -i -H "Authorization: Bearer wrong-key" http://localhost:8086/agent/broker/performance/test
# expect 403 Forbidden (header sent, value doesn't match)

curl -i -H "Authorization: Bearer $KEY" http://localhost:8086/agent/broker/performance/test
# expect a real response (404/200/etc, not 401/403) -- proves the key is accepted
```

If the unauthenticated call succeeds (anything other than 401), `VINU_API_KEY`
didn't make it into `./secrets/vinu_api_key` — go back to step 3. Every other
service follows the identical pattern: swap the port and path prefix
(`/news/...` on 8080, `/stock/...` on 8081, `/portfolio/...` on 8090, etc. --
each service's prefix matches its `route_prefix` in that service's
`server/app.py`).

## After it's running — what to actually do (updated 2026-09-07)

**Predict first, then watch.** Before a test run, estimate it:
`python3 scripts/collect-timings.py predict --tickers AAPL,MSFT,NVDA`
(uses `test-status/timing-baselines.json` + worker cadences from `.env`;
today's truth: ~7 min compute + ~112 min cadence waits ≈ 120 min for 3 tickers).
During the run, track it:
`python3 scripts/collect-timings.py collect --run-id <id>` then
`progress --run-id <id>` (actual vs p50 per stage).
After (or during), scan for failures:
`python3 scripts/watchdog.py --watch` (appends to
`test-status/failures.jsonl`; exit 1 if open incidents).

1. **Seed a watchlist.** Nothing proposes candidates until the Planner has
   tickers to look at — check whichever config/table the watchlist lives in
   (per the design doc, this is the entry point the change-gate reads from).
2. **Confirm the Kill Switch state is what you expect.** It's meant to be a
   deliberate, explicit gate — check `broker/kill_switch.py`'s current state
   before assuming trades will actually execute or that a halt is active
   when you think it is. Note: `OrderGuard` now throttles `10 orders/sec` (`B20`) and blocks even risk-reducing rebalance `REQUEST` by default (`decisions/12`).
3. **Watch the first full cycle end to end** in the logs: Summary Agent →
   Planner triage → Researcher/Executor sweep (+ `PaperRehearsalResult` 7-day) → risk_gatekeeper verdict →
   PEND → capital_allocator (batched, with `replace` unwind `REQUEST` if `PEND deflated_sharpe >= worst ACTIVE +0.8`, composition `gaps` check) →
   funded or held. This is the single best way to confirm the pipeline is
   actually doing what the design doc says, not just that processes started.
4. **Check Significance Triage delivery**, if you set Telegram/Discord
   credentials — trigger something notable (or wait for a real one) and
   confirm a message actually arrives, not just that the code path ran. Delivery is manual gate until creds observed (`decisions/09`).
5. **Sanity-check the TickerLedger** is accumulating real events for tickers
   you're watching — taxonomy now pinned `stage/event_type/source` (`decisions/10`), append-only, `ref_id` points to real row. This is the ticker-keyed audit trail everything else in the design writes to.
6. **(New) Run freeze manifest** for lineage: `python -c "from vinu_infra.freeze import freeze_manifest; freeze_manifest('freeze.json')"` — hashes `VINU_*` env + `*_DATA_ROOT` file hashes (`B21`, `vinu_infra/freeze.py`). Use `contamination_check(old,new)` between research and live to prove no data drift.
7. **(New) Check shock batch:** `TradePlanOrchestrator.cycle_shock_batch(max_batch=5)` now scores by `shock_clustering` + `shock_personality` and prioritizes top batch — not just `on_shock_event` debounced 60s per symbol.

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
- **New since v1:** `PaperRehearsalResult` (Row 1), `replace` REQUEST (Row 2), `cycle_shock_batch` (Row 3), `composition_view` (Row 4), `OrderGuard` throttle `10/sec` (B20), `freeze_manifest` (B21) — see `04-new-full-explanation-v2.md` + `pending-items-to-be-implemented.md` Status 2026-09-07.
- **Known follow-up, not urgent**: task 01's capital-allocator-worker test
   doesn't yet exercise the actual scheduling loop (only the cycle function it
   calls) — the worker itself is confirmed working in practice, this is just a
   test-coverage gap to close eventually. Also `ShadowEvaluator` tick wallet still spiked (B24).
- **If you ever add a new committed file with real credentials in it by
  mistake**, follow the leaked-credential playbook in
  `docs/secrets-rotation.md` immediately — rotate at the provider first,
  don't just delete the file.
