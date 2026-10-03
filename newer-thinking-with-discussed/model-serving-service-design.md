# Model-serving service (`vinu-models`) — design

Status: **built 2026-10-03** (see "As built" at the end; it differs from the plan below in one respect: the whole angle `compute()` runs in the service, it is not split in two).

Written 2026-10-03.

## Why

- The analysis angles that need `torch` (Chronos, TimesFM, Kronos, Timer, and the trained ones: LSTM, DLinear, PatchTST, LPatchTST, iTransformer, TFT, TIPS) run **inside `vinu-initial-analysis`**. That makes the whole analysis service depend on `torch`, a GPU reservation and 8 GB of memory, and it is why its test suite cannot run on a machine without `torch`.
- Three models (Moirai, MOMENT, Lag-Llama) are **downloaded but not wired** because their libraries conflict with the shared environment (`uni2ts` downgrades torch, `momentfm` fails to build, `gluonts` downgrades pandas). A separate service can hold those conflicts in its own container.
- The Chronos angle silently falls back to a simple proxy when the model cannot load. It is labelled in the row (`model_backend: fallback_proxy`) but nobody is told. The service should say "unavailable" loudly instead.

## What it is

One new container, **`models-api`**, port **8096** (8080-8084, 8086, 8087, 8090, 8091 and 8095 are taken). It only runs models. It knows nothing about angles, tickers, run logs or storage.

```
initial-analysis-api  --HTTP-->  models-api  --> /models (read-only weights), GPU
 (windowing, row shaping,         (load, cache, infer)
  RunLog, storage; no torch)
```

## API (all internal-auth, same headers as the other services)

| Route | Purpose |
|---|---|
| `GET /models/health` | Per model: `available` / `loaded` / `unavailable` + reason, device, loaded checkpoint, policy version. 200 even if a model is down; the service itself being up is separate from each model. |
| `GET /models/registry` | Registered models and checkpoints (from `vinu_infra.models.MODELS`). |
| `POST /models/{model}/load` | Warm a model (optional; otherwise lazy on first call). |
| `POST /models/{model}/forecast` | Body: `{symbol, closes[] or bars[], horizon, time_format, params{}, seed?}`. Zero-shot models (Chronos, TimesFM, Kronos, Timer). |
| `POST /models/{model}/fit-forecast` | Same body; for models trained per ticker (LSTM, DLinear, PatchTST, ...). Same response envelope. |
| `POST /models/{model}/forecast/batch` | Up to N items in one call. A walk-forward backtest makes hundreds of forecasts; one request each would be wasteful. |

Response envelope for every call:
`{model, checkpoint, model_backend: "pretrained"|"trained"|"proxy", device, latency_ms, policy_version, forecast: {...}, meta: {...}}`.
Errors are explicit: `503 {error: "model_unavailable", reason}` (missing weights, out of memory, library missing), `422` for bad input. **No silent proxy**: a proxy result is returned only when the caller sent `allow_proxy: true`, and then `model_backend` says `proxy`.

## How the angles change

Each model angle is split in two, and only the second half moves:

1. **Stays in initial-analysis:** minimum-observations check, context windowing (e.g. last 512 closes), turning the forecast into the angle's output row, RunLog, storage.
2. **Moves to the service:** the model call itself (`_forecast`, `_get_pipeline`, training loops). The vendored Kronos code (`angles/kronos/_kronos_model/`) moves with it.

A small `ModelClient` (built on the existing `ResilientClient`) is added to `vinu-infra`. Switch: **`VINU_MODEL_SERVICE_URL`**. Unset = angles run in-process exactly as today (zero-risk rollout, and the old path keeps working until the end). Set = angles call the service.

When the service is set but unreachable or a model is unavailable, the runner records an `error` run with the reason (same mechanism as the price-fetch fix), so the run is retried later, never stored as a healthy empty result. `models_enabled()` / `VINU_MODELS_ENABLED` and `VINU_<ANGLE>_CHECKPOINT` keep working: the policy version is returned by the service and stamped on rows as today.

## Container

- Own `Dockerfile` with `torch`, `chronos-forecasting`, `timesfm[torch]`, GPU base image; weights from `./data/models:/models:ro` (same mount as now); `read_only: true`, `cap_drop: ALL`, `tmpfs /triton-cache` (rw, exec) copied from the current initial-analysis settings.
- The `nvidia` GPU reservation and most of the memory limit **move** from `initial-analysis-api` to `models-api`; initial-analysis becomes a small CPU container.
- Models load lazily and are kept in an LRU cache bounded by `VINU_MODELS_MAX_LOADED` (default 2), so a single GPU is not asked to hold every model.
- One inference at a time per GPU (a queue), with a per-request timeout (default 120 s; Chronos-large measured about 14 s per forecast on CPU).
- `depends_on` for initial-analysis becomes a soft dependency: it starts without the model service; model angles report unavailable until it is up.

## Observability (reuses the edge recorder)

