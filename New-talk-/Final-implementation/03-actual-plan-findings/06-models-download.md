---
name: models-download
status: discussion-phase
purpose: plan to replace the current split model handling — FinBERT baked into the vinu-news image, Chronos/TimesFM downloaded live to a tmpfs cache (wiped every restart) — with a single shared, gitignored models directory under data/models/ plus one idempotent download command, so all downloadable pretrained weights are fetched once into a known place and served locally at runtime instead of baked or re-downloaded.
---

# Models — Shared Download Directory Plan

## Why this change

Today's model handling is inconsistent and has a real bug:

- **FinBERT** (vinu-news) is baked into the image at build time
  (`/app/models/finbert`, `vinu-news/Dockerfile` `RUN ... save_pretrained`)
  — ~430MB baked into every image build.
- **Chronos / TimesFM** (vinu-initial-analysis) are *not* baked — they hit
  the Hugging Face Hub live on first use and cache under
  `~/.cache/huggingface`. But every container runs `read_only: true` with
  tmpfs on `/home/app/.cache` (`vinu-components/docker-compose.yml` lines
  23-26, 135-137). **Tmpfs is wiped on every restart, so the ~1.4GB of
  weights re-download on every single container restart.**

Goal: one shared models directory + one idempotent download command; models
are fetched once, stored in a known place, and served from disk at runtime —
no baking into images, no re-download on restart.

## 1. Target directory

`vinu-components/data/models/` (gitignored), one subdir per model:

```
data/models/
├── finbert/                    # ProsusAI/finbert
├── chronos-t5-tiny/            # amazon/chronos-t5-tiny
├── timesfm-2.5-200m-pytorch/   # google/timesfm-2.5-200m-pytorch
├── moirai/                     # Salesforce/moirai-1.0-R (weights-only; uni2ts torch issue stays)
├── moment/                     # autonlab MOMENT weights
└── ...
```

Add `data/models/` to `vinu-components/.gitignore`.

## 2. Download command — `download_models.py`

- Lives in `vinu-infra` (or a `scripts/` dir) with a `make models` target
  in the Makefile.
- Env/flag: `--model all` (default) or `--model finbert|chronos|timesfm|...`.
- **Idempotent**: skips any model already present in `data/models/`.
- Uses `huggingface_hub.snapshot_download()` into a known local dir (not the
  default HF cache), so weights live in our tree and loaders point directly
  at them.
- **Auto-check**: loaders check `data/models/<model>` first; if missing they
  auto-download (same helper) before loading — manual command + auto-check.

## 3. Loader changes (local-first, no baking)

- `vinu-news/.../finbert_sentiment.py` — `MODEL_DIR` becomes
  `{VINU_MODELS_DIR or data/models}/finbert`; drop the Docker-baked
  `/app/models` path.
- `vinu-news/Dockerfile` — remove the `RUN ... from_pretrained +
  save_pretrained` bake step entirely (image slims by ~430MB).
- `vinu-initial-analysis/angles/chronos/compute.py` —
  `ChronosPipeline.from_pretrained(local_dir, local_files_only=True)` with
  fallback to HF only if truly absent.
- `vinu-initial-analysis/angles/timesfm/compute.py` — same pattern for the
  TimesFM checkpoint.
- Proxy angles stay as-is unless real weights can actually be loaded
  (Moirai/MOMENT weights are downloadable, but their packages still have
  torch/Python-3.12 issues — keep proxies, fetch weights only as a follow-up).

## 4. Docker wiring (read-only at serve time)

- `vinu-components/docker-compose.yml` — mount `./data/models:/models:ro`
  into `news-api` and `initial-analysis-api`.
- Add `VINU_MODELS_DIR=/models` to both services' env.
- Runtime stays offline; no tmpfs wipe → no re-download on restart (fixes the
  current ~1.4GB-per-restart bug on initial-analysis).

## 5. Verification

- Run `download_models.py`, confirm all fetchable weights land in
  `data/models/`.
- Run vinu-news (122 tests) + vinu-initial-analysis (194 + 11 pre-existing):
  FinBERT/Chronos/TimesFM tests should show `model_backend="pretrained"`
  without network (pointed at the local dir).
- Confirm images build without the bake step and containers serve without
  network access.

## Honest limits — what "all models" means

| Downloadable weights | No public weights |
|---|---|
| FinBERT, Chronos-T5-tiny, TimesFM-200m, Moirai, MOMENT, Lag-Llama, Timer/TimerXL, Kronos | TimeGPT (paid API), PatchFormer, FinCast, FinMamba |

Note: Kronos (`NeoQuasar/Kronos-base`) *was* originally marked "no package" —
but its HuggingFace weights exist (1.4M+ downloads); it's only the loader
(github.com/shiyu-coder/Kronos) that isn't pip-installable. Weights are now
downloaded; loading them still needs the repo's custom model code (follow-up).

For the "no public weights" column the command reports "no downloadable
weights" and leaves the existing proxy fallback in place — never faked, still
honestly labeled `model_backend="fallback_proxy"`.

## Open question

Should Moirai/MOMENT/Lag-Llama/TimerXL weight downloads be in this pass
(they need real package work to load the weights), or keep this pass to the
3 models that actually load today (FinBERT, Chronos, TimesFM) and just prep
the folder for the rest?

