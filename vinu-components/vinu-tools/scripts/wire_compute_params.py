"""Add **kwargs to compute() functions that have params in YAML catalogs.

Usage: python scripts/wire_compute_params.py
"""

import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO / "vinu_tools" / "compute" / "formulas" / "catalog"
FACTOR_DIRS = [
    REPO / "vinu_tools" / "compute" / "factors/singles" / "gtja191",
    REPO / "vinu_tools" / "compute" / "factors/singles" / "alpha101",
    REPO / "vinu_tools" / "compute" / "factors/singles" / "academic",
    REPO / "vinu_tools" / "compute" / "factors/singles" / "fundamental",
]

# Build set of factor IDs that have params
factor_ids_with_params: set[str] = set()
for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    for fid, spec in data.items():
        if spec.get("params"):
            factor_ids_with_params.add(fid)

print(f"Found {len(factor_ids_with_params)} factors with params")

ID_RE = re.compile(r"""['"]id['"]\s*:\s*['"]([^'"]+)['"]""")

# Map factor ID to source file path
id_to_file: dict[str, Path] = {}
for d in FACTOR_DIRS:
    if not d.exists():
        continue
    for py_file in sorted(d.glob("*.py")):
        if py_file.stem == "__init__":
            continue
        content = py_file.read_text()
        m = ID_RE.search(content)
        if m:
            id_to_file[m.group(1)] = py_file

COMPUTE_RE = re.compile(r'^(def compute\(panel[^)]*)(\))(\s*->\s*pd\.DataFrame\s*)?\s*:', re.MULTILINE)


def add_kwargs_to_compute(source: str) -> str:
    def _replacer(m: re.Match) -> str:
        return f"{m.group(1)}, **kwargs{m.group(2)}{m.group(3) or ''}:"
    return COMPUTE_RE.sub(_replacer, source, count=1)


modified = 0
for fid in factor_ids_with_params:
    if fid not in id_to_file:
        print(f"  ? no file found for {fid}")
        continue
    fpath = id_to_file[fid]
    old = fpath.read_text()

    # Check if **kwargs already present
    if "**kwargs" in old:
        continue

    new = add_kwargs_to_compute(old)
    if new == old:
        print(f"  X could not patch {fid} in {fpath.name}")
        continue
    fpath.write_text(new)
    modified += 1

print(f"\nModified {modified} files")
