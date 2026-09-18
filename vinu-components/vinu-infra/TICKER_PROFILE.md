# Ticker profile files — one reference

The single reference for the shared per-ticker JSON mechanism: where the
data lives, what's in it, how to read/write it, and — just as
important — what it deliberately does **not** cover. Built 2026-09-18.

## What it is, in one line

One JSON file per ticker, written by every service that knows something
about that ticker, each service owning exactly one key in the file —
so any reader gets every service's facts about one symbol from a single
plain file, no database, no cross-service package import, no HTTP call.

## Where it lives

```
<shared_root>/ticker-profiles/<SYMBOL>.json
<shared_root>/ticker-profiles/<SYMBOL>.json.lock   (sidecar lock file, filelock)
```

`shared_root` is `VINU_SHARED_ROOT`, resolved per-service (see "Where
it's wired in" below) — in Docker Compose this is the `/shared` mount
(`./data/shared` on the host), the same volume `watchlist.json` already
uses. Empty/unset anywhere in the chain means **every write is a silent
no-op** — nothing breaks, nothing is written, by design (see
`vinu_infra/ticker_profile.py`'s own docstring).

## Relationship to the 55-store catalog

This is **not** one of the 55 stores catalogued in
`project-understanding/05-full-recorded-information/README.md`, and it
never duplicates their role as the real source of truth — every field
written here is also, separately, durably recorded in whichever of
those 55 stores actually owns it (`symbol_catalog`, `WeightsStore`,
`RankedSnapshotStore`, the position book, `AllocationHistoryStore`,
etc). This is a **derived, best-effort projection** across 5 of those
stores, purely for cheap same-symbol reads — if this file is ever lost,
corrupted, or simply never written (the ships-inert default), nothing
about the real system's correctness changes; only cross-service lookups
that would otherwise need 5 separate calls get slower.

## What's actually in one file, right now

```json
{
  "symbol": "AAPL",
  "vinu_stock_price": {
    "provider": "alpaca", "archive_through": 2026, "has_adj_data": true,
    "gap_count": 0, "updated_at": 1758198000.0
  },
  "vinu_initial_analysis": {
    "angles": {
      "dlinear": {"timeframe": "1D", "tier": "tier2", "run_id": "a1b2c3", "row_count": 480}
    },
    "updated_at": 1758198000.0
  },
  "vinu_screener": {
    "ranker_id": "core_starter", "final_score": 4.82,
    "risk_flags": [], "rank_percentile": 0.95, "updated_at": 1758198000.0
  },
  "vinu_live": {
    "position_id": "AAPL-20260918", "side": "long", "qty": 100,
    "avg_entry": 150.0, "realized_pnl": 0.0, "stop_loss": 142.5,
    "take_profit": null, "is_open": true, "updated_at": 1758198000.0
  },
  "vinu_portfolio": {
    "target_weight": 0.12, "base_weight": 0.10,
    "regime_multiplier": 1.15, "outcome_multiplier": 1.05,
    "updated_at": 1758198000.0
  }
}
```

Every namespaced key gets `updated_at` (a Unix timestamp) added
automatically by `write_ticker_profile_key` — not something a caller
sets itself. A ticker with only some services having ever written to it
simply has only those keys present; a missing key means "this service
has never recorded anything for this ticker," not an error.

## How to read it

```python
from vinu_infra.ticker_profile import read_ticker_profile

profile = read_ticker_profile(shared_root, "AAPL")
# {} if the file doesn't exist, shared_root is None, or the JSON is
# corrupt -- never raises.
screener_data = profile.get("vinu_screener", {})
```

## How to write to it

```python
from vinu_infra.ticker_profile import write_ticker_profile_key

write_ticker_profile_key(
    shared_root, "AAPL", "your_service_name",
    {"some_field": 123, "another_field": "value"},
)
```

**The one contract every writer must follow**: this replaces your
service's key *wholesale* — it does not merge inside it. If your data
has sub-items that accumulate over time (like `vinu_initial_analysis`'s
per-angle results), read your own current key first, merge in your
update, and pass the merged dict:

```python
existing = read_ticker_profile(shared_root, symbol).get("your_service_name", {})
write_ticker_profile_key(shared_root, symbol, "your_service_name", {**existing, "new_field": ...})
```

Best-effort throughout: a write failure (missing/unwritable
`shared_root`, a lock timeout, a non-serializable value) is swallowed,
never raised — a ticker-profile write must never be able to break the
real work that triggered it.

## What this deliberately does NOT cover

**Not history, not date-indexed — current state only.** Every key holds
whatever that service's *latest* write was; there is no way to ask
"what was AAPL's `vinu_screener` rank_percentile on 2026-09-10." If you
need that, go to the owning store directly (`RankedSnapshotStore`'s own
history, `RankerChurnStore`, `trade_score_calibration_history`, etc.) —
this file only ever answers "right now, as of the last write."

**Not pairwise or portfolio-wide facts.** Checked directly, doesn't fit:
`CorrelationMonitorStore` (a fact about *two* tickers), the daily total
in `AllocationHistoryStore` (a fact about the *whole* portfolio), full
`RankerChurnStore` history (an event log, not a snapshot). Those stay in
their own real stores; nothing here replaces them.

**Not authoritative for anything.** See "Relationship to the 55-store
catalog" above — always a projection, never the source of truth.

## Where it's wired in, today

| Service | File | Function | Env var read |
|---|---|---|---|
| vinu-stock-price | `backfill/year_job.py` | `run_year_job()` | `VINU_SHARED_ROOT` (via `VinuStockConfig.shared_root`) |
| vinu-initial-analysis | `storage/orchestration_registry.py` | `_persist_result_and_write_factsheet()` (via `run_batch_with_parallel_harness()`) | passed as `shared_root` param — no live caller yet, see caveat below |
| vinu-screener | `rankers/churn.py` | `record_ranking()` | `VINU_SHARED_ROOT` (via `server/app.py`'s `DEFAULT_SHARED_ROOT`) |
| vinu-live | `book/positions.py` | `open_position()` / `add_to_position()` / `reduce_position()` / `close_position()` | `VINU_SHARED_ROOT`, resolved directly inside the module (no config-DI chain existed here) |
| vinu-portfolio | `service.py` | `compute_daily_allocation()` | `VINU_SHARED_ROOT` (via `PortfolioConfig.shared_root`) |

**Caveat on vinu-initial-analysis**: `run_batch_with_parallel_harness`
has no live production caller today (only its own tests exercise it) —
wired and ready, but unverified against a real end-to-end run, and this
sandbox has no `torch` installed to run its test suite at all (a
pre-existing environment limitation, confirmed unrelated to this
change).

`docker-compose.yml`'s `/shared` mount covers all 5 producers above
plus `vinu-agent` and `vinu-research` (the two intended readers, though
no reader is built yet) and the two services that already had it
before this (`vinu-news`, `vinu-stock-price`).

## Tests

`vinu-infra/tests/test_ticker_profile.py` — the mechanism itself (12
tests: round-trip, cross-service merge, corrupt-file/missing-root
best-effort behavior, lock-file creation). Each producer's own test
suite additionally covers its specific write (2 in vinu-stock-price's
`tests/test_year_job.py`, 2 in vinu-screener's `tests/test_ranker_churn.py`,
5 in vinu-live's `tests/test_book_ticker_profile.py`, 4 in
vinu-portfolio's `tests/test_service.py`).