## Implementation status (2026-08-06)

**Done — the 3 models that actually load today now run from the shared dir:**

- `vinu-infra/models.py` — new module: `MODELS` registry, `models_dir()`
  (`$VINU_MODELS_DIR` else `<components>/data/models`), `ensure_model()`
  (auto-download if absent, idempotent), `download_models()`, plus a
  `vinu-models` CLI entry point (`--list`, `--model`, `--dir`).
- `vinu-infra/pyproject.toml` — new `models` extra (`huggingface_hub`) and
  `vinu-models` console script.
- `vinu-infra/tests/test_models.py` — 5 tests (env override, default root,
  unknown model, idempotent short-circuit). All green.
- `vinu-news/.../finbert_sentiment.py` — `MODEL_DIR` replaced with
  `_model_dir()` → `model_path("finbert")`; loads local-first, auto-downloads
  via `ensure_model` only if missing.
- `vinu-news/Dockerfile` — FinBERT bake step (the old `RUN ... save_pretrained`
  block) **removed**; now installs `vinu-infra[models]`.
- `chronos/compute.py` / `timesfm/compute.py` — `from_pretrained(
  <local dir>)` via `ensure_model`, local-first, auto-download fallback.
- `vinu-components/docker-compose.yml` — `./data/models:/models:ro` mounted
  into `news-api` and `initial-analysis-api`; `VINU_MODELS_DIR=/models` set.
- `Makefile` — `make models` (install extra + download all), `make models-list`.
- `.gitignore` — `data/models/` ignored.
- Downloads: `finbert`, `chronos-t5-tiny`, `timesfm-2.5-200m-pytorch`,
  `moirai`, `moment`, `lag-llama`, `timer-timerxl`, `kronos` all present in
  `data/models/`.

**Verified:** vinu-news 122/122; vinu-initial-analysis 194 + 11 pre-existing
`bar_ts` failures (unchanged); vinu-infra 68 + 5 new model tests. FinBERT
smoke test scores "Apple beats earnings estimates" → positive/0.457 from the
shared local dir.

**Wired since — 2 more angles now run real pretrained weights (2026-08-06):**

- `timer_timerxl/compute.py` — loads `thuml/timer-base-84m` from the shared
  dir via `ensure_model` + `AutoModelForCausalLM.from_pretrained(...,
  trust_remote_code=True)`. Inference uses a single `forward` pass
  (`use_cache=False`, `max_output_length=5`, `revin=True`) on log-transformed
  prices truncated to a multiple of the 96-point patch — NOT `generate()`,
  because the vendored `TSGenerationMixin` (written for transformers 4.40.x)
  calls removed transformers 5.x APIs (`DynamicCache.from_legacy_cache`,
  `DynamicCache.seen_tokens`). Deterministic point forecast; p10/p90 bands
  come from residual-normal log-return spread around the model output.
  `model_backend: pretrained`, checkpoint `thuml/timer-base-84m`. Tests
  updated: 5 passed (sub-patch fallback + real-model integration).
- `kronos/compute.py` — loads `NeoQuasar/Kronos-base` + companion tokenizer
  `NeoQuasar/Kronos-Tokenizer-base` (new `kronos-tokenizer` registry entry)
  from the shared dir. The custom model code is **vendored** (MIT license,
  upstream github.com/shiyu-coder/Kronos) into
  `angles/kronos/_kronos_model/` (`module.py`, `kronos.py`, `__init__.py` —
  only the import plumbing adjusted) since the repo is not pip-installable.
  Uses upstream `KronosPredictor.predict(...)` for a 5-step OHLC forecast
  (T=0.8, top_p=0.9, sample_count=3 averaged). `model_backend: pretrained`,
  checkpoint `NeoQuasar/Kronos-base`. Tests updated: 5 passed. spec.yaml
  updated to drop the "(fallback proxy)" title.

**Deferred by decision — 3 models stay on honest `fallback_proxy` (2026-08-06):**

User decision: keep proxies and document the exact env blockers rather than
risk the shared environment. Weights for all three ARE downloaded into
`data/models/` (via `make models`), so the folder is prepped and any later
pass can wire them without re-downloading:

- `lag_llama` — needs `gluonts[torch]<=0.14.4` from the research repo's
  requirements (github.com/time-series-foundation-models/lag-llama), which
  would **downgrade pandas 3.0.3 → 2.3.3** in the shared env, plus
  pytorch-lightning/torchmetrics, plus vendoring the repo's `lag_llama/`,
  `gluon_utils/`, `utils/` model code. Loader is a ckpt (`lag-llama.ckpt`),
  not a pip package.
- `moirai` — needs `uni2ts` (the Salesforce package that can actually load
  `Salesforce/moirai-1.0-R-small`); `pip install --dry-run uni2ts` showed it
  would **downgrade torch 2.13.0+cpu → 2.4.1** (plus jax/jaxlib/
  pytorch-lightning/tensorboard). Downgrading torch would risk the 5 now-wired
  pretrained loaders (finbert, chronos, timesfm, timer, kronos).
- `moment` — needs `momentfm`, whose pip build **fails on Python 3.12**
  (`pkgutil.ImpImporter` removal); the shared env is Python 3.12.

All three loaders keep `model_backend: "fallback_proxy"` with
`fallback_reason` stating the exact blocker, so nothing is silently fake.
