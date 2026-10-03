"""Model-serving core: runs the model-category analysis angles and FinBERT, nothing else.

The service imports the angle code from the `vinu-initial-analysis` package (one source of truth, no copy), so it needs
that package installed WITH its `models` extra (torch, chronos, timesfm). It does not touch the analysis store, run log
or any other service: it receives bars / news in the request and returns the angle's rows.

Errors are explicit and typed (`ModelError.status` + `.reason`); there is no silent fallback to a proxy here.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

LOG = logging.getLogger(__name__)


class ModelError(Exception):
    """A request the service cannot satisfy. `status` is the HTTP status, `reason` a stable machine-readable code."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.message = message


def _angles_dir() -> Path:
    from vinu_initial_analysis.runner import ANGLES_DIR

    return Path(ANGLES_DIR)


def discover_model_angles(angles_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """{angle_name: spec} for every angle whose spec.yaml says `category: model`."""
    import yaml

    out: dict[str, dict[str, Any]] = {}
    base = angles_dir or _angles_dir()
    for spec_path in sorted(base.glob("*/spec.yaml")):
        try:
            spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        except Exception:
            LOG.exception("unreadable spec %s", spec_path)
            continue
        if spec.get("category") == "model":
            out[spec_path.parent.name] = spec
    return out


@dataclass
class ModelService:
    max_concurrent: int = 1
    timeout_sec: float = 600.0
    # Some angles fall back to a simple statistical proxy when their model cannot load (the row says
    # model_backend=fallback_proxy). True keeps that behaviour but reports it; False turns it into a 503 so the caller
    # records an error run and retries, instead of storing a proxy result as if it were the model's.
    allow_proxy: bool = True
    angles_dir: Path | None = None
    # Overridable seams so tests need neither torch nor the real angle packages.
    module_loader: Callable[[str], Any] | None = None
    finbert_scorer: Callable[[list[str], int], list[dict]] | None = None
    models_enabled_fn: Callable[[], bool] | None = None
    _angles: dict[str, dict[str, Any]] | None = field(default=None, init=False, repr=False)
    _slots: threading.Semaphore = field(init=False, repr=False)
    _stats: dict[str, Any] = field(default_factory=lambda: {"calls": 0, "errors": 0, "last_error": None}, init=False)

    def __post_init__(self) -> None:
        self._slots = threading.Semaphore(max(1, int(self.max_concurrent)))

    # ---- registry / status ------------------------------------------------------------------------------------

    def angles(self) -> dict[str, dict[str, Any]]:
        if self._angles is None:
            self._angles = discover_model_angles(self.angles_dir)
        return self._angles

    def _models_enabled(self) -> bool:
        if self.models_enabled_fn is not None:
            return self.models_enabled_fn()
        from vinu_infra.model_policy import models_enabled

        return models_enabled()

    def status(self, *, deep: bool = False) -> dict[str, Any]:
        """Per-angle availability. `deep` actually imports every angle module (slow, loads torch)."""
        torch_ok = importlib.util.find_spec("torch") is not None
        rows = []
        for name, spec in self.angles().items():
            row: dict[str, Any] = {"angle": name, "title": spec.get("title")}
            if deep:
                try:
                    self._load_module(name)
                    row["available"], row["reason"] = True, None
                except ModelError as exc:
                    row["available"], row["reason"] = False, exc.message
            rows.append(row)
        return {
            "models_enabled": self._models_enabled(),
            "torch_installed": torch_ok,
            "max_concurrent": self.max_concurrent,
            "angles": rows,
            "stats": dict(self._stats),
        }

    # ---- angle compute ----------------------------------------------------------------------------------------

    def _load_module(self, angle: str) -> Any:
        try:
            if self.module_loader is not None:
                return self.module_loader(angle)
            return importlib.import_module(f"vinu_initial_analysis.angles.{angle}.compute")
        except ImportError as exc:
            raise ModelError(503, "model_unavailable", f"{angle}: a required library is missing: {exc}") from exc

    def _check_angle(self, angle: str) -> None:
        if angle not in self.angles():
            known = ", ".join(sorted(self.angles()))
            raise ModelError(404, "unknown_angle", f"{angle!r} is not a model angle (model angles: {known})")
        if not self._models_enabled():
            raise ModelError(503, "models_disabled", "VINU_MODELS_ENABLED is false in the model service")

    @staticmethod
    def _bars_frame(records: list[dict[str, Any]] | None) -> pd.DataFrame:
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "bar_ts" in df.columns:
            df["bar_ts"] = df["bar_ts"].astype("int64")
        return df

    def _run_angle_sync(self, angle: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        # The slot is held for the whole computation, including after an HTTP timeout, so a request that already gave
        # up cannot let a second one oversubscribe the GPU.
        with self._slots:
            module = self._load_module(angle)
            kwargs: dict[str, Any] = {
                "symbol": payload["symbol"], "bars": self._bars_frame(payload.get("bars")),
                "news": payload.get("news") or [], "from_ts": payload.get("from_ts"),
                "to_ts": payload.get("to_ts"), "time_format": payload.get("time_format"),
            }
            import inspect

            if "price_client" in inspect.signature(module.compute).parameters:
                kwargs["price_client"] = None
            df = module.compute(**kwargs)
        if df is None or not isinstance(df, pd.DataFrame):
            raise ModelError(500, "compute_error", f"{angle}.compute returned {type(df).__name__}, not a DataFrame")
        rows = json.loads(df.to_json(orient="records", date_format="iso")) if len(df) else []
        proxied = [r for r in rows if r.get("model_backend") == "fallback_proxy"]
        if proxied and not self.allow_proxy:
            raise ModelError(
                503, "model_unavailable",
                f"{angle}: the model could not run and the angle fell back to a proxy forecast "
                f"({proxied[0].get('fallback_reason') or 'no reason given'})",
            )
        return rows

    async def compute_angle(self, angle: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._check_angle(angle)
        if not payload.get("symbol"):
            raise ModelError(422, "bad_request", "symbol is required")
        started = time.perf_counter()
        self._stats["calls"] += 1
        loop = asyncio.get_running_loop()
        try:
            rows = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_angle_sync, angle, payload), timeout=self.timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            self._fail(f"{angle}: timed out after {self.timeout_sec}s")
            raise ModelError(504, "timeout", f"{angle} did not finish within {self.timeout_sec}s") from exc
        except ModelError as exc:
            self._fail(exc.message)
            raise
        except Exception as exc:  # noqa: BLE001 -- surfaced to the caller, which records an error run
            LOG.exception("angle %s failed", angle)
            self._fail(f"{angle}: {exc}")
            raise ModelError(500, "compute_error", f"{angle}: {exc}") from exc
        from vinu_infra.model_policy import policy_version

        backends: dict[str, int] = {}
        for r in rows:
            key = str(r.get("model_backend") or "n/a")
            backends[key] = backends.get(key, 0) + 1
        if backends.get("fallback_proxy"):
            self._stats["proxy_rows"] = self._stats.get("proxy_rows", 0) + backends["fallback_proxy"]
        return {
            "angle": angle, "row_count": len(rows), "rows": rows, "backends": backends,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1), "policy_version": policy_version(),
        }

    # ---- finbert ----------------------------------------------------------------------------------------------

    def _score_finbert_sync(self, texts: list[str], batch_size: int) -> list[dict]:
        with self._slots:
            if self.finbert_scorer is not None:
                return self.finbert_scorer(texts, batch_size)
            from vinu_infra.finbert_scoring import score_finbert_batch

            return score_finbert_batch(texts, batch_size)

    async def score_finbert(self, texts: list[str], batch_size: int = 16) -> dict[str, Any]:
        if not self._models_enabled():
            raise ModelError(503, "models_disabled", "VINU_MODELS_ENABLED is false in the model service")
        self._stats["calls"] += 1
        loop = asyncio.get_running_loop()
        try:
            results = await asyncio.wait_for(
                loop.run_in_executor(None, self._score_finbert_sync, texts, max(1, int(batch_size))),
                timeout=self.timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            self._fail("finbert: timed out")
            raise ModelError(504, "timeout", "finbert did not finish in time") from exc
        except ImportError as exc:
            self._fail(f"finbert: {exc}")
            raise ModelError(503, "model_unavailable", f"finbert: a required library is missing: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            LOG.exception("finbert failed")
            self._fail(f"finbert: {exc}")
            raise ModelError(500, "compute_error", f"finbert: {exc}") from exc
        return {"count": len(results), "results": results}

    def _fail(self, message: str) -> None:
        self._stats["errors"] += 1
        self._stats["last_error"] = message
