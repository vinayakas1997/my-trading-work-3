"""Remove YAML params whose default value doesn't exist in the compute body.

These params were auto-generated from formula constants but the formula
value doesn't appear in the Python code (the implementer used a different constant).
Keeping them in YAML would be misleading — overrides would have no effect.

Usage:
    python scripts/clean_spurious_yaml_params.py
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO / "vinu_tools" / "compute" / "formulas" / "catalog"
FACTOR_DIRS = {
    "gtja191": REPO / "vinu_tools" / "compute" / "factors/singles" / "gtja191",
    "alpha101": REPO / "vinu_tools" / "compute" / "factors/singles" / "alpha101",
    "academic": REPO / "vinu_tools" / "compute" / "factors/singles" / "academic",
    "fundamental": REPO / "vinu_tools" / "compute" / "factors/singles" / "fundamental",
}

ID_RE = re.compile(r"""['"]id['"]\s*:\s*['"]([^'"]+)['"]""")
KWARG_GET_RE = re.compile(r"kwargs\.get\('([^']+)',")

# Pre-load YAML
yaml_data: dict[str, dict] = {}
yaml_file_for: dict[str, Path] = {}
for yp in sorted(CATALOG_DIR.glob("*.yaml")):
    with open(yp) as f:
        data = yaml.safe_load(f) or {}
    for fid in data:
        yaml_data[fid] = data
        yaml_file_for[fid] = yp

removed_total = 0

for group, d in FACTOR_DIRS.items():
    if not d.exists():
        continue
    for py_file in sorted(d.glob("*.py")):
        if py_file.stem == "__init__":
            continue
        content = py_file.read_text()
        m = ID_RE.search(content)
        if not m:
            continue
        factor_id = m.group(1)

        ydata = yaml_data.get(factor_id)
        if ydata is None:
            continue
        entry = ydata.get(factor_id, {})
        params = entry.get("params", {})
        if not params:
            continue

        body_start = content.find("def compute(")
        if body_start < 0:
            continue
        body = content[body_start:]

        wired = {m.group(1) for m in KWARG_GET_RE.finditer(content)}

        to_remove = []
        for pname, pinfo in params.items():
            if pname in wired:
                continue
            default = pinfo.get("default")
            pattern = re.compile(r'(?<!\w)' + re.escape(str(default)) + r'(?!\w)')
            if not pattern.search(body):
                to_remove.append(pname)

        if to_remove:
            for pname in to_remove:
                del params[pname]
            if not params:
                del entry["params"]
            removed_total += len(to_remove)

# Write modified YAML files — use in-memory data (already modified)
written = set()
for factor_id, ydata in yaml_data.items():
    yp = yaml_file_for.get(factor_id)
    if yp is None or yp in written:
        continue
    written.add(yp)
    with open(yp, "w") as f:
        yaml.dump(ydata, f, default_flow_style=None, sort_keys=False, allow_unicode=True, width=120)

print(f"Removed {removed_total} spurious params from YAML across {len(written)} files")
