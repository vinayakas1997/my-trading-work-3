# vinu-research — Test Log

**Status:** VERIFIED (2026-08-02) — LLM connectivity confirmed; real
trade plans generated for AAPL/TSLA/JNJ via `qwen36-35B`; calibration loop
works. One config fix needed (LLM timeout), logged below.

## Verification results (2026-08-02)

- **Prereq `VINU_RESEARCH_LLM_ENABLED`:** already `true` in `.env`; confirmed
  inside container.
- **LLM connectivity (container→host):** success. `host.docker.internal:8009`
  reachable from `research-api`; verified model `qwen36-35B` (n_ctx 32000).
  Note: model is a *reasoning* model — with too-small `max_tokens` it fills
  `reasoning_content` and returns empty `content`. Service uses
  `VINU_LLM_MAX_TOKENS=8000`, fine.
- **`POST /research/trade-plan/{symbol}`** (complex tier core):
  - `AAPL` → `art_86803b85d69c`, **long**, confidence **0.55**,
    magnitude **0.5%**, 1-day horizon, real reasoning about
    win-rate/Kelly/vol-persistence/gap-fill; risk_bands,
    contingency_rules, invalidation_conditions all populated.
  - `TSLA` → `art_07af597dd6c25`, **neutral**, conf **0.38**.
  - `JNJ` → `art_2022...`, **neutral**, conf **0.45`.
  - Each plan is distinct + data-driven (not a template), and forecast
    includes direction/magnitude/confidence/reasoning extracted from the
    actual model output.
- **`POST /trade-plan/{id}/record-outcome`:** recorded `forward_return_pct 0.6`
  on AAPL → returns `directional_correct: true`, `brier_score 0.2025`,
  `magnitude_error 0.167`.
- **`GET /trade-plan/{id}/calibration`:** n_entries 1, accuracy 1.0,
  brier_mean 0.2025, magnitude_mape 0.167; `passed:false` with reason
  `insufficient calibration entries (1 < 10)` — promotion gate working.

### Bug-7 — research LLM forecast times out at the default 120s timeout

- **Found during:** first `POST /research/trade-plan/AAPL`. Returned empty
  body; logs show `LLM request error to http://host.docker.internal:8009/v1
  (ReadTimeout)` then retries 1/3, 2/3 — the whole forecast call exceeded
  `VINU_LLM_TIMEOUT_SEC` (default `120.0`, research
  `config.py:195`), which is too short for `qwen36-35B`'s 8000-token
  reasoning generation.
- **Date:** 2026-08-02
- **Symptom:** empty trade-plan response, ReadTimeout in logs, no artifact
  created.
- **Cause:** reasoning model + large prompt/token budget requires more than
  120s; the client configured a 120s read deadline.
- **Fix applied:** added `VINU_LLM_TIMEOUT_SEC=600` to `vinu-components/.env`;
  restarted `research-api`. trade-plan then completed (status CREATED with a
  full plan).
- **Status:** fixed. (Note: the shared `vinu-lib` LLM client uses the same
  `_DEFAULT_TIMEOUT_SEC` — worth re-checking `news-api`/`agent-api` paths
  that also drive LLM calls for the same bound.)

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
