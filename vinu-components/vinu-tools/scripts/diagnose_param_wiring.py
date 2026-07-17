"""Diagnose which YAML params are wired vs unwired in factor compute functions.

Reports:
- Total params / wired / unwired
- Per-file list of unwired params with reasons
- Factors with 0% wiring rate

Usage:
    python scripts/diagnose_param_wiring.py
"""

from __future__ import annotations

import re
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

ID_RE = re.compile(r"""['"]id['"]\s*:\s*['"]([^'"]+)['"]""")
KWARG_GET_RE = re.compile(r"kwargs\.get\('([^']+)',")

# Build factor_id -> file path
id_to_file: dict[str, Path] = {}
for d in FACTOR_DIRS:
    if not d.exists():
        continue
    for py_file in sorted(d.glob("*.py")):
        if py_file.stem == "__init__":
            continue
        m = ID_RE.search(py_file.read_text())
        if m:
            id_to_file[m.group(1)] = py_file

# Build factor_id -> yaml params
factor_params: dict[str, dict] = {}
for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    for fid, entry in data.items():
        ps = entry.get("params")
        if ps and isinstance(ps, dict):
            factor_params[fid] = ps

total_params = 0
total_wired = 0
zero_rate_files = []

for fid in sorted(factor_params):
    if fid not in id_to_file:
        continue

    params = factor_params[fid]
    fpath = id_to_file[fid]
    content = fpath.read_text()
    source_file = fpath.name

    # Find all wired params in this file
    wired = set()
    for m in KWARG_GET_RE.finditer(content):
        wired.add(m.group(1))

    file_total = len(params)
    file_wired = sum(1 for p in params if p in wired)
    total_params += file_total
    total_wired += file_wired

    if file_wired == 0:
        zero_rate_files.append((fid, source_file, file_total))

    unwired = [p for p in params if p not in wired]

    if unwired:
        for pname in unwired:
            default = params[pname].get("default")
            # Count how many times this default value appears in the compute body
            body_start = content.find("def compute(")
            if body_start >= 0:
                body = content[body_start:]
                val_count = len(re.findall(rf'(?<!\w){default}(?!\w)', body))
            else:
                val_count = 0
            print(f"  {fid} / {pname}: default={default}, available={val_count}")

print(f"\nSummary: {total_wired}/{total_params} params wired ({total_wired*100//max(total_params,1)}%)")

if zero_rate_files:
    print(f"\nFactors with 0% wiring rate ({len(zero_rate_files)}):")
    for fid, src, total in zero_rate_files[:20]:
        print(f"  {fid} ({src}) — {total} params")
    if len(zero_rate_files) > 20:
        print(f"  ... and {len(zero_rate_files) - 20} more")
