# The analyst interface — how all 6 analysts actually run

Companion to `01-table-schemas.md` (same folder) — that doc covers what
gets stored; this one covers the code shape that produces it. See also
`03-severity-and-trend.md` (same folder) for how `severity` and `trend`
actually get computed — neither is hand-set by the analyst.

---

## The `Finding` dataclass

Mirrors `reflection_findings_history`'s columns, plus one field
(`primary_metric`) that exists only to feed the shared `trend`
computation — see `03-severity-and-trend.md`:

```python
@dataclass
class Finding:
    analyst_name: str
    cluster: str
    scope_type: str   # system | ticker | ticker_pair | strategy_family | angle
    scope_key: str
    signal_json: dict
    evidence_count: int
    primary_metric: float   # the one number this analysis tracks (e.g. this
                             # cycle's brier_trend for A) — used only to derive
                             # `trend` generically at write time, never stored
                             # as its own column
    narrative: str | None = None
```

`finding_id`, `computed_at`, `severity`, and `trend` are **not** set by
the analyst — `severity` is derived from the same PSI-distance already
computed for the Condition, and `trend` is derived by diffing
`primary_metric` against the prior belief row, both at write time (see
`03-severity-and-trend.md`). An analyst shouldn't need to know about ID
generation, timestamps, or classification thresholds; it just reports
what it found and the one number that represents it.

