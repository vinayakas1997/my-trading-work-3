from __future__ import annotations

import importlib
import inspect
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from vinu_initial_analysis.storage.parquet import AngleStorage
from vinu_initial_analysis.storage.meta import RunLog
from vinu_infra.debug import sync_timer

LOG = logging.getLogger(__name__)

ANGLES_DIR = Path(__file__).resolve().parent / "angles"
DEFAULT_TIME_FORMATS = ["1D"]

JSON_MIME = "application/json"


class AngleRunner:
    """Discovers angles/ folder and runs each available angle's compute()."""

    def __init__(
        self,
        storage: AngleStorage,
        run_log: RunLog,
        news_client: Any = None,
        price_client: Any = None,
    ) -> None:
        self._storage = storage
        self._run_log = run_log
        self._news_client = news_client
        self._price_client = price_client
        self._angles: list[dict[str, Any]] = []
        self._bar_cache: dict[tuple[str, str], pd.DataFrame] = {}
        self._news_cache: dict[tuple[str, int | None, int | None], list[dict]] = {}
        self._discover()

    # -- discovery ----------------------------------------------------------

    def _discover(self) -> None:
        self._angles = []
        if not ANGLES_DIR.exists():
            return
        for entry in sorted(ANGLES_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            compute_path = entry / "compute.py"
            spec_path = entry / "spec.yaml"
            if not compute_path.exists():
                continue
            spec = self._load_spec(spec_path) if spec_path.exists() else {}
            self._angles.append({
                "name": entry.name,
                "title": spec.get("title", entry.name),
                "purpose": spec.get("purpose", ""),
                "path": entry,
                "spec": spec,
            })

    def list_angles(self) -> list[dict[str, Any]]:
        return list(self._angles)

    def get_angle(self, name: str) -> dict[str, Any] | None:
        for a in self._angles:
            if a["name"] == name:
                return a
        return None

    def refresh(self) -> None:
        self._discover()

    # -- execution ----------------------------------------------------------

    def run(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        angle_names: list[str] | None = None,
        run_id: str | None = None,
        tier: str = "tier2",
        time_format: str | None = None,
    ) -> dict[str, Any]:
        """Run all (or selected) angles for a symbol.

        `run_id`: pre-assign the run's ID rather than letting `_run_angle`
        generate its own. Only meaningful when `angle_names` selects exactly
        one angle — a caller that pre-assigns a single ID for a multi-angle
        sweep would get that same ID recorded against every angle, which
        breaks run_id's one-run-one-ID traceability guarantee (see
        02-api-design.md's run_id design). Used by the v1 API's
        `trigger/.../{method}` route, which is always single-angle.

        `tier`: "tier2" (scheduled, the default — matches every existing
        call site's behavior unchanged) or "tier3" (triggered/ad-hoc,
        prunable). The v1 API's trigger route passes "tier3" explicitly.

        `time_format`: restrict this run to a single declared time_format
        instead of computing every one the angle declares. When given, the
        result is written under that exact `granularity` (not the storage
        default of "1D") — this is what the v1 API's `trigger` route needs
        so a request for one specific granularity doesn't silently compute
        every timeframe the angle happens to declare. `None` (the default)
        preserves every existing call site's behavior unchanged: every
        declared time_format computed and combined into one write under
        the default granularity.

        Returns a summary dict keyed by angle_name.
        """
        if run_id is not None and (angle_names is None or len(angle_names) != 1):
            raise ValueError("run_id can only be pre-assigned when angle_names selects exactly one angle")
        if run_id is not None and time_format is None:
            # A pre-assigned run_id no longer has one coherent meaning for an
            # unrestricted multi-format sweep -- each declared time_format
            # now gets its own real, distinct run_id and storage write (see
            # _run_angle), so a single caller-supplied ID would just be
            # silently discarded rather than actually identifying anything.
            raise ValueError("run_id can only be pre-assigned together with a single time_format")

        self._bar_cache.clear()
        self._news_cache.clear()
        results: dict[str, Any] = {}
        to_run = [a for a in self._angles if angle_names is None or a["name"] in angle_names]

        for angle in to_run:
            # Generated here (not left to _run_angle) so a real run_id exists
            # even on a failure that happens before _run_angle would have
            # made its own -- RunLog.record_run's run_id column is NOT NULL,
            # and a failed run needs its own real, traceable ID same as a
            # successful one.
            angle_run_id = run_id or uuid4().hex[:12]
            t0 = time.perf_counter()
            try:
                with sync_timer(f"angle.{angle['name']}"):
                    count = self._run_angle(
                        symbol, angle, from_ts, to_ts, run_id=angle_run_id, tier=tier, time_format=time_format
                    )
                results[angle["name"]] = {
                    "status": "completed",
                    "row_count": count,
                }
            except Exception as exc:
                LOG.exception("Angle %s failed for %s", angle["name"], symbol)
                duration = time.perf_counter() - t0
                # Previously silent: a failed angle left zero trace in
                # RunLog at all (record_run was only ever called from the
                # success path inside _run_angle). Recording the failure
                # here -- real elapsed time, real error, real granularity
                # -- is what makes RunLog an actual "what completed, what
                # failed, how long did it take" lookup rather than only
                # ever showing successes.
                self._run_log.record_run(
                    symbol=symbol,
                    angle_name=angle["name"],
                    run_id=angle_run_id,
                    analysis_from=from_ts,
                    analysis_until=to_ts,
                    tier=tier,
                    status="error",
                    error=str(exc),
                    duration_seconds=duration,
                    granularity=time_format or "1D",
                )
                results[angle["name"]] = {"status": "error", "error": str(exc)}

        return results

    def _run_angle(
        self,
        symbol: str,
        angle: dict[str, Any],
        from_ts: int | None,
        to_ts: int | None,
        run_id: str | None = None,
        tier: str = "tier2",
        time_format: str | None = None,
    ) -> int:
        """Run an angle for each of its time_formats (or just `time_format`,
        if given). Each time_format gets its OWN storage write and its OWN
        RunLog row, under its own real granularity -- previously every
        declared format got combined into one DataFrame and written/recorded
        under a single default "1D" bucket regardless of what was actually
        computed, so a later fetch scoped to (say) "1H" found nothing even
        though 1H rows existed, mixed in under "1D". Returns total row count
        across every time_format actually run (skipped/empty ones excluded).
        """
        module = self._import_compute(angle["name"])
        if module is None:
            raise ImportError(f"Could not import compute for {angle['name']}")

        declared_time_formats = angle["spec"].get("time_formats", DEFAULT_TIME_FORMATS)
        if time_format is not None:
            if time_format not in declared_time_formats:
                raise ValueError(
                    f"{angle['name']} does not declare time_format '{time_format}' "
                    f"(declared: {declared_time_formats})"
                )
            time_formats = [time_format]
        else:
            time_formats = declared_time_formats
        needs_bars = angle["spec"].get("needs_bars", True)
        news = self._fetch_news(symbol, from_ts, to_ts)

        total_rows = 0
        for tf in time_formats:
            # Existing-run check is now scoped per (symbol, angle, tf) --
            # previously this only ever checked the default "1D" granularity
            # for the whole angle, which was correct back when everything
            # really did land under "1D" together, but would now wrongly
            # skip (or wrongly NOT skip) individual timeframes once each one
            # is stored under its own real granularity.
            if self._run_log.has_existing_run(symbol, angle["name"], from_ts, to_ts, granularity=tf, tier=tier):
                LOG.info("Skipping %s for %s at %s — existing run found", angle["name"], symbol, tf)
                continue

            tf_t0 = time.perf_counter()
            bars = self._fetch_bars(symbol, tf, from_ts, to_ts) if needs_bars else pd.DataFrame()
            compute_kwargs: dict[str, Any] = {
                "symbol": symbol,
                "bars": bars,
                "news": news,
                "from_ts": from_ts,
                "to_ts": to_ts,
                "time_format": tf,
            }
            if "price_client" in inspect.signature(module.compute).parameters:
                compute_kwargs["price_client"] = self._price_client
            df = module.compute(**compute_kwargs)

            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            df = df.copy()
            if "time_format" in df.columns:
                df = df.drop(columns=["time_format"])
            df["time_format"] = tf

            # A single explicitly-requested time_format keeps the caller's
            # exact run_id -- the v1 API's trigger/fetch_by_run contract
            # depends on polling by that exact ID. An unrestricted
            # multi-format sweep has no such single-ID contract to
            # preserve, and reusing one run_id across multiple real writes
            # here would violate RunLog's run_id UNIQUE constraint
            # (INSERT OR REPLACE would silently erase every earlier
            # timeframe's row) -- so each timeframe gets its own fresh,
            # real, distinct run_id instead.
            tf_run_id = run_id if time_format is not None else uuid4().hex[:12]

            self._storage.write(
                symbol,
                angle["name"],
                df,
                analysis_from=from_ts,
                analysis_until=to_ts,
                run_id=tf_run_id,
                tier=tier,
                granularity=tf,
            )
            self._run_log.record_run(
                symbol=symbol,
                angle_name=angle["name"],
                run_id=tf_run_id,
                analysis_from=from_ts,
                analysis_until=to_ts,
                tier=tier,
                row_count=len(df),
                duration_seconds=time.perf_counter() - tf_t0,
                granularity=tf,
            )
            total_rows += len(df)

        return total_rows

    def _fetch_bars(
        self,
        symbol: str,
        time_format: str,
        from_ts: int | None,
        to_ts: int | None,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars at the given time_format for the symbol."""
        key = (symbol, time_format)
        cached = self._bar_cache.get(key)
        if cached is not None:
            return cached
        if self._price_client is None:
            return pd.DataFrame()
        try:
            candles = self._price_client.get_candles(symbol, from_ts=from_ts, to_ts=to_ts, interval=time_format)
            if not candles:
                return pd.DataFrame()
            df = pd.DataFrame(candles)
            if "bar_ts" in df.columns:
                df["bar_ts"] = df["bar_ts"].astype(int)
            self._bar_cache[key] = df
            return df
        except Exception:
            LOG.exception("Failed to fetch bars for %s at %s", symbol, time_format)
            return pd.DataFrame()

    def _fetch_news(
        self,
        symbol: str,
        from_ts: int | None,
        to_ts: int | None,
    ) -> list[dict]:
        """Fetch news articles for the symbol (cached once per run)."""
        if self._news_client is None:
            return []
        key = (symbol.upper(), from_ts, to_ts)
        cached = self._news_cache.get(key)
        if cached is not None:
            return cached
        try:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
            self._news_cache[key] = articles or []
            return articles or []
        except Exception:
            LOG.exception("Failed to fetch news for %s", symbol)
            self._news_cache[key] = []
            return []

    # -- helpers ------------------------------------------------------------

    def _import_compute(self, angle_name: str) -> Any:
        try:
            module_path = f"vinu_initial_analysis.angles.{angle_name}.compute"
            if module_path in sys.modules:
                return sys.modules[module_path]
            return importlib.import_module(module_path)
        except Exception as exc:
            LOG.warning("Could not import angle %s: %s", angle_name, exc)
            return None

    def _load_spec(self, path: Path) -> dict[str, Any]:
        try:
            import yaml
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
