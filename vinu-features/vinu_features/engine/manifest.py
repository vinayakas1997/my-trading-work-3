"""Write manifest.md audit files for feature runs."""

from __future__ import annotations

from pathlib import Path

from vinu_features.storage.models import FeatureRequest


def write_manifest(path: Path, request: FeatureRequest, *, row_count: int, parquet_name: str) -> None:
    lines = [
        f"# {request.title}",
        "",
        "## Request",
        f"- **ID:** {request.id}",
        f"- **Symbols:** {', '.join(request.symbols)}",
        f"- **From ts:** {request.from_ts}",
        f"- **To ts:** {request.to_ts}",
        f"- **Interval:** {request.interval}",
        f"- **Preset:** {request.preset or '(none)'}",
        f"- **Features:** {', '.join(request.features)}",
        f"- **Conditions:** {request.conditions or '(none)'}",
        "",
        "## Run",
        f"- **Created:** {request.created_at}",
        f"- **Completed:** {request.updated_at}",
        f"- **Status:** {request.status}",
        "",
        "## Output",
        f"- **File:** {parquet_name}",
        f"- **Rows:** {row_count}",
        f"- **Columns:** ts, symbol, open, high, low, close, volume, "
        + ", ".join(request.features),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
