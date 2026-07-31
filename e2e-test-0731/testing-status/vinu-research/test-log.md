# vinu-research — Test Log

**Status:** Not started

## What will be tested

**This is where the complex tier's entire test lives** — there is no
`vinu-strategy` YAML for it (see
[../../scope-responsibilities/vinu-strategy.md](../../scope-responsibilities/vinu-strategy.md)).
Testing means calling this service's real endpoints directly for AAPL,
TSLA, JNJ and inspecting the output, not writing rule conditions:

1. **Prerequisite check:** `VINU_RESEARCH_LLM_ENABLED` must be `true` in
   `vinu-components/.env` (currently `false` — flip before testing this
   component, otherwise the LLM path likely never gets exercised).
2. **LLM connectivity:** local OpenAI-compatible server on the host at
   port 8009 (`qwen36-35B`), reachable from inside the `research-api`
   container via `http://host.docker.internal:8009/v1`. Confirm this
   actually connects before trusting any generated output — `extra_hosts`
   is configured in `docker-compose.yml` but has never been exercised.
3. **`POST /trade-plan/{symbol}`** for each of AAPL, TSLA, JNJ — the core
   call. Internally this should invoke the LLM (`forecast_skill.py`) to
   produce a forecast, then use calibration data
   (`judgment_store.py`) to compute a probability-scored exit level
   (`trade_plan_authoring.py` — built in Step 03 of the prior audit plan).
4. **`POST /trade-plan/{artifact_id}/calibration`** — recording an
   outcome and confirming calibration data actually updates.
5. **`POST /run` / `POST /ensure` and `POST /artifacts/{id}/promote`** —
   the broader strategy-generation/promotion loop, and recording the
   Stage 1 run as a queryable artifact for the "research again" step
   between Stage 1 and Stage 2.

## Expected output

- A real, non-trivial forecast per symbol from the actual `qwen36-35B`
  model — not an error, not an empty stub, not a template fallback.
- The exit level in the trade plan is plausibly derived from the forecast
  (direction/magnitude) and calibration data, not a fixed constant
  regardless of input.
- If `host.docker.internal:8009` is unreachable from inside the
  container, or `VINU_RESEARCH_LLM_ENABLED=false` silently short-circuits
  to a template, that's a `Bug-N` here — not a silent substitution that
  makes "complex" indistinguishable from "medium."
- Calibration recording actually changes what a subsequent trade-plan
  call returns for the same symbol (proof the calibration loop is real,
  not a no-op).
- Promotion gating blocks a strategy that fails
  walk-forward/holdout/stress tests from reaching ACTIVE.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its storage DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `research-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'` in
  `ResearchStorage.__init__`.
- **Reproduction:** `docker compose up -d` then `docker compose logs research-api`.
- **Suspected cause:** same bug class as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 — `vinu-components/.env` sets
  `VINU_RESEARCH_DATA_ROOT=../data/research`, a local-dev-style relative
  path overriding the Dockerfile's correct default
  (`ENV VINU_RESEARCH_DATA_ROOT=/data`).
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs research-api` —
  same shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_RESEARCH_DATA_ROOT`
  changed from `../data/research` to `/data`; host-directory ownership
  fixed via the shared `chown -R 100:101` fix.
- **Verification:** `docker compose ps` → `research-api ... (healthy)`,
  no tracebacks in `docker compose logs research-api`.
- **Status:** fixed.
