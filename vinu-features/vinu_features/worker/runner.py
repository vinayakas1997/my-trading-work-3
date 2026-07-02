"""Background worker: claim pending jobs and produce run artifacts."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from vinu_features.client.stock_price import CandleClient
from vinu_features.config import VinuFeaturesConfig, load_config
from vinu_features.engine.engine import FeatureEngine
from vinu_features.storage.models import FeatureRequest, STATUS_RUNNING
from vinu_features.storage.sqlite_backend import SqliteBackend

LOG = logging.getLogger(__name__)


class FeatureWorker:
    def __init__(
        self,
        storage: SqliteBackend,
        *,
        config: VinuFeaturesConfig | None = None,
        engine: FeatureEngine | None = None,
    ) -> None:
        self.storage = storage
        self.config = config or load_config()
        self.engine = engine or FeatureEngine()

    def process_one(self, request_id: int) -> FeatureRequest | None:
        pending = self.storage.get_request(request_id)
        if pending is None:
            return None
        if pending.status != "pending":
            return pending
        running = self.storage.mark_running(request_id)
        if running is None:
            return self.storage.get_request(request_id)
        return self._execute(running)

    def process_pending(self, *, limit: int = 1) -> list[FeatureRequest]:
        results: list[FeatureRequest] = []
        for _ in range(max(1, limit)):
            pending = self.storage.claim_next_pending()
            if pending is None or pending.id is None:
                break
            running = self.storage.mark_running(pending.id)
            if running is None:
                continue
            results.append(self._execute(running))
        return results

    def _execute(self, request: FeatureRequest) -> FeatureRequest:
        assert request.id is not None
        run_dir = self.engine.run_dir_for(self.config.data_dir, request)
        try:
            if run_dir.exists():
                shutil.rmtree(run_dir)
            completed, row_count = self.engine.process(request, data_root=self.config.data_dir)
            if request.ml_model and request.ml_label:
                from vinu_features.compute.ml_models.runner import run_ml_step

                run_ml_step(
                    run_dir=completed,
                    ml_model=request.ml_model,
                    ml_label=request.ml_label,
                    feature_columns=request.features,
                )
            return self.storage.mark_done(
                request.id,
                file_path=str(completed),
                row_count=row_count,
            ) or request
        except Exception as exc:
            LOG.exception("Feature run failed for request %s", request.id)
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)
            failed = self.storage.mark_failed(request.id, error_message=str(exc))
            return failed or request
