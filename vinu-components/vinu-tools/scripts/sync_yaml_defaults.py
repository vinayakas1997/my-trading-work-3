"""Sync YAML param defaults with actual code defaults from kwargs.get() calls.

Some YAML params had wrong defaults (e.g., 0 instead of 100.0) due to
the YAML generator extracting individual digits from formula constants.
The pass 2 wiring script fixed the code defaults but the YAML wasn't updated.
"""

from __future__ import annotations

import ast
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
KWARG_GET_RE = re.compile(r"kwargs\.get\('([^']+)',\s*([^)]+)\)")

# Build factor_id -> {param_name: code_default}
factor_defaults: dict[str, dict[str, object]] = {}
for d in FACTOR_DIRS:
    if not d.exists():
        continue
    for f in sorted(d.glob("*.py")):
        if f.stem == "__init__":
            continue
        content = f.read_text()
        m = ID_RE.search(content)
        if not m:
            continue
        fid = m.group(1)
        defaults: dict[str, object] = {}
        for mm in KWARG_GET_RE.finditer(content):
            try:
                default_val = ast.literal_eval(mm.group(2))
                defaults[mm.group(1)] = default_val
            except (ValueError, SyntaxError):
                pass
        factor_defaults[fid] = defaults

# Validate and fix YAML defaults
mismatches = []
for yp in sorted(CATALOG_DIR.glob("*.yaml")):
    with open(yp) as f:
        data = yaml.safe_load(f) or {}
    modified = False
    for fid, entry in data.items():
        yaml_params = entry.get("params", {})
        code_defaults = factor_defaults.get(fid, {})
        for pname in list(yaml_params.keys()):
            yaml_default = yaml_params[pname].get("default")
            code_default = code_defaults.get(pname)
            if code_default is not None and yaml_default != code_default:
                mismatches.append((fid, pname, yaml_default, code_default))
                yaml_params[pname]["default"] = code_default
                # Fix invalid ranges
                rng = yaml_params[pname].get("range")
                if rng and len(rng) == 2 and rng[0] > rng[1]:
                    del yaml_params[pname]["range"]
                modified = True

        # Remove empty params dict
        if yaml_params and not any(True for _ in yaml_params.values() if _):
            del entry["params"]
        if yaml_params == {}:
            del entry["params"]

    if modified:
        with open(yp, "w") as f:
            yaml.dump(data, f, default_flow_style=None, sort_keys=False, allow_unicode=True, width=120)

if mismatches:
    print(f"Fixed {len(mismatches)} default mismatches:")
    for fid, pname, yaml_def, code_def in mismatches:
        print(f"  {fid}/{pname}: YAML={yaml_def} -> code={code_def}")
else:
    print("All YAML defaults match code defaults")