New edge `models.forecast->initial_analysis.angle` recorded per call (`received` / `missing` on a refused or unreachable service). `GET /research/pipeline-edges?only_problems=true` then shows a dead model service without anyone reading logs. `/models/health` also feeds the existing system health view.

## Dependency-conflicting models (later)

`models-api` is a gateway with a model → backend table. Models whose libraries conflict (Moirai, MOMENT, Lag-Llama) get their own tiny container (`models-api-moirai`, ...) behind the same routes. Nothing else changes for callers.

## Rollout

| Phase | What | Risk |
|---|---|---|
| 0 | Skeleton service: health, registry, load, auth; fake-model contract tests that need no `torch` | none |
| 1 | `ModelClient` + `VINU_MODEL_SERVICE_URL` switch; Chronos moved as the proof; compare service output with in-process output on the same input | none (flag off by default) |
| 2 | Move TimesFM, Kronos, Timer | low |
| 3 | Move the trained models (fit-forecast); batch endpoint for backtests | medium (training time, queueing) |
| 4 | Remove `torch` and the GPU reservation from initial-analysis; its full test suite then runs anywhere | low |
| 5 | Wire Moirai / MOMENT / Lag-Llama in their own containers | optional |

## Decisions already made (so none are left open)

- Synchronous HTTP with a batch route first; an async job API only if a real call exceeds the timeout.
- The service returns forecasts only; it never writes to the analysis store.
- Forecast sampling takes an optional `seed` so a comparison between the in-process and service paths can be exact.
- Gateway pattern for conflicting models, not one giant environment.

## Tests

- Service: contract tests with fake model backends (no `torch`), including 503 on unavailable, no silent proxy, batch limits, LRU eviction.
- Client: unreachable / timeout / 503 each produce the error run, never an empty "completed" run.
- Equivalence: for each moved model, the same input through the in-process path and the service path gives the same output (seeded).
- Initial-analysis suite after phase 4 passes without `torch` installed.

## As built (2026-10-03)

- **Simpler split than planned.** Instead of splitting every angle into "prepare" and "infer", the service runs each model angle's own `compute()` (the code is imported from the `vinu-initial-analysis` package, one source of truth, no copy). The runner sends the bars and news and gets the rows back. All 11 model angles move at once, with no rewrite of any angle.
- **Service:** `vinu-models/` (`vinu_models/service.py`, `server/app.py`, `cli.py`, `Dockerfile`, tests). Port **8096**, docker service **`models-api`**. Routes: `GET /models/health` (liveness), `GET /models/status[?deep=true]` (per-angle availability; `deep` imports every angle), `GET /models/angles`, `POST /models/angle/{angle}/compute`, `POST /models/finbert/score`.
- **Errors are typed:** 404 unknown / non-model angle, 503 `models_disabled`, 503 `model_unavailable` (a library such as torch is missing, with the message), 504 `timeout`, 500 `compute_error`, 422 bad request. The GPU slot (`VINU_MODELS_MAX_CONCURRENT`, default 1) stays held until a timed-out computation really ends.
- **Proxy rows:** an angle's own `fallback_proxy` row (model could not load) is passed through and counted (`backends` in the response, `proxy_rows` in `/models/status`); `VINU_MODELS_ALLOW_PROXY=false` turns it into a 503 instead.
- **Client:** `vinu-infra/model_client.py` (`VINU_MODEL_SERVICE_URL`, `VINU_MODEL_SERVICE_TIMEOUT_SEC`). Any failure raises `ModelServiceError` with a reason; the runner records an `error` run (retried later), news raises.
- **initial-analysis:** model-category angles go to the service when the URL is set and are never imported locally. `torch`, `chronos-forecasting` and `timesfm` moved from its dependencies into an optional `models` extra; its image no longer installs them, loses the GPU reservation (8 GB to 4 GB). `storage/weights.py` imports torch lazily; `write_summary` no longer needs the torch registry.
- **news:** FinBERT scoring moved into `vinu-infra/finbert_scoring.py` (lazy torch) and is called through the service; `torch` and `transformers` moved from its dependencies into an optional `models` extra and out of its Dockerfile and `/models` mount.
- **Compose:** new `models-api` (GPU, 8 GB, `./data/models:/models:ro`, `./data/initial-analysis:/data`). `initial-analysis-api` and `news-api` get `VINU_MODEL_SERVICE_URL` and the edge mount; neither depends on `models-api` (they start without it).
- **Edges:** `models.angle_compute->initial_analysis.runner` and `models.finbert_score->news.backfill` (both instrumented): a dead or refusing model service shows in `GET /research/pipeline-edges?only_problems=true`.
- **Not done / limits:** the backtest registry (`orchestration_registry`, offline walk-forward batches) still imports every model backtest, so it runs in an environment with torch (the models image has it). Moirai, MOMENT and Lag-Llama stay disabled. No Docker image was built (Docker was not running). Real models were run through the live service with a real torch in a temporary environment; see `04-implementation-status.md` "Model-serving service".
