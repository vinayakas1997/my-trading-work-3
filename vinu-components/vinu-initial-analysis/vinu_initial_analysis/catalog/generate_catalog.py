"""Regenerate angles.yaml from spec.yaml files in the angles/ directory."""

from __future__ import annotations

import argparse
from pathlib import Path

ANGLES_DIR = Path(__file__).resolve().parent.parent / "angles"
CATALOG_PATH = Path(__file__).resolve().parent / "angles.yaml"


def generate_catalog(output_path: str | Path | None = None) -> str:
    """Walk angles/*/spec.yaml and produce a unified YAML catalog."""
    import yaml

    entries = []
    if not ANGLES_DIR.exists():
        raise FileNotFoundError(f"Angles directory not found: {ANGLES_DIR}")

    for folder in sorted(ANGLES_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        spec_file = folder / "spec.yaml"
        if not spec_file.exists():
            continue
        with open(spec_file, encoding="utf-8") as f:
            spec = yaml.safe_load(f) or {}

        entries.append({
            "id": folder.name,
            "title": spec.get("title", folder.name),
            "purpose": spec.get("purpose", ""),
            "time_formats": spec.get("time_formats", []),
            "inputs": spec.get("inputs", {"symbol": "str"}),
            "outputs": spec.get("outputs", []),
        })

    catalog = {"angles": entries}

    out_path = Path(output_path) if output_path else CATALOG_PATH
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(catalog, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Wrote {len(entries)} angles to {out_path}")
    return str(out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate angles YAML catalog")
    parser.add_argument("--output", default=None, help="Output path (default: angles.yaml)")
    args = parser.parse_args()
    generate_catalog(args.output)
