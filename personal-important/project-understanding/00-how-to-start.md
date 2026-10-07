---
name: how-to-start
status: operational guide, matches the actual code/scripts as of 2026-09-11 (v3 — adds the pretrained-model-download step, verified against the real vinu-infra/models.py + docker-compose.yml mounts). 2026-09-15 addendum: added the two new optional env-knob groups from that session's work (reserve fraction, role-based LLM config) -- everything else below unchanged/not re-verified in this pass. 2026-09-21 addendum (v4): added a source-verified knobs inventory for running a real test (date ranges, auto-vs-manual toggles, watchlist seeding, candidate limits). v5 (2026-09-21, same day): restructured the whole doc around one split -- Part A is the shared bring-up steps every deployment needs regardless of purpose; Part B is "run this for real" (production/live-money framing); Part C is "run this as a test" (the v4 knobs inventory + the test-day walkthrough). Content is unchanged from v4, only reorganized, except where noted.
purpose: step-by-step to bring the vinu-components stack up from a clean machine, plus what to check once it's running -- and, critically, which of what follows applies to a real production deployment vs a supervised test run, since several knobs (credentials, cadences, date ranges) genuinely differ between the two.
note: the "Ongoing operational checklist" and "test-day walkthrough" sections reference some older decision/row IDs from the 2026-09-07 phase of the project that weren't re-verified in this pass -- Part A's steps (through the model-download and auth-verification steps) ARE freshly re-verified against the current code as of this edit, and Part C's knobs inventory was verified 2026-09-21 directly against config.py/cli.py source.
---

# How to start the system

Everything below refers to the real repo at
`/home/somic_cps/Vina/my-trading-work-3/vinu-components`. All commands assume you're
in that directory unless stated otherwise.

**This doc has three parts.** Part A is identical either way — do it once,
regardless of what you're using the stack for. Then go to **Part B** if
you're standing this up as a real, running system (live or paper trading
that's meant to keep running), or **Part C** if you're doing a supervised
test run (a bounded session to verify behavior, not a long-lived
deployment). The two diverge on real things — which credentials to use,
which knobs need setting, what "done" looks like — so pick one path rather
than reading both as if they were the same checklist.

## What you'll need from the user before starting (ask for these first)

Before touching any file, get these from whoever is standing the system up
— nothing past Step 2 works without them:

1. **Alpaca API key + secret** — must be a freshly rotated pair, never the
   old leaked one in `alpaca-details/details.md`. Paper or live — either
   works, `ALPACA_PAPER=true` (default) picks paper. **This is the first
   real fork between Part B and Part C**: a production deployment (Part B)
   may want `ALPACA_PAPER=false` for real capital; a test run (Part C)
   should almost always stay on the `true` default — see Part C for why.
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

---

# Part A — Common setup (do this once, either way)

Every step in this part is identical whether you're headed to Part B (real
system) or Part C (test run) next — the stack has to actually be up and
authenticated before either kind of use makes sense.

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

New env knobs added 2026-09-15 (all default to today's exact behavior — genuinely optional, not just "safe defaults"):
- `VINU_PORTFOLIO_RESERVE_FRACTION` (default `0.0`) — holds back this
  fraction of account equity from `compute_daily_allocation` before
  sizing anything; `0.0` means deployable equity == full equity,
  unchanged from before this existed.
- `VINU_LLM_ROLES_PATH` (default: `vinu-infra/llm/roles.json`, which
  ships with every role empty) — points the role-based LLM config
  (`missing-pieces-of-system/llm-configuration-settings-system/`) at a
  different file, e.g. to give the orchestrator tier a different
  model/endpoint than teams/specialists without touching
  `VINU_ORCHESTRATOR_LLM_*` (which still wins if set).
- `VINU_LLM_ROLE_<ROLE>_BASE_URL` / `_MODEL` / `_API_KEY` / `_MAX_TOKENS`
  / `_TIMEOUT_SEC` / `_RETRY_MAX` — per-role, per-field override, layered
  on top of `roles.json`, layered on top of the existing plain
  `VINU_LLM_*` defaults. Only takes effect for a role that actually gets
  passed to `get_llm_config_for_role`/`ResearchLlmClient(role=...)` —
  today that's `orchestrator` (vinu-agent) and `forecast_skill`
  (vinu-research).

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

---

# Part B — Running this as a REAL (production) environment

Stack is up (Part A done). This part is for a deployment meant to actually
keep running — real or paper trading, unattended, on the shipped
production cadences. **If you're doing a bounded, supervised test session
instead, skip to Part C** — several of Part C's knobs (shorter date
ranges, faster cadences, manual gate triggers) would be actively wrong to
leave set on a real deployment.