Note: `regime` is dropped from `scope_type`'s enum here — none of the
25 scoped analyses in `25-A-Y-details/` ever set it; regime always
appears nested inside `signal_json` (e.g. A's `regime_breakdown`)
rather than as a top-level scope.

## The function every analyst implements

```python
def run(
    data_root_paths: dict[str, Path],
    service_clients: dict[str, ServiceClient],
) -> list[Finding]:
    ...
```

Two params, not one — see "colocated vs. mounted vs. HTTP" below for
why `service_clients` still exists even though most cross-service reads
turn out not to need it. Each of the 6 analyst modules implements this
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

## Colocated vs. shared ticker-profile files vs. HTTP — implemented 2026-09-18

**History, briefly**: this section went through two prior versions.
The first proposed a `service_clients` HTTP abstraction for every
cross-service read. The second (still visible in git history) proposed
mounting each service's SQLite data root into vinu-agent and
pip-installing its package in-process — modeled on
`research_link.py`'s real, proven direct-mount-first/HTTP-fallback
pattern — but excluding `vinu-initial-analysis` alone, since its real
`pyproject.toml` pulls in `torch`/`xgboost`/`chronos-forecasting`/
`timesfm`, making a package install a bad trade for two small reads.

**That second version is now superseded by something simpler that
removes the dependency-weight problem entirely, not just for
`vinu-initial-analysis` but for everyone**: each producing service
writes a small, plain JSON projection of its own per-ticker facts into
a shared folder, namespaced by service key — `read_ticker_profile`/
`write_ticker_profile_key` in `vinu-infra/ticker_profile.py` (built and
tested, 12 tests, all passing). Any reader opens plain JSON — no ORM,
no package import, no dependency weight at all, regardless of how heavy
the *producing* service's own stack is. This closes the
`vinu-initial-analysis` problem completely rather than just excluding
it, and it's cheaper than the mount-and-import plan for the other 4
services too (no new pip dependency needed by vinu-agent at all).

**Implemented, all 3 producers wired, ships inert**:
- `vinu-stock-price`: `backfill/year_job.py`'s `run_year_job()` writes
  `gap_count`/`has_adj_data`/`provider`/`archive_through` right after
  its existing `catalog.upsert_symbol()` call.
- `vinu-initial-analysis`: `storage/orchestration_registry.py`'s
  `_persist_result_and_write_factsheet()` writes each angle's
  `timeframe`/`tier`/`run_id`/`row_count`, nested under `angles.<name>`,
  right after its existing `write_factsheet()` call — merges with prior
  angles for the same symbol rather than overwriting them. **Caveat**:
  this hook has no live production caller today (`run_batch_with_parallel_harness`
  is only exercised by its own tests currently) — wired ready for when
  it is, verified only by `py_compile` in this environment since
  `torch` isn't installed here to run the real test suite.
- `vinu-screener`: `rankers/churn.py`'s `record_ranking()` writes
  `ranker_id`/`final_score`/`risk_flags`/`rank_percentile` per symbol in
  the current top-N, right after `snapshot_store.set_latest()`.
- `vinu-live`: `book/positions.py`'s `open_position()`/`add_to_position()`/
  `reduce_position()`/`close_position()` each write
  `side`/`qty`/`avg_entry`/`realized_pnl`/`stop_loss`/`take_profit`/
  `is_open` at their natural return point. Genuinely additive, not
  redundant with Round 2's `already_held` feature — vinu-agent's broker
  `Position` is a live Alpaca snapshot; vinu-live's book is a separate,
  richer, persisted lifecycle record (stop_loss/take_profit levels,
  realized P&L, links to the originating trade plan). **Different
  wiring shape on purpose**: this module has no existing config-DI
  chain reaching its write functions (unlike the other 3 producers), so
  `shared_root` is resolved directly from `VINU_SHARED_ROOT` inside
  `positions.py` itself (same convention `vinu-infra/calibration_log.py`
  already uses) rather than threaded through `orchestrator.py`'s several
  call sites — deliberately lower-touch for a live-trading module, no
  change to any function signature anything else calls.
- `vinu-portfolio`: `service.py`'s `compute_daily_allocation()` writes
  `target_weight`/`base_weight`/`regime_multiplier`/`outcome_multiplier`
  per symbol, right after its existing `record_daily_allocation()` call
  — the per-symbol weight data lives inline in this method (`tilted`),
  not in `AllocationHistoryStore` itself (confirmed: that store is
  portfolio-wide/daily, doesn't fit this mechanism at all). Symbol key
  falls back to strategy name when a weight row has no real ticker
  symbol, matching a convention this same method already used one block
  above (`w.get("symbol") or w.get("name", "")`) — not a new rule
  invented for this. New `PortfolioConfig.shared_root` field
  (`VINU_SHARED_ROOT`), same DI pattern as every other config field in
  that dataclass, unlike vinu-live's env-resolved approach above — this
  service already had a config object reaching the hook point.

All gated on a new `shared_root`/`VINU_SHARED_ROOT`, defaulting to
`None`/unset — unset means every write is a silent no-op, confirmed by
each producer's existing test suite staying green unchanged (104/104
vinu-stock-price, 436/436 vinu-screener, 436/436 vinu-live, 209/209
vinu-portfolio — 2, 2, 5, and 4 new tests added respectively, on top of
each package's original suite). `docker-compose.yml`'s `/shared` mount,
previously only on `news-api`/`stock-api`, is now on all 6
producer/consumer services (`agent-api`, `research-api`, `live-api`,
`portfolio-api`, `screener-api`, `initial-analysis-api`). **All 5
identified per-ticker producers are now wired** — `vinu-initial-analysis`
remains the one with unresolved live-runner verification (see caveat
above, unrelated to whether the hook is correct).

**What this does and doesn't cover**: current-state-per-ticker facts —
`symbol_catalog`, `WeightsStore`, fact sheets, ranker output — all fit.
Event-stream/history data that's genuinely about the past, not current
state (`RebalanceRequestQueue`'s pending-request queue, full
`RankerChurnStore` history, pairwise facts like `CorrelationMonitorStore`/
`AllocationHistoryStore`) doesn't fit a per-ticker snapshot file — those
still need either a "latest N" projection into the same namespaced key
(cheap, same mechanism) or a real HTTP call for full history on demand
(rare, already served by each service's own existing API). No
`service_clients` abstraction has been built, and per this mechanism's
coverage, none may be needed before Forecast Intelligence or
Governance & Freshness are built — reassess only if one of those needs
genuine full-history data this mechanism's "latest N" projection can't
approximate well enough.

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
                write_findings(findings)  # classify_severity() + trend-diff
                                           # against prior reflection_beliefs
                                           # row per finding, THEN upsert_many
                                           # into both tables — see
                                           # severity-and-trend.md
            except Exception:
                logger.exception(f"[reflection-worker] {analyst_fn.__module__} failed, skipping")
        time.sleep(interval)
```

**Failure isolation (`05-to-do.md` #7) is structural, not just the
try/except habit**: each analyst is a standalone pure function with no
shared state between them, so one analyst throwing can't corrupt
another's computation even before the try/except is added — the
try/except only stops one failure from skipping the rest of *this
cycle's* run.

## Why this shape, in one line

Reuse what's already proven (`SQLiteBackend`'s `upsert_many`, the real
worker loop, `research_link.py`'s direct-mount-first-HTTP-fallback
pattern, now extended to 4 more lightweight services instead of just
one) instead of inventing anything new — every analyst becomes a pure,
independently testable function, and the framework itself stays to 1
worker, 1 registry list, 1 dataclass.

## Open items before every analyst is buildable — now just one

The shared ticker-profile mechanism (previous section) closes what used
to be two open items here: the mount-and-import extension is done and
verified (2 of 3 producers' test suites green; the 3rd,
`vinu-initial-analysis`, compiles clean but couldn't be test-run in
this environment — see caveat above), and no `service_clients` HTTP
work was needed to get there. What's left:

1. **A real reader** — every producer now writes, but nothing reads
   `data/shared/ticker-profiles/*.json` yet, because the reflection
   worker itself doesn't exist. Not a design gap — this was explicitly
   out of scope for this round (producer-side only, per the plan) —
   just the honest next step once Decision-Process (the actual first
   analyst) is being built and a second analyst needs this data.
