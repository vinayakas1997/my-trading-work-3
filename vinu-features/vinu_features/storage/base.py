"""Storage backend protocol for vinu-features."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from vinu_features.storage.models import FeatureRequest, SubmitRequest


@runtime_checkable
class StorageBackend(Protocol):
    db_path: Path

    def close(self) -> None: ...

    def __enter__(self) -> StorageBackend: ...

    def __exit__(self, *args: object) -> None: ...

    def insert_request(self, req: SubmitRequest, *, request_hash: str, features: list[str]) -> FeatureRequest: ...

    def get_request(self, request_id: int) -> FeatureRequest | None: ...

    def get_latest_by_title(self, title: str) -> FeatureRequest | None: ...

    def get_by_hash(self, request_hash: str, *, status: str | None = None) -> FeatureRequest | None: ...

    def list_requests(
        self,
        *,
        status: str | None = None,
        title: str | None = None,
        limit: int = 100,
    ) -> list[FeatureRequest]: ...

    def claim_next_pending(self) -> FeatureRequest | None: ...

    def mark_running(self, request_id: int) -> FeatureRequest | None: ...

    def mark_done(
        self,
        request_id: int,
        *,
        file_path: str,
        row_count: int,
    ) -> FeatureRequest | None: ...

    def mark_failed(self, request_id: int, *, error_message: str) -> FeatureRequest | None: ...

    def mark_deleted(self, request_id: int) -> FeatureRequest | None: ...

    def health_info(self) -> dict[str, Any]: ...
