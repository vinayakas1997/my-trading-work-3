"""Generate YAML catalogs for all factor groups from Python source files.

Usage:
    python scripts/generate_yaml_catalog.py

Output:
    vinu_tools/compute/formulas/catalog/<group>.yaml  (one per factor group)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

ALPHA_FACTORS_DIR = (
    Path(__file__).resolve().parent.parent
    / "vinu_tools" / "compute" / "factors/singles"
)
OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "vinu_tools" / "compute" / "formulas" / "catalog"
)

ALPHA_META_VAR = "__alpha_meta__"


def extract_meta_dict(py_file: Path) -> dict | None:
    """Extract __alpha_meta__ dict from a Python factor file."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == ALPHA_META_VAR:
                    if isinstance(node.value, ast.Dict):
                        kv: dict = {}
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                try:
                                    kv[k.value] = ast.literal_eval(v)
                                except (ValueError, SyntaxError):
                                    pass
                        return kv
    return None


def extract_params(meta: dict) -> dict:
    """Extract tunable parameters from formula_latex or notes.

    This identifies numeric constants in the formula that could be exposed
    as tunable parameters. Currently placeholder — override params by manually
    editing the generated YAML.
    """
    params = {}
    return params


def get_formula_short(formula_latex: str, max_len: int = 120) -> str:
    if len(formula_latex) <= max_len:
        return formula_latex
    return formula_latex[: max_len - 3] + "..."


def generate_catalog_for_group(group_name: str) -> dict:
    """Generate a YAML catalog entry for one factor group.

    Preserves any manually added fields (description, interpretation, when_to_use,
    params) from existing YAML if it exists.
    """
    group_dir = ALPHA_FACTORS_DIR / group_name
    if not group_dir.exists():
        print(f"  SKIP: {group_dir} does not exist")
        return {}

    # Load existing catalog to preserve manual fields
    existing: dict = {}
    existing_path = OUTPUT_DIR / f"{group_name}.yaml"
    if existing_path.exists():
        with open(existing_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    catalog = {}
    py_files = sorted(group_dir.glob("*.py"))
    for py_file in py_files:
        if py_file.name == "__init__.py" or py_file.name == "_compat.py":
            continue
        meta = extract_meta_dict(py_file)
        if meta is None:
            continue

        factor_id = meta.get("id", py_file.stem)

        # Auto-generated fields
        entry = {
            "id": factor_id,
            "theme": meta.get("theme", ["other"]),
            "formula": meta.get("formula_latex", ""),
            "columns_required": meta.get("columns_required", ["close"]),
            "universe": meta.get("universe", "us_equity"),
            "frequency": meta.get("frequency", "1d"),
            "decay_horizon": meta.get("decay_horizon", 60),
            "min_warmup_bars": meta.get("min_warmup_bars", 20),
            "params": extract_params(meta),
            "description": f"Factor {factor_id} - {', '.join(meta.get('theme', ['other']))}",
            "interpretation": "",
            "when_to_use": "",
            "source": f"alpha_factors/{group_name}/{py_file.name}",
        }

        # Preserve manual fields from existing catalog
        if factor_id in existing:
            existing_entry = existing[factor_id]
            for field in ("params", "description", "interpretation", "when_to_use"):
                if field in existing_entry and existing_entry[field]:
                    if field == "params" and isinstance(existing_entry.get(field), dict):
                        auto_params = entry.get("params", {})
                        merged_params = dict(existing_entry[field])
                        for k, v in auto_params.items():
                            if k not in merged_params:
                                merged_params[k] = v
                        entry["params"] = merged_params
                    elif isinstance(existing_entry.get(field), str) and existing_entry[field].strip():
                        entry[field] = existing_entry[field]

        catalog[factor_id] = entry

    return catalog


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    group_names = ["alpha101", "gtja191", "academic", "fundamental"]
    # Note: qlib158 was removed (duplicate of alpha158 recipe)

    total_factors = 0
    for group in group_names:
        print(f"Generating catalog for {group}...")
        catalog = generate_catalog_for_group(group)
        if not catalog:
            continue

        output_path = OUTPUT_DIR / f"{group}.yaml"
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                catalog,
                f,
                default_flow_style=None,
                sort_keys=False,
                allow_unicode=True,
                width=120,
            )
        count = len(catalog)
        total_factors += count
        print(f"  → {count} factors written to {output_path}")

    print(f"\nTotal: {total_factors} factors across {len(group_names)} groups")


if __name__ == "__main__":
    main()
