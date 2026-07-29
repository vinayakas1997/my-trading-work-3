# End-to-end pipeline run — status log (run 1)

Goal: run the analysis pipeline (`vinu-stock-price → vinu-news → vinu-tools →
vinu-initial-analysis → vinu-strategy → vinu-simulator → vinu-research`) against
the live `docker-compose` services and record per-step duration, memory, and LLM
call data via a new `vinu-components/run_pipeline.py` orchestrator. Deliberately
stops before `vinu-portfolio`/`vinu-agent`/`vinu-live` (no broker involved).

Last updated: 2026-07-21, mid-run (see §4 for current live status).

---

## 1. Bugs found, and their fix status

### 1.1 — FIXED PERMANENTLY: missing `.env` files blocked `docker compose up` entirely
`vinu-tools`, `vinu-initial-analysis`, `vinu-strategy`, `vinu-simulator` only had
`.env.example`, not `.env`. `docker-compose.yml` references `env_file: ./<service>/.env`
for each, so `docker compose up` failed outright with *"env file ... not found"*.
**Fix:** copied each service's `.env.example` → `.env`. Permanent, no follow-up needed.

### 1.2 — FIXED PERMANENTLY: `vinu-research`'s LLM was disabled with no credentials
`vinu-research/.env` didn't exist at all, and `.env.example` has
`VINU_RESEARCH_LLM_ENABLED=false` with no model/URL set — the research
generate/critique/refine loop would run rule-based-only, producing zero LLM calls
to log. **Fix:** created `vinu-research/.env` with
`VINU_RESEARCH_LLM_ENABLED=true`, `VINU_LLM_MODEL=qwen36-35b-vision`,
`VINU_LLM_BASE_URL=http://localhost:7000/v1`, `VINU_LLM_MAX_TOKENS=32000` (values
given by the user). Permanent.

### 1.3 — FIXED PERMANENTLY: real Alpaca keys were being overridden to blank
`docker-compose.yml` sets `ALPACA_API_KEY: ${ALPACA_API_KEY}` /
`ALPACA_API_SECRET: ${ALPACA_API_SECRET}` explicitly for the `news-ingest`
service. Compose's `environment:` block overrides `env_file:`, and since there
was no root-level `vinu-components/.env` for compose's own variable
substitution, both resolved to blank — **silently clobbering** the real keys
that were already correctly set in `vinu-news/.env`. Effect: `news-ingest`'s
Alpaca ticker-news provider was never "configured" (and Yahoo is disabled in
`ticker_news.yaml`), so ticker-news fetching for a newly-toggled symbol ran with
**zero active providers** and appeared to hang (see 1.4 for how this surfaced).
**Fix:** created `vinu-components/.env` (repo root, next to `docker-compose.yml`)
with the same real `ALPACA_API_KEY`/`ALPACA_API_SECRET` already in
`vinu-news/.env`, then `docker compose up -d --force-recreate news-ingest news-api`.
Permanent — confirmed via `docker exec ... env` that both containers now see the
real keys.

### 1.4 — FIXED IN `run_pipeline.py`: news step blocked on a redundant, slow call
Once 1.3 was fixed, `POST /backfill/{ticker}/toggle {"enabled":true}` was
observed to **automatically** kick off `news-ingest`'s background historical
Alpaca sweep for that ticker (confirmed in `news-ingest` logs: *"New ticker(s)
added (AAPL); fetching news immediately"* fires right after the toggle, with no
separate trigger needed). The orchestrator's original design *also* called
`POST /backfill/trigger?ticker=<T>` explicitly and waited on it — a second,
redundant call that blocks synchronously on the same multi-minute historical
sweep (each month of Alpaca history takes ~30-45s to fetch), which blew past the
script's original 60s client timeout and looked exactly like a hang.
**Fix (in `run_pipeline.py::step_news`):** dropped the explicit
`/backfill/trigger` call; now just toggles backfill on and polls
`GET /ticker/{symbol}` for up to 180s, proceeding with whatever articles have
arrived rather than waiting on the full historical sweep. This is a fix to our
own orchestrator's logic, not to `vinu-news` itself — `vinu-news`'s behavior
(auto-fetch-on-toggle) is correct and unchanged.

