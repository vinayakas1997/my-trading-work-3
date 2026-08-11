# Open Gaps — Still Needs To Be Fixed

Tracked against the 5 known gaps documented in `architecture.md` §8, plus any newly discovered issues found during full-project testing.

## Known Gaps (from architecture.md §8)

### 1. Research artifact auto-promotion missing
- `/research/runs/{id}/approve` endpoint exists and works, but **nothing calls it**.
- Result: research artifacts are never automatically promoted for downstream use.
- **Workaround during E2E:** call the approve endpoint directly via HTTP.

### 2. Order `pending_confirmation` dead-end
- `require_confirmation` defaults to `True`, but **no confirm endpoint or tool exists**.
- Result: any order submitted without confirmation support is a dead-end.
- **Workaround during E2E:** set `require_confirmation: false` (safe in Alpaca paper mode).

### 3. Strategy registry drift
- `meta.db` is synced from strategy YAML files **one-way at startup**.
- Stale rows are **never deleted**.
- Result: removed strategies linger in the registry.

### 4. Two broken fallback URLs (missing route prefix)
- `vinu-agent/vinu_agent/tools/portfolio_comparison_tool.py` — `_fetch_portfolio` / `_fetch_artifacts` fallback URLs lack the correct route prefix.
- `vinu-agent/vinu_agent/memory/sync_service.py` — has **zero callers** (dead code).

### 5. Simulator backtest `run_id` discarded
- `run_id` (uuid4) is generated in the simulator backtest then **discarded**.
- Result: backtest runs cannot be traced/audited by run id.

## Fixed Already (no longer open)
- **stock-api persisted `data_root` bug** — `vinu_stock_price.db` vinu_settings row held a Windows host path; `StockService` read the DB instead of env → candles returned 0 rows. Fixed via Option A (env is source of truth). `vinu-stock-price/vinu_stock/service.py`.
- **features-api missing `4h` interval** — `_interval_seconds()` in `vinu-tools/vinu_tools/engine/engine.py` only mapped 1m/5m/15m/1h/1d. Added `"4h": 4 * 3600`. All other services already supported 4h.
- **initial-analysis timer_timerxl real model never loaded** — `.env` leaks Windows `HOME=C:Usersvinay` into the container; `trust_remote_code=True` writes remote code to a nonexistent path on read-only rootfs → `OSError(30, 'Read-only file system')` → silent `fallback_proxy`. Fixed via `HF_HOME: /home/app/.cache/huggingface` in `docker-compose.yml`. Follow-up: remove the HOME leak from `.env` at the source.
- **initial-analysis resource cap** — `cpus: 1 / mem_limit: 1g` was too small for chronos-t5-large (~2.8GB fp32). Raised to `cpus: 4 / mem_limit: 8g` in `docker-compose.yml`.

## To Verify During Testing (potential new gaps)
- Features engine filters rows to the requested window **before** computing indicators → indicators are null for windows shorter than the indicator warmup. Confirm whether warmup bars should be kept for computation.
- `values: {}` in earlier features responses — confirm resolved now that stock candles return rows.
- Container `/data/strategy/strategies` directory is empty (registry loads from the package dir) — confirm this matches the ARCH doc behavior and does not break strategy evaluation in containers.

## Status
_Update as tests run — mark each gap REPRODUCED / PARTIAL / FIXED._
