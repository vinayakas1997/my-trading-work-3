"""Analyses P + G -- ingest health and provider fallback vs. forecast
quality, merged into one per-ticker row (the design doc's own "P and G
answer adjacent questions off adjacent tables ... would otherwise double
the per-ticker row count for no added signal" merge). Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-
pattern/25-A-Y-details/01-forecast-intelligence.md ("P", "G").

**Corrects the 2026-09-19 "Blocked" verdict recorded in that file and in
`07-implementation-plan-status.md`**: that verdict rests on the claim that
`calibration.py`'s `add_entry()` "leaves [`CalibrationEntry.timestamp`] at
the dataclass default ('')" and that "no real writer anywhere in the
codebase ever sets it." Checked directly: `add_entry()`
(`vinu-research/vinu_research/calibration.py`) sets
`timestamp=datetime.now(timezone.utc).isoformat()`, and `git blame` shows
that line has been there since 2026-07-27 -- two months before the
"blocked" verdict. It is wired to a real production writer: vinu-live's
`feedback_loop.py` calls `POST /trade-plan/{id}/record-outcome` on every
closed position, which calls `record_realized_outcome()` ->
`CalibrationTracker.add_entry()` -> `append_calibration_entry()`, and
`strategy_store.py`'s `append_calibration_entry`/`_row_to_calibration_entry`
persist/read that column verbatim. The "blocked" verdict was a
documentation error (an incorrect investigation), not a real data gap --
this is the correction, not a new writer.

**Real join used, and why it is not a naive per-entry timestamp match**:
`CalibrationEntry.timestamp` is the trade's *close* time (set when
`record_realized_outcome` is called) -- an ingest gap or provider
fallback that degraded a forecast would have happened near the trade's
*entry*, not its close, so joining on `calibration_entry.timestamp`
directly would silently mis-date every comparison. Joined on
`Artifact.created_at` instead (the real forecast-authoring moment):
each closed position's calibration entries are attributed to the
calendar day its owning artifact was created, and that day (plus a
1-day lag -- a data problem on day D can still degrade a forecast
authored the next morning, before the gap is noticed/backfilled) is
checked against `ingest_log`'s bad-day set (P) and
`provider_fallback_log`'s fallback-day set (G) for that same symbol.

**Scoped down from the design doc's Condition, documented, not silently
dropped**: "`gap_count` itself exceeds this symbol's own trailing P90"
needs a historical *time series* of `gap_count` per symbol; only a
current snapshot lives in `symbol_catalog` (no history table exists for
it anywhere). Only the error-adjusted brier comparison half of P (and
G's fallback-vs-primary equivalent) is implemented; `gap_count` is
still reported in `signal_json` as context, not as its own condition.

Significance uses the same PSI machinery every other analyst in this
service uses (`vinu_infra.reflection.population_stability_index`),
applied to two *labeled* groups (clean-day vs. degraded-day forecasts)
rather than two adjacent time windows -- the right generalization here,
since P/G's real question is "does this symbol's brier_score differ
between clean and degraded days," not "has it drifted over time."
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import vinu_stock
from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)
from vinu_stock.catalog.store import CatalogStore, open_catalog_db

from vinu_agent.broker.research_link import get_strategy_store

# vinu_stock's own `MetaBackend` (storage/backend.py) also wires up
# SettingsStore/WatchlistStore, and SettingsStore's schema init calls
# `vinu_stock.config.load_config()` for its env-default seeding -- which
# requires `VINU_STOCK_DATA_ROOT` to be set, entirely independent of
# whatever `db_path` is actually passed in. This analyst only ever reads
# `symbol_catalog`/`ingest_log`/`provider_fallback_log`, so it opens
# `CatalogStore` directly instead (same construction
# vinu-stock-price's own `tests/test_catalog.py` uses) -- avoids that
# unrelated env-var coupling rather than requiring a second, redundant
# env var just to satisfy a schema this analyst never touches.
_CATALOG_SCHEMA_PATH = Path(vinu_stock.__file__).resolve().parent / "catalog" / "schema.sql"


def _open_catalog(db_path: Path) -> CatalogStore:
    conn = open_catalog_db(db_path)
    store = CatalogStore(conn)
    store.init_schema(_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    return store


ANALYST_NAME = "forecast_intelligence"
CLUSTER = "Forecast Intelligence"
METRIC_NAME = "ingest_brier_delta"

# Minimum-sample floor for each side of a clean-vs-degraded comparison --
# same "don't compare a signal against too few observations to mean
# anything" posture as B's ">=5 real closed trades" / V's ">=5 promoted
# artifacts" floors in 02-regime-risk-coverage.md.
MIN_GROUP = 5
LAG_DAYS = 1
# Same domain-floor exception as A -- brier_score >= 0.5 is no better
# than a coin flip and forces `significant` regardless of PSI.
DOMAIN_FLOOR_BRIER = 0.5


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _date_from_epoch(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _date_from_iso(ts: str) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _tainted_days(day_strs: set[str]) -> set[str]:
    """Each bad day D also taints D+1..D+LAG_DAYS."""
    out: set[str] = set()
    for d in day_strs:
        date = datetime.fromisoformat(d).date()
        for offset in range(LAG_DAYS + 1):
            out.add((date + timedelta(days=offset)).isoformat())
    return out


def _stock_db_path(data_root_paths: dict[str, Path]) -> Optional[Path]:
    """`data_root_paths["vinu_stock"]` must point at a mounted copy of
    vinu-stock-price's own data root (docker-compose.yml mounts
    `./data/stock-price` read-only into this service at `/stock-data`)."""
    raw = data_root_paths.get("vinu_stock")
    if raw is None:
        return None
    return Path(raw) / "vinu_stock_price.db"


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    db_path = _stock_db_path(data_root_paths)
    if db_path is None or not db_path.exists():
        return []

    catalog = _open_catalog(db_path)
    strategy_store = get_strategy_store()

    findings: list[Finding] = []
    for entry in catalog.list_symbols():
        symbol = entry.symbol
        ingest_rows = catalog.list_ingest_log(symbol)
        fallback_rows = catalog.list_recent_fallbacks(symbol)
        if not ingest_rows and not fallback_rows:
            continue

        bad_ingest_days = _tainted_days(
            {_date_from_epoch(r["run_at"]) for r in ingest_rows if not r["ok"]}
        )
        fallback_days = _tainted_days(
            {_date_from_epoch(r["occurred_at"]) for r in fallback_rows}
        )

        clean_briers: list[float] = []
        gap_degraded_briers: list[float] = []
        primary_briers: list[float] = []
        fallback_briers: list[float] = []
        for artifact in strategy_store.list_artifacts_for_symbol(symbol):
            artifact_day = _date_from_iso(artifact.created_at)
            if artifact_day is None:
                continue
            for calib in strategy_store.get_calibration_entries(artifact.artifact_id):
                if artifact_day in bad_ingest_days:
                    gap_degraded_briers.append(calib.brier_score)
                else:
                    clean_briers.append(calib.brier_score)
                if artifact_day in fallback_days:
                    fallback_briers.append(calib.brier_score)
                else:
                    primary_briers.append(calib.brier_score)

        p_computable = len(clean_briers) >= MIN_GROUP and len(gap_degraded_briers) >= MIN_GROUP
        g_computable = len(primary_briers) >= MIN_GROUP and len(fallback_briers) >= MIN_GROUP
        if not p_computable and not g_computable:
            continue

        signal: dict[str, Any] = {
            "gap_count": entry.gap_count,
            "error_rate": (
                sum(1 for r in ingest_rows if not r["ok"]) / len(ingest_rows)
                if ingest_rows else 0.0
            ),
        }

        p_psi, p_delta = 0.0, 0.0
        if p_computable:
            p_delta = _mean(gap_degraded_briers) - _mean(clean_briers)
            p_psi = population_stability_index(clean_briers, gap_degraded_briers)
            signal["brier_delta_vs_clean_periods"] = p_delta

        g_psi, g_delta = 0.0, 0.0
        if g_computable:
            g_delta = _mean(fallback_briers) - _mean(primary_briers)
            g_psi = population_stability_index(primary_briers, fallback_briers)
            signal["fallback_brier_delta"] = g_delta
            signal["fallback_frequency"] = len(fallback_rows) / max(len(ingest_rows), 1)

        # Whichever half actually has evidence drives severity/trend for
        # this merged row -- ties favor P (the base row per the design
        # doc's own merge rule).
        if p_computable and (not g_computable or p_psi >= g_psi):
            primary_metric, psi, worst_group = p_delta, p_psi, gap_degraded_briers
        else:
            primary_metric, psi, worst_group = g_delta, g_psi, fallback_briers

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="ticker",
                scope_key=symbol,
                signal_json=signal,
                evidence_count=len(ingest_rows) + len(fallback_rows),
                primary_metric=primary_metric,
                metric_name=METRIC_NAME,
                psi=psi,
                domain_floor_breached=_mean(worst_group) >= DOMAIN_FLOOR_BRIER,
                narrative=(
                    f"{symbol}: brier delta {primary_metric:+.3f} between clean and "
                    f"degraded-ingest/fallback days (gap_count={entry.gap_count})"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="clean_ingest_days_vs_gap_or_fallback_tainted_days",
        reason=(
            "P/G: a higher brier_score on ingest-degraded/fallback-served "
            "days than on clean/primary-provider days means worse forecasts"
        ),
        updated_by=ANALYST_NAME,
    )