### 1.5 — FIXED IN `run_pipeline.py`: wrong simulator endpoint for a fresh ticker
`POST /simulate` (with just a `strategy_name`) reads **pre-accumulated**
historical weight data — the kind that only exists after a strategy has been
`evaluate`'d daily for weeks/months in production. A ticker that was just
`evaluate`'d once, moments ago, has none, so `/simulate` 422s with
*"No weight data found for strategy '...' in range ..."*.
**Fix (in `run_pipeline.py::step_simulator`):** switched to
`POST /simulate/custom`, which computes weights on the fly for any date range
from an ad-hoc `BaseStrategy` subclass passed as a source-code string. Wrote a
minimal SMA-crossover class mirroring `vinu-strategy`'s built-in `ma_crossover`
(9/21 SMA) so the backtest has a real, working strategy rather than needing to
reuse the YAML-defined one (which isn't in a form `/simulate/custom` accepts).

### 1.6 — NOT FIXED (real bug in `vinu-stock-price`, out of scope): historical date ranges crash the candle query engine
`vinu_stock/query/engine.py::fetch_candles` unconditionally builds a DuckDB SQL
query that does `read_parquet` on **both**
`archive/<year>.parquet` (historical) **and** `live/<year>*.parquet` (recent,
day-partitioned) for every year touched by the requested range. The "live"
partition only exists starting `2025-12-31` (confirmed by listing
`data/stock-price/prices/1m/AAPL/live/`) — for any year before that with no live
files, DuckDB's `read_parquet` throws `IOException: No files found that match
the pattern ".../live/<year>*.parquet"` instead of treating a zero-match glob as
an empty result. This makes **any** candle query (and therefore any backtest)
for a date range before ~2025-12-31 hard-crash with a 500, which is what first
looked like a "no weight data" problem in step 1.5's testing (an original
`--from-date 2024-01-01 --to-date 2024-06-01` run hit exactly this).
**Workaround used for this run:** picked a recent date range
(`2026-04-01` to `2026-07-15`) that falls entirely inside real `live`-partition
coverage, sidestepping the bug rather than fixing it.
**Permanent fix still needed** (not done — belongs to `vinu-stock-price`, a
different service, and wasn't part of what was asked): `fetch_candles` should
check whether a year's `live` glob actually matches any files before including
that pattern in the query (or catch the per-pattern `IOException` and retry
without it), so historical-only date ranges don't crash.

### 1.7 — FIXED IN `run_pipeline.py`: initial-analysis timeout too short (not a bug, just slow)
`POST /run/{ticker}` (25 deterministic angles across multiple timeframes) took
**~8 minutes** in a direct, isolated timing test (`time curl ... /run/AAPL`,
8m6s). The orchestrator's original 180s timeout was simply too optimistic for
real work, not a hang. **Fix:** bumped `step_initial_analysis`'s timeout to 900s.

### 1.8 — NOT FIXED (minor, non-blocking, in `vinu-initial-analysis`): a few angles request unsupported candle intervals
During the 8-minute run, logs showed repeated
`Failed to fetch bars for AAPL at 15min` / `at 1W` —
`stock-api`'s `/candles` endpoint doesn't accept `"15min"` or `"1W"` as valid
`interval` values (422), and those specific angle computations catch the
failure and continue (graceful degradation, confirmed non-fatal — the overall
`/run/{ticker}` call still returns 200). Left as-is: doesn't block anything,
just wastes a few requests per run. Would be worth fixing in
`vinu-initial-analysis`'s angle code (use a supported interval string) if this
becomes a priority later.

### 1.9 — EXPECTED, NOT A BUG: no local LLM server is actually running
Every real LLM call attempt (from `vinu-news`'s article analysis) fails
instantly with `Connection refused` — `http://host.docker.internal:8009`
(news's configured endpoint) and `http://localhost:7000` (research's) have
nothing listening. This is environmental (no local inference server started
yet), not a code problem — and importantly, it confirms the new LLM call
logging instrumentation (`vinu-news/vinu_news/analysis/llm/client.py`,
`vinu-research/vinu_research/llm.py`) is working correctly: every failed attempt
is captured in `data/news/llm_calls.jsonl` / `data/research/llm_calls.jsonl`
with the full error, model, base_url, and duration — exactly what it's supposed
to record, success or failure. **Nothing to fix here** unless/until an actual
local LLM server is started on those ports.

---

## 2. What's permanently fixed vs. what's a workaround

| # | Issue | Status |
|---|---|---|
| 1.1 | Missing `.env` files (4 services) | **Permanent fix** |
| 1.2 | `vinu-research` LLM disabled/unconfigured | **Permanent fix** |
| 1.3 | Alpaca keys blanked by compose env override | **Permanent fix** |
| 1.4 | Redundant blocking news-trigger call | **Permanent fix** (in orchestrator) |
| 1.5 | Wrong simulator endpoint for a fresh ticker | **Permanent fix** (in orchestrator) |
| 1.6 | `vinu-stock-price` crashes on pre-2025-12-31 candle queries | **Workaround only** — real fix belongs in `vinu-stock-price`, not done |
| 1.7 | Initial-analysis timeout too short | **Permanent fix** (in orchestrator) |
| 1.8 | A few angles request unsupported intervals (422, non-fatal) | **Not fixed** — low priority, doesn't block runs |
| 1.9 | No local LLM server listening | **Not a bug** — environmental, needs the user to start one |

---

## 3. Files changed this session

- `vinu-components/.env` — **new** (root, Alpaca keys for compose substitution)
- `vinu-research/.env` — **new** (LLM enabled + credentials)
- `vinu-tools/.env`, `vinu-initial-analysis/.env`, `vinu-strategy/.env`,
  `vinu-simulator/.env` — **new** (copied from `.env.example`)
- `vinu-news/vinu_news/analysis/llm/client.py` — LLM call logging instrumentation
- `vinu-research/vinu_research/llm.py` — LLM call/cache-hit logging instrumentation
- `vinu-components/run_pipeline.py` — **new** orchestrator; fixed 3 times during
  testing (news polling, simulator endpoint, initial-analysis timeout)

---

## 4. Current run status (live)

Run: `AAPL`, `2026-04-01` → `2026-07-15` (recent range, sidesteps bug 1.6).

| Step | Status | Duration | Notes |
|---|---|---|---|
| vinu-stock-price | ✅ ok | 69.4s | |
| vinu-news | ✅ ok | 10.9s | 5 LLM calls logged, all failed (no LLM server — see 1.9) |
| vinu-tools (features) | ✅ ok | 5.8s | |
| vinu-initial-analysis | ⏳ running | (~8 min expected) | in progress as of this update |
| vinu-strategy | not yet reached | — | |
| vinu-simulator | not yet reached | — | |
| vinu-research | not yet reached | — | |

Will update this section once the run completes (or hits another issue).

---

## 5. What's left

- Let the current run finish through `vinu-strategy` → `vinu-simulator` →
  `vinu-research` and confirm all 7 steps go green in one clean pass.
- Decide whether bug 1.6 (`vinu-stock-price` historical-range crash) is worth
  fixing properly, since right now historical backtests (e.g. actual 2024 data)
  are simply unusable — only recent/live-partition-covered ranges work.
- Optionally fix 1.8 (unsupported interval strings in a couple of angles) —
  cosmetic/log-noise only, not blocking.
- If real LLM analysis output is wanted (not just connection-refused logging),
  an actual inference server needs to be running on the configured ports
  (`8009` for news, `7000` for research).
