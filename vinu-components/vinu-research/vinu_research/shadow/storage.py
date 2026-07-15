from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from vinu_research.shadow.models import ShadowProfile

LOG = logging.getLogger(__name__)

SHADOW_ROOT = Path.home() / ".vinu" / "shadow_accounts"


class ShadowStorage:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or SHADOW_ROOT
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, shadow_id: str) -> Path:
        return self._root / f"{shadow_id}.json"

    def _atomic_write(self, path: Path, data: dict[str, Any]) -> None:
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="shadow_", dir=str(self._root))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(fd)
            os.replace(tmp, str(path))
        except Exception as exc:
            LOG.error("Failed to write %s: %s", path, exc)
            raise
        finally:
            if tmp is not None and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    @staticmethod
    def compute_hash(rows: list[dict[str, Any]]) -> str:
        raw = json.dumps(rows, sort_keys=True, default=str).encode()
        return hashlib.sha1(raw).hexdigest()

    def save(self, profile: ShadowProfile) -> ShadowProfile:
        path = self._path(profile.shadow_id)
        self._atomic_write(path, profile.to_dict())
        return profile

    def load(self, shadow_id: str) -> ShadowProfile | None:
        path = self._path(shadow_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ShadowProfile.from_dict(data)
        except (json.JSONDecodeError, OSError) as exc:
            LOG.warning("Failed to load shadow %s: %s", shadow_id, exc)
            return None

    def exists(self, journal_hash: str) -> str | None:
        for fpath in self._root.glob("*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                if data.get("journal_hash") == journal_hash:
                    return data["shadow_id"]
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def list_all(self) -> list[ShadowProfile]:
        profiles: list[ShadowProfile] = []
        for fpath in sorted(self._root.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                profiles.append(ShadowProfile.from_dict(data))
            except (json.JSONDecodeError, OSError):
                continue
        return profiles

    def delete(self, shadow_id: str) -> bool:
        path = self._path(shadow_id)
        if not path.exists():
            return False
        path.unlink()
        return True
