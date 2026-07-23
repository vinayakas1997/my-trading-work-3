from __future__ import annotations

import importlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from vinu_initial_analysis.storage.parquet import AngleStorage
from vinu_initial_analysis.storage.meta import RunLog

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
    ) -> dict[str, Any]:
        """Run all (or selected) angles for a symbol.

        Returns a summary dict keyed by angle_name.
        """
        self._bar_cache.clear()
        results: dict[str, Any] = {}
        to_run = [a for a in self._angles if angle_names is None or a["name"] in angle_names]

        for angle in to_run:
            try:
                with sync_timer(f"angle.{angle['name']}"):
                    count = self._run_angle(symbol, angle, from_ts, to_ts)
                results[angle["name"]] = {
                    "status": "completed",
                    "row_count": count,
                }
            except Exception as exc:
                LOG.exception("Angle %s failed for %s", angle["name"], symbol)
                results[angle["name"]] = {"status": "error", "error": str(exc)}

        return results

    def _run_angle(
        self,
        symbol: str,
        angle: dict[str, Any],
        from_ts: int | None,
        to_ts: int | None,
    ) -> int:
        """Run an angle for each of its time_formats. Returns total row count."""
        existing = self._run_log.has_existing_run(symbol, angle["name"], from_ts, to_ts)
        if existing:
            LOG.info("Skipping %s for %s — existing run found", angle["name"], symbol)
            return 0

        module = self._import_compute(angle["name"])
        if module is None:
            raise ImportError(f"Could not import compute for {angle['name']}")

        time_formats = angle["spec"].get("time_formats", DEFAULT_TIME_FORMATS)
        needs_bars = angle["spec"].get("needs_bars", True)
        run_id = uuid4().hex[:12]
        all_dfs: list[pd.DataFrame] = []

        news = self._fetch_news(symbol, from_ts, to_ts)

        for tf in time_formats:
            bars = self._fetch_bars(symbol, tf, from_ts, to_ts) if needs_bars else pd.DataFrame()
            df = module.compute(
                symbol, bars=bars, news=news,
                from_ts=from_ts, to_ts=to_ts, time_format=tf,
            )

            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            df = df.copy()
            if "time_format" in df.columns:
                df = df.drop(columns=["time_format"])
            df["time_format"] = tf
            all_dfs.append(df)

        if not all_dfs:
            return 0

        combined = pd.concat(all_dfs, ignore_index=True)
        self._storage.write(
            symbol,
            angle["name"],
            combined,
            analysis_from=from_ts,
            analysis_until=to_ts,
            run_id=run_id,
        )
        self._run_log.record_run(
            symbol=symbol,
            angle_name=angle["name"],
            run_id=run_id,
            analysis_from=from_ts,
            analysis_until=to_ts,
            row_count=len(combined),
        )
        return len(combined)

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
        """Fetch news articles for the symbol."""
        if self._news_client is None:
            return []
        try:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
            return articles or []
        except Exception:
            LOG.exception("Failed to fetch news for %s", symbol)
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