## What's different about "real" vs "test"

- **Leave every cadence at its shipped default.** `VINU_AGENT_PLANNER_INTERVAL=1800`,
  `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL=900`, `VINU_LIVE_SHADOW_INTERVAL=3600`, etc.
  are the real, deliberately-chosen production values (see
  `01-new-full-explanation-v2.md`'s cadence table) — don't shorten them the
  way Part C does for a test window.
- **Leave `VINU_STAGE1_START_DATE` at whatever the real backfill needs**
  (default `2022-01-01`) — this is hashed into the freeze manifest
  (`vinu_infra/freeze.py`) for lineage, so it should stay fixed for the
  life of the deployment, not be tuned down the way a short test would.
- **Decide `ALPACA_PAPER` deliberately.** `true` (default) is paper —
  real order flow through a real paper account, safe to leave running
  unattended. `false` is real capital — only set this once you've actually
  watched a full cycle behave correctly (Part C's walkthrough is the right
  way to build that confidence first, even on a paper account).
- **Watchlist seeding is a one-time bootstrap, not a per-session
  step.** Set `VINU_AGENT_WATCHLIST_SEED_TICKERS` (and, if you want
  automatic discovery beyond the static list, `VINU_AGENT_SCREENER_RANKER_ID`
  — see `vinu-screener seed-default` to create the `core_starter` ranker
  first) once; the `planner-worker` loop keeps discovering new tickers
  from it on its own cadence from then on. No manual re-seeding needed.
- **Promotion and decay stay on their real triggers.** `promotion_bar`
  only ever runs via `vinu-research promote-scan` or a direct
  `POST /artifacts/{id}/promote` call — for a live deployment, decide who
  or what calls this (a human reviewing candidates, or a cron you set up
  yourself; the codebase doesn't ship one). `decay_scan` already runs on
  its own internal hourly loop (`ScheduledResearchExecutor`, hardcoded
  3600s) — nothing to configure there.

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
- **Confirm the Kill Switch state is what you expect** before assuming
  trades will actually execute or that a halt is active when you think it
  is — check `broker/kill_switch.py`'s current state. `OrderGuard`
  throttles `10 orders/sec` (`B20`) and blocks even risk-reducing
  rebalance `REQUEST` by default (`decisions/12`).
- **Check Significance Triage delivery** periodically if Telegram/Discord
  credentials are set — confirm alerts actually arrive, not just that the
  code path ran. Delivery is a manual gate until creds are observed
  (`decisions/09`). Includes a service-wide `llm_failure_rate` detector
  (ticker="SYSTEM") that fires if 5+ LLM calls fail within an hour.
- **New since v1:** `PaperRehearsalResult` (Row 1), `replace` REQUEST
  (Row 2), `cycle_shock_batch` (Row 3), `composition_view` (Row 4),
  `OrderGuard` throttle `10/sec` (B20), `freeze_manifest` (B21) — see
  `01-new-full-explanation-v2.md` + `pending-items-to-be-implemented.md`
  Status 2026-09-07.
- **Known follow-up, not urgent**: task 01's capital-allocator-worker test
   doesn't yet exercise the actual scheduling loop (only the cycle function it
   calls) — the worker itself is confirmed working in practice, this is just a
   test-coverage gap to close eventually. Also `ShadowEvaluator` tick wallet still spiked (B24).
- **If you ever add a new committed file with real credentials in it by
  mistake**, follow the leaked-credential playbook in
  `docs/secrets-rotation.md` immediately — rotate at the provider first,
  don't just delete the file.

---

# Part C — Running this as a TEST environment

Stack is up (Part A done). This part is for a bounded, supervised session
to verify the pipeline actually behaves as designed — not a long-lived
deployment. Stay on `ALPACA_PAPER=true` (the default) unless the test's
explicit purpose is verifying live-order behavior.

## The knobs nobody would guess (verified 2026-09-21 against current source)

Every env knob a real test run silently depends on but that has no obvious
symptom when left wrong — the container starts fine, logs look clean, and
the test just quietly produces nothing or produces stale/misleading
results. Every value below was read directly from the current
`config.py`/`cli.py` source, not guessed.

### 1. Getting tickers into the pipeline at all — there is no seed command

There is **no standalone "seed the watchlist" CLI command**. Seeding only
happens *inside* the continuously-running `planner-worker` loop
(`vinu-agent/vinu_agent/cli.py`'s `planner_worker_main`) — each cycle it
merges two sources into one seed list, then calls `bootstrap_new_tickers()`
for anything not already tracked:
- `VINU_AGENT_WATCHLIST_SEED_TICKERS` — comma-separated symbols, e.g.
  `AAPL,MSFT,NVDA`. Default `""` — **if you don't set this (or the screener
  ranker below), nothing ever enters the pipeline, and the stack will run
  "healthy" forever without a single candidate.**
- `VINU_AGENT_SCREENER_RANKER_ID` — default `""` (ships inert). When set
  (e.g. `core_starter`, seeded via `vinu-screener seed-default`), the
  planner-worker also pulls the screener's live top-ranked symbols into
  the seed list each cycle. Optional — the static seed list above is
  enough for a first test.

Either way, this only fires on the `planner-worker`'s own cadence —
`VINU_AGENT_PLANNER_INTERVAL`, default `1800` (30 min). For a real test you
either wait out the first cycle after startup, or set this interval lower
for the duration of the test (see cadence note below) — and set it back
before treating the deployment as a real one (Part B).

### 2. Date ranges — a short test window can silently starve the backtest/promotion gates

- `VINU_STAGE1_START_DATE` (default `2022-01-01`) — Stage-1 analysis
  backfill start date, read by both `vinu-initial-analysis/config.py` and
  `vinu-agent/tools/angles_tool.py`. Also hashed into the freeze manifest
  for lineage (`vinu_infra/freeze.py`) — **don't change this mid-test**,
  it's meant to stay fixed once a real run has started against it. For a
  short, deliberately-bounded test, set it once before the run starts,
  not adjusted partway through.
- `VINU_RESEARCH_WF_MIN_TRAIN_DAYS` (default `252`, ~1 trading year) — a
  symbol with less history than this fails/degrades walk-forward
  validation. If you're testing against a recently-listed symbol or a
  deliberately short backfill window, this will silently gate every
  candidate for that symbol.
- `VINU_RESEARCH_MIN_TRADES_FOR_PASS` (default `30`) — a backtest that
  produces fewer than 30 trades over the test window fails promotion
  regardless of how good it otherwise looks. A short test window or a
  low-frequency strategy can fail this purely on trade count, not quality
  — worth checking before concluding a strategy is "bad."
- `VINU_RESEARCH_HOLDOUT_FRACTION`/`_HOLDOUT_GAP_DAYS` (default `0.2`/`5`)
  — the promotion-bar holdout split; combined with `WF_MIN_TRAIN_DAYS`
  above, a short overall history can leave too little data for both a
  train window and a holdout window to coexist.

### 3. Things that are already ON by default in docker-compose.yml — don't re-set them

`VINU_STRATEGY_EVAL_DATA_ROOT` (the strategy-evaluation audit trail —
`vinu-agent strategy-eval <TICKER>`'s data source, covering all 10 real
evaluation/rejection gates) is **already wired to `/strategy-eval` for
`agent-api`/`research-api`/`live-api`** in `docker-compose.yml` — nothing
to set in `.env` for this one. It's mentioned here only because the code
itself describes it as "ships inert when unset," which could read as
something you need to opt into; under `docker compose up`, you don't.

### 4. Cron-driven vs manual-only — know which one you're waiting for

- **Decay scan** (`decay_scan`, one of the 10 real evaluation gates) runs
  on an internal hourly loop inside `vinu-research`'s
  `ScheduledResearchExecutor` — not env-configurable, hardcoded to 3600s.
  For a real test you will likely NOT see a decay cycle fire naturally;
  trigger it manually instead: `vinu-research decay-scan`.
- **Promotion** (`promotion_bar`) is **never** on a cron — it only runs
  via the manual `vinu-research promote-scan` CLI command or a direct
  `POST /artifacts/{id}/promote` call. If a test's artifacts are sitting
  in `BENCHING` and you're waiting for them to move, they won't on their
  own — run `promote-scan` explicitly.
- **LLM-assisted candidate generation** is off by default —
  `VINU_RESEARCH_LLM_ENABLED=false`. The research generator still runs in
  `hybrid` mode without it (template/rule-based candidates), but if the
  test is specifically meant to exercise LLM-driven idea generation, this
  needs to be explicitly set to `true`.

### 5. Candidate limits — not env-configurable, worth knowing before you go looking for a knob

`K_CAP_DEFAULT = 3` and `K_CAP_WINDOW_DAYS`/non-terminal-artifact-count cap
(how many open candidates one ticker can have at once) are **hardcoded
Python constants** in
`vinu-agent/vinu_agent/agent/thesis_intake_gate.py`, not env vars — if a
test needs a different cap, that's a code change, not a `.env` change.

### 6. Worker cadences too slow to observe inside a short manual test

Several real-pipeline workers run on cadences of 15-60+ minutes by
default (`VINU_AGENT_PLANNER_INTERVAL=1800`,
`VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL=900`, `VINU_LIVE_SHADOW_INTERVAL=3600`,
`VINU_LIVE_INTERVAL=3600`). For a short, supervised test session, either
budget real wall-clock time for each stage to fire naturally (see the
`collect-timings.py predict` step below, which already accounts for this),
or lower the relevant interval env var for the duration of the test only
— **this is exactly the setting Part B tells you NOT to touch once the
deployment is real**, so remember to restore the production defaults
before treating this environment as anything other than a test.

## Test-day walkthrough

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
   tickers to look at — set `VINU_AGENT_WATCHLIST_SEED_TICKERS` (and
   optionally `VINU_AGENT_SCREENER_RANKER_ID`) and let the `planner-worker`
   loop pick it up on its next cycle. See section 1 above — there is no
   separate one-shot seed command.
2. **Confirm the Kill Switch state is what you expect.** It's meant to be a
   deliberate, explicit gate — check `broker/kill_switch.py`'s current state
   before assuming trades will actually execute or that a halt is active
   when you think it is. `OrderGuard` throttles `10 orders/sec` (`B20`) and
   blocks even risk-reducing rebalance `REQUEST` by default (`decisions/12`).
3. **Watch the first full cycle end to end** in the logs: Summary Agent →
   Planner triage → Researcher/Executor sweep (+ `PaperRehearsalResult` 7-day) → risk_gatekeeper verdict →
   PEND → capital_allocator (batched, with `replace` unwind `REQUEST` if `PEND deflated_sharpe >= worst ACTIVE +0.8`, composition `gaps` check) →
   funded or held. This is the single best way to confirm the pipeline is
   actually doing what the design doc says, not just that processes started.
4. **Check Significance Triage delivery**, if you set Telegram/Discord
   credentials — trigger something notable (or wait for a real one) and
   confirm a message actually arrives, not just that the code path ran. Delivery is manual gate until creds observed (`decisions/09`).
   As of 2026-09-15 this also includes a 4th, service-wide detector
   (`llm_failure_rate`, ticker="SYSTEM") that fires if 5+ LLM calls fail
   within an hour — worth deliberately breaking the LLM endpoint once to
   confirm this actually alerts, since it's new and reads a table
   (`telemetry.db`) nothing else in the system consumes yet.
5. **Sanity-check the TickerLedger** is accumulating real events for tickers
   you're watching — taxonomy now pinned `stage/event_type/source` (`decisions/10`), append-only, `ref_id` points to real row. This is the ticker-keyed audit trail everything else in the design writes to.
6. **Read the strategy-evaluation audit trail** for any ticker whose
   candidates you're following: `vinu-agent strategy-eval <TICKER>` — shows
   every candidate, how far it got through the 10 real evaluation gates,
   and for any FAIL, the specific real reason plus the general rule from
   the step registry. This is the fastest way to answer "why didn't this
   one get promoted" without reading code.
7. **(New) Run freeze manifest** for lineage: `python -c "from vinu_infra.freeze import freeze_manifest; freeze_manifest('freeze.json')"` — hashes `VINU_*` env + `*_DATA_ROOT` file hashes (`B21`, `vinu_infra/freeze.py`). Use `contamination_check(old,new)` between research and live to prove no data drift.
8. **(New) Check shock batch:** `TradePlanOrchestrator.cycle_shock_batch(max_batch=5)` now scores by `shock_clustering` + `shock_personality` and prioritizes top batch — not just `on_shock_event` debounced 60s per symbol.

**Before promoting this from a test to a real deployment**: revert every
cadence/date-range knob you lowered for the test window back to Part B's
production defaults, and re-read Part B's "What's different" list — it's
written as the mirror image of this section specifically so nothing gets
missed in that direction either.
