# vinu-infra

## What it is

Not a running service — a shared library every other service imports.
No cadence of its own; this doc lists what it actually provides and who
consumes each piece, since "internal granularity" here means "which
service-crossing behavior lives in one shared place" rather than a
pipeline.

## What it provides

**`server.py::create_app()`** — the one FastAPI app factory every
service's `server/app.py` calls (confirmed: `vinu-stock-price`,
`vinu-news`, `vinu-initial-analysis`, `vinu-research`, `vinu-screener`,
`vinu-agent`, `vinu-portfolio`, `vinu-simulator` all build on it, not
each rolling their own). What it standardizes across every service at
once:
- `VINU_API_KEY`-gated auth (`auth.py::require_auth`) — opt-in: no key
  set, no auth wrapper added at all. When set, every route under the
  main router requires it — this is the exact mechanism that caused the
  real pre-deployment bug found while shipping `vinu-screener`
  (B20's pairlist route had its own separate default token, which would
  have silently 401'd forever once `VINU_API_KEY` was actually
  configured — fixed by defaulting the pairlist token to `VINU_API_KEY`
  itself).
- CORS, opt-in via `VINU_CORS_ORIGINS`.
- NaN-safe JSON responses (`_NanSafeJSONResponse`) — a stray `NaN` from a
  numpy computation doesn't produce invalid JSON that breaks every
  caller's parser.
- `expose_health_on_root` — a consistent `/health` across every service.

**`runtime_settings.py::RuntimeSettings`** — the live-patchable settings
mechanism (`GET/PATCH /admin/settings`) used by multiple services for
knobs an operator needs to change without a restart (poll intervals,
thresholds). `build_admin_settings_router(..., on_change=...)` lets a
service audit-log every change — `vinu-agent` wires its own
`AuditLogger` in here. `_Knob`'s `category`/`type_name` metadata (added
during Stage C) is what backs `GET /admin/settings/schema` — the
single source of truth for what each knob means and what type it is,
not duplicated per-service documentation.

**`calibration_log.py`** (added this session's reasoning audit) —
`record()`/`read_all()`, a plain append-only JSONL observation log. Not
a decision store — nothing reads it back to decide anything at runtime.
Exists purely so genuinely-arbitrary threshold decisions (`vinu-live`'s
`bracket_partial`/`rebalance_protect` checkpoints) leave a record of what
was decided and why, checkable later against what actually happened.
Callers gate writes on a real, confirmed broker connection
(`_broker_account_configured`) so synthetic/test runs never pollute the
sample.

**`secrets_loader.py`** — `load_secret(name, env_var)` reads Docker
secrets (`/run/secrets/{name}` in the deployed container) first, falls
back to the legacy env var for local dev. This is how `vinu-agent`'s
`AlpacaBroker` and `vinu-news`'s/`vinu-initial-analysis`'s API keys
actually resolve — never a hardcoded path, never assumes one mechanism
over the other.

**`llm/client.py::LlmClient`** (+ `client_async.py`) — the shared LLM
call wrapper: `_log_llm_call` (every LLM call logged, cost tracked via
`llm/cost.py`), `_parse_json_content` (tolerant JSON extraction from a
chat completion, the same "fails soft to a safe default on unparseable
output" posture used throughout `vinu-research`'s forecast generation
and `vinu-agent`'s team verdicts), `llm/cache.py` (response caching),
`llm/providers.py` (provider abstraction).

**`security/`** — `network.py` (egress restrictions), `scanner.py` (a
static scan, likely CI-facing rather than runtime).

**`debug.py::sync_timer`** — the timing context manager
`vinu-initial-analysis`'s `AngleRunner` wraps each of the 28 angles in
(`with sync_timer(f"angle.{angle['name']}")`) — one shared
instrumentation mechanism, not each angle timing itself independently.

**`db.py`/`sqlite.py`/`parquet.py`** — shared storage primitives
(connection handling, schema helpers) most services' own `storage/`
modules build on rather than reimplementing SQLite/parquet boilerplate
per service.

## Talks to

Nothing external — pure shared library, imported in-process by every
other Vina service. No HTTP surface of its own beyond what
`create_app()` scaffolds for whoever calls it.
