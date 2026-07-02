"""FeatureService facade for submit, query, worker, and delete."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_features.client.stock_price import CandleClient
from vinu_features.config import VinuFeaturesConfig, load_config
from vinu_features.compute.feature_spec import validate_and_resolve
from vinu_features.compute.registry import parse_feature_names
from vinu_features.engine.engine import FeatureEngine
from vinu_features.presets.registry import resolve_features
from vinu_features.storage.factory import create_storage
from vinu_features.storage.models import FeatureRequest, STATUS_DONE, SubmitRequest
from vinu_features.storage.sqlite_backend import SqliteBackend
from vinu_features.worker.runner import FeatureWorker


class FeatureService:
    def __init__(
        self,
        *,
        config: VinuFeaturesConfig | None = None,
        storage: SqliteBackend | None = None,
        candle_client: CandleClient | None = None,
    ) -> None:
        self.config = config or load_config()
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
            from_ts = to_ts - days * 86400

        if preset and features:
            raise ValueError("Provide either preset or features, not both")
        if preset:
            resolved = resolve_features(preset=preset, features=[])
            parse_feature_names([preset])
        else:
            if not features:
                raise ValueError("Either preset or features is required")
            resolved = validate_and_resolve(features)

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
        from vinu_features.presets.registry import list_presets

        return [
            {"name": p.name, "features": list(p.features), "description": p.description}
            for p in list_presets()
        ]

    def health_info(self) -> dict[str, Any]:
        info = self.storage.health_info()
        info["data_dir"] = str(self.config.data_dir)
        info["stock_api_url"] = self.config.stock_api_url
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
