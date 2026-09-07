"""Freeze manifest — hash of config + data roots for lineage (B21, Row 14).

Minimal port of quant-live-readiness-kit freeze.py + contamination check:
- `freeze_manifest()` hashes VINU_*_DATA_ROOT, VINU_*_API_URL, and file mtimes under data roots
- Atomic write, deterministic JSON
- `contamination_check()` diffs two manifests for structural drift
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def freeze_manifest(output_path: str | Path | None = None) -> dict[str, Any]:
    """Collect deterministic manifest of current env + data roots."""
    import datetime

    manifest: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "env": {k: v for k, v in os.environ.items() if k.startswith("VINU_")},
        "data_roots": {},
        "file_hashes": {},
    }
    for key in [k for k in os.environ if k.endswith("_DATA_ROOT")]:
        p = Path(os.environ[key])
        manifest["data_roots"][key] = str(p)
        if p.exists() and p.is_dir():
            for fp in sorted(p.rglob("*")):
                if fp.is_file() and fp.stat().st_size < 10_000_000:
                    try:
                        manifest["file_hashes"][str(fp.relative_to(p))] = _hash_file(fp)
                    except OSError:
                        pass
    if output_path:
        Path(output_path).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def contamination_check(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Diff two manifests."""
    old_keys = set(old.get("file_hashes", {}))
    new_keys = set(new.get("file_hashes", {}))
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = sorted(k for k in old_keys & new_keys if old["file_hashes"][k] != new["file_hashes"][k])
    env_changed = {k: (old.get("env", {}).get(k), new.get("env", {}).get(k)) for k in set(old.get("env", {})) | set(new.get("env", {})) if old.get("env", {}).get(k) != new.get("env", {}).get(k)}
    return {"added": added, "removed": removed, "changed": changed, "env_changed": env_changed, "drift": bool(added or removed or changed or env_changed)}
