"""FeatureService facade for submit, query, worker, and delete."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_tools.client.stock_price import CandleClient
from vinu_tools.config import VinuFeaturesConfig, load_config
from vinu_tools.compute.feature_spec import validate_and_resolve
from vinu_tools.constants import SECONDS_PER_DAY
from vinu_tools.engine.engine import FeatureEngine
from vinu_tools.presets.registry import resolve_features
from vinu_tools.storage import create_storage
from vinu_tools.storage.models import FeatureRequest, STATUS_DONE, STATUS_PENDING, SubmitRequest
from vinu_tools.storage.sqlite_backend import SqliteBackend
from vinu_tools.worker.runner import FeatureWorker


class FeatureService:
    def __init__(
        self,
        *,
        config: VinuFeaturesConfig | None = None,
        storage: SqliteBackend | None = None,
        candle_client: CandleClient | None = None,
        data_dir: str | None = None,
        meta_db_path: str | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = load_config(data_dir=data_dir, meta_db_path=meta_db_path)
        self.storage = storage or create_storage(self.config.meta_db_path)
        self._owns_storage = storage is None
        engine = FeatureEngine(client=candle_client) if candle_client else FeatureEngine()
        self.worker = FeatureWorker(self.storage, config=self.config, engine=engine)

    def close(self) -> None:
        if self._owns_storage:
            self.storage.close()

    def __enter__(self) -> FeatureService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def submit(
        self,
        *,
        title: str,
        symbols: list[str],
        from_ts: int | None = None,
        to_ts: int | None = None,
        days: int | None = None,
        interval: str = "1d",
        preset: str | None = None,
        features: list[str | dict[str, Any]] | None = None,
        conditions: str | None = None,
        ml_model: str | None = None,
        ml_label: str | None = None,
        run_immediately: bool = False,
        dry_run: bool = False,
    ) -> FeatureRequest:
        if not title.strip():
            raise ValueError("title is required")
        syms = [s.strip().upper() for s in symbols if s.strip()]
        if not syms:
            raise ValueError("At least one symbol is required")

        now_ts = int(datetime.now(timezone.utc).timestamp())
        if to_ts is None:
            to_ts = now_ts
        if from_ts is None:
            if days is None:
                days = 365
            from_ts = to_ts - days * SECONDS_PER_DAY

        if preset and features:
            raise ValueError("Provide either preset or features, not both")
        if preset:
            from vinu_tools.compute.factors.recipes import catalog as recipe_catalog

            if not recipe_catalog.is_recipe(preset):
                raise ValueError(f"Unknown preset: {preset}")
            resolved = resolve_features(preset=preset, features=[])
        else:
            if not features:
                raise ValueError("Either preset or features is required")
            resolved = validate_and_resolve(features)

        if dry_run:
            return FeatureRequest(
                id=-1,
                title=title.strip(),
                symbols=syms,
                status=STATUS_PENDING,
                from_ts=from_ts,
                to_ts=to_ts,
                interval=interval,
                preset=preset,
                hash="",
                created_at="",
                updated_at="",
            )

        req = SubmitRequest(
            title=title.strip(),
            symbols=syms,
            from_ts=from_ts,
            to_ts=to_ts,
            interval=interval,
            preset=preset,
            features=resolved if not preset else [],
            conditions=conditions,
            ml_model=ml_model,
            ml_label=ml_label,
        )
        request_hash = self._hash_request(req, resolved)
        existing = self.storage.get_by_hash(request_hash, status=STATUS_DONE)
        if existing is not None:
            return existing

        created = self.storage.insert_request(req, request_hash=request_hash, features=resolved)
        if run_immediately and created.id is not None:
            return self.worker.process_one(created.id) or created
        return created

    def get_request(self, request_id: int) -> FeatureRequest | None:
        return self.storage.get_request(request_id)

    def get_by_title(self, title: str) -> FeatureRequest | None:
        return self.storage.get_latest_by_title(title)

    def list_requests(
        self,
        *,
        status: str | None = None,
        title: str | None = None,
        limit: int = 100,
    ) -> list[FeatureRequest]:
        return self.storage.list_requests(status=status, title=title, limit=limit)

    def run_worker(self, *, once: bool = True, limit: int = 1) -> list[FeatureRequest]:
        if once:
            return self.worker.process_pending(limit=limit)
        results: list[FeatureRequest] = []
        while True:
            batch = self.worker.process_pending(limit=limit)
            if not batch:
                break
            results.extend(batch)
        return results

    def run_request(self, request_id: int) -> FeatureRequest | None:
        req = self.storage.get_request(request_id)
        if req is None:
            return None
        if req.status == STATUS_DONE:
            return req
        return self.worker.process_one(request_id)

    def delete_request(self, request_id: int) -> FeatureRequest | None:
        req = self.storage.get_request(request_id)
        if req is None:
            return None
        if req.file_path:
            path = Path(req.file_path)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        return self.storage.mark_deleted(request_id)

    def list_presets(self) -> list[dict[str, Any]]:
        from vinu_tools.presets.registry import list_presets

        return [
            {"name": p.name, "features": list(p.features), "description": p.description}
            for p in list_presets()
        ]

    # ── Factor catalog ──────────────────────────────────────────────

    def list_factors(self) -> list[dict[str, Any]]:
        """List all factors from YAML catalogs."""
        specs = []
        from vinu_tools.compute.formulas.engine import resolve_factor_spec
        from pathlib import Path
        catalog_dir = Path(__file__).resolve().parent / "compute" / "formulas" / "catalog"
        import yaml
        for yaml_path in sorted(catalog_dir.glob("*.yaml")):
            group = yaml_path.stem
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            for fid, entry in data.items():
                specs.append({"id": fid, "group": group, "theme": entry.get("theme", []), "description": entry.get("description", "")[:80]})
        return specs

    def search_factors(self, query: str) -> list[dict[str, Any]]:
        """Search factors by concept/description."""
        from vinu_tools.compute.meta.concept_index import search_factors
        return search_factors(query)

    def get_factor_spec(self, factor_id: str) -> dict[str, Any] | None:
        """Get full spec for a factor ID."""
        from vinu_tools.compute.formulas.engine import resolve_factor_spec
        return resolve_factor_spec(factor_id)

    def bench_factor(
        self, factor_id: str, panel: dict, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Bench a single factor with IC analysis."""
        from vinu_tools.compute.bench import bench_factor as _bench
        return _bench(factor_id, panel, params=params)

    def bench_factors(self, factor_ids: list[str], panel: dict) -> list[dict[str, Any]]:
        """Bench multiple factors, ranked by |IC|."""
        from vinu_tools.compute.bench import bench_factors as _bench
        return _bench(factor_ids, panel)

    def bench_zoo(self, group: str, panel: dict, max_factors: int = 10) -> list[dict[str, Any]]:
        """Bench an entire zoo group."""
        from vinu_tools.compute.bench import bench_zoo as _bench
        return _bench(group, panel, max_factors=max_factors)

    # ── ML models ───────────────────────────────────────────────────

    def list_ml_models(self) -> list[str]:
        from vinu_tools.compute.ml import list_models
        return list_models()

    def train_ml_model(self, model_name: str, X, y) -> dict[str, Any]:
        """Train a model and return (estimator_info, predictions, metrics)."""
        from vinu_tools.compute.ml import train, evaluate
        estimator, preds = train(model_name, X, y)
        metrics = evaluate(y, preds)
        return {"model": model_name, "estimator_type": type(estimator).__name__, "predictions": preds, "metrics": metrics}

    def select_best_ml_model(self, X_train, y_train, X_test, y_test, candidates=None) -> dict[str, Any]:
        """Auto-select best model by OOS IC."""
        from vinu_tools.compute.ml import select_best
        best_name, best_ic, results = select_best(X_train, y_train, X_test, y_test, candidates)
        return {"best_model": best_name, "best_ic": best_ic, "results": [{"name": r["name"], "ic": r["ic"]} for r in results]}

    def health_info(self) -> dict[str, Any]:
        info = self.storage.health_info()
        info["data_dir"] = str(self.config.data_dir)
        info["stock_api_url"] = self.config.stock_api_url
        import httpx
        import time
        for attempt in range(3):
            try:
                res = httpx.get(f"{self.config.stock_api_url}/health", timeout=2.0)
                info["stock_api_healthy"] = res.status_code == 200
                break
            except Exception:
                if attempt < 2:
                    time.sleep(1.5 ** attempt)
                else:
                    info["stock_api_healthy"] = False
        from vinu_tools.compute.feature_catalog import list_indicators
        from vinu_tools.presets.registry import list_presets
        info["catalog_count"] = len(list_indicators())
        info["presets_count"] = len(list_presets())
        return info

    @staticmethod
    def _hash_request(req: SubmitRequest, features: list[str]) -> str:
        payload = {
            "symbols": sorted(req.symbols),
            "from_ts": req.from_ts,
            "to_ts": req.to_ts,
            "interval": req.interval,
            "features": sorted(features),
            "conditions": req.conditions or "",
            "ml_model": req.ml_model or "",
            "ml_label": req.ml_label or "",
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()
