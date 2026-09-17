# The analyst interface — how all 6 analysts actually run

Companion to `table-schemas.md` (same folder) — that doc covers what
gets stored; this one covers the code shape that produces it.

---

## The `Finding` dataclass

Mirrors `reflection_findings_history`'s columns exactly, so there's no
translation layer between "what an analyst returns" and "what gets
written to disk":

```python
@dataclass
class Finding:
    analyst_name: str
    cluster: str
    scope_type: str   # system | ticker | ticker_pair | regime | strategy_family | angle
    scope_key: str
    signal_json: dict
    evidence_count: int
    severity: str      # routine | notable | significant
    narrative: str | None = None
```

`finding_id` and `computed_at` are **not** set by the analyst — the
framework fills those in at write time. An analyst shouldn't need to
know about ID generation or timestamps; it just reports what it found.

## The function every analyst implements

```python
def run(
    data_root_paths: dict[str, Path],
    service_clients: dict[str, ServiceClient],
) -> list[Finding]:
    ...
```

Two params, not one — see "colocated vs. HTTP" below for why
`service_clients` exists. Each of the 6 analyst modules implements this
same function name, so the registry is just a list of callables:

```python
ANALYSTS: list[Callable] = [
    forecast_intelligence.run,
    regime_risk_coverage.run,
    execution_money_flow.run,
    decision_process.run,
    governance_freshness.run,
    external_signal_cross_check.run,
]
```

Adding a 7th analyst later is a one-line addition to this list, not a
framework change.

## Colocated vs. HTTP — grounded in the real `docker-compose.yml` mounts

Checked directly against the real compose file, not assumed.
`vinu-agent`'s container (where this worker lives, per `to-do.md` #5)
mounts:

- `./data/agent:/data` — its own data root
- `./data/research:/research-data` — **vinu-research's** data root, also mounted

Nothing else. `vinu-live`, `vinu-portfolio`, `vinu-screener`,
`vinu-stock-price`, `vinu-initial-analysis` are all separate containers
with their own, unmounted data roots. So an analyst can only open a
file directly if it lives in `vinu-agent`'s or `vinu-research`'s data
root — anything else needs an HTTP call to that service's API, the
same pattern `vinu-portfolio/research_link.py` already uses to read
`vinu-research`'s strategy store cross-service.

**Per-cluster breakdown, real stores checked against real mounts:**

| Cluster | Colocated (direct file access) | Needs HTTP |
|---|---|---|
| Forecast Intelligence | `angle_calibration_entries`, `decay_snapshots` (vinu-research); `ticker_summaries` (vinu-agent) | `WeightsStore`, fact sheets (vinu-initial-analysis); `symbol_catalog`, `backfill_runs`, `ingest_log`, `provider_fallback_log` (vinu-stock-price) |
| Regime & Risk Coverage | `artifacts`, `bench_history`, `decay_snapshots` (vinu-research); `paper_performance`, `safety_ledger.jsonl` (vinu-agent) | `CorrelationMonitorStore` (vinu-live); `AllocationHistoryStore` (vinu-portfolio); `shock_*` angle files, OHLCV bars (vinu-initial-analysis/vinu-stock-price) |
| Execution & Money-Flow | — | `RebalanceRequestQueue` (vinu-live); `events`/`events_meta` (vinu-stock-price); `trade_audit_log.jsonl`'s exact mount needs re-checking against `VINU_DATA_ROOT` at build time |
| **Decision-Process** | `llm_calls`, `telemetry.db`, Session/Attempt store, `memory_entries`, `facts`, Swarm runs, `team_runs` — **all vinu-agent** | **none** |
| Governance & Freshness | `symbol_limits`/`symbol_overrides`/`daily_limits`, `significance_flags`, `trade_audit.log` (vinu-agent) | `runs`/RunLog (vinu-initial-analysis); `calibration_log.jsonl`'s exact mount needs re-checking |
| External-Signal Cross-Check | `ticker_ledger`, `TickerSummaryStore` (vinu-agent) | `RankedSnapshotStore`, `RankerChurnStore`, `WatchAuditStore` (vinu-screener); LESSON snapshots (vinu-live) |

**This is independent confirmation that Decision-Process is the right
starting analyst** — not only because `llm_calls.db`/`telemetry.db` are
zero-reader stores (the original reason), but because it's the **only**
one of the 6 clusters needing zero HTTP calls at all. Every other
cluster needs `service_clients` wired up before it can run for real;
Decision-Process doesn't.

## The worker loop

Copies `skill_audit_worker_main`'s real shape from `vinu-agent/vinu_agent/cli.py`
verbatim — same `resolve_worker_interval(...)` → `while True: cycle(); sleep()`
pattern every other worker already uses, so existing ops tooling (logs,
cadence config, restart behavior) works on this one unchanged:

```python
def reflection_worker_main(args: argparse.Namespace) -> None:
    config = load_config()
    interval = resolve_worker_interval(args, config, "reflection_worker_interval_sec")
    print(f"[reflection-worker] Starting (interval={interval}s)")
    while True:
        for analyst_fn in ANALYSTS:
            try:
                findings = analyst_fn(data_root_paths, service_clients)
                write_findings(findings)  # upsert_many into both tables
            except Exception:
                logger.exception(f"[reflection-worker] {analyst_fn.__module__} failed, skipping")
        time.sleep(interval)
```

**Failure isolation (`to-do.md` #7) is structural, not just the
try/except habit**: each analyst is a standalone pure function with no
shared state between them, so one analyst throwing can't corrupt
another's computation even before the try/except is added — the
try/except only stops one failure from skipping the rest of *this
cycle's* run.

## Why this shape, in one line

Reuse what's already proven (`SQLiteBackend`'s `upsert_many`, the real
worker loop, `research_link.py`'s colocated-vs-HTTP pattern) instead of
inventing anything new — every analyst becomes a pure, independently
testable function, and the framework itself stays to 1 worker, 1
registry list, 1 dataclass.

## Open item before this is buildable

`service_clients`' exact shape (what a `ServiceClient` looks like, how
auth — `VINU_API_KEY` `Authorization: Bearer`, same as every other
route — gets threaded through) isn't designed yet. Needed before any
analyst outside Decision-Process can actually run.
