"""Second-pass param wiring: handle edge cases missed by the first pass.

Strategy:
  1. Map each YAML param to its likely code occurrence.
  2. If two YAML params map to the same code occurrence, the extras are spurious — remove from YAML.
  3. available=0 (value not in code) → remove from YAML or flag for manual review.
  4. available=1 with no conflict → wire it (replace rightmost occurrence).
  5. available>=2 (multiple matches) → try name-based matching, else flag.

Usage:
    python scripts/parameterize_compute_functions_pass2.py [--dry-run] [--remove-spurious]
"""

from __future__ import annotations

import re
import sys
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

# Pre-load all YAML catalogs
_ALL_YAML: dict[str, dict] = {}  # factor_id -> (yaml_data, yaml_path)
for yp in sorted(CATALOG_DIR.glob("*.yaml")):
    with open(yp) as f:
        data = yaml.safe_load(f) or {}
    for fid in data:
        _ALL_YAML[fid] = (data, yp)


def find_source_path(factor_id: str) -> Path | None:
    entry_dict, _ = _ALL_YAML.get(factor_id, ({}, None))
    source = entry_dict.get(factor_id, {}).get("source", "")
    if source:
        return REPO / "vinu_tools" / "compute" / source
    return None


def load_yaml(factor_id: str) -> tuple[dict | None, Path | None]:
    return _ALL_YAML.get(factor_id, (None, None))


# Build mapping: group -> [(source_file_path, factor_id)]
def build_mapping():
    mapping = {}
    for group, d in FACTOR_DIRS.items():
        if not d.exists():
            continue
        mapping[group] = []
        for py_file in sorted(d.glob("*.py")):
            if py_file.stem == "__init__":
                continue
            m = ID_RE.search(py_file.read_text())
            if m:
                mapping[group].append((py_file, m.group(1)))
    return mapping


def get_wired_params(content: str) -> set[str]:
    return {m.group(1) for m in KWARG_GET_RE.finditer(content)}


def find_value_in_code(body: str, default) -> list[tuple[int, int, str]]:
    """Find all occurrences of `default` in the code body.

    Returns [(start_pos, end_pos, matched_text), ...]
    """
    pattern = re.compile(r'(?<!\w)' + re.escape(str(default)) + r'(?!\w)')
    return [(m.start(), m.end(), m.group()) for m in pattern.finditer(body)]


def is_already_wired(body: str, pos: int) -> bool:
    """Check if the occurrence at `pos` is already inside a kwargs.get() call."""
    # Look backwards for 'kwargs.get(' before this position
    before = body[max(0, pos - 200):pos]
    last_kwargs = before.rfind("kwargs.get('")
    if last_kwargs < 0:
        return False
    # Check if there's a closing paren between kwargs.get and this position
    between = before[last_kwargs:]
    if between.count(")") > between.count("("):
        return False  # already closed
    return True


def try_name_match(body: str, param_name: str, default) -> int | None:
    """Try to find the value by name pattern (e.g., window=5, window = 5).

    Returns the start position of the value if found, None otherwise.
    """
    # Try patterns: param_name=value, param_name = value, param_name: value
    patterns = [
        re.compile(rf'\b{param_name}\s*=\s*{re.escape(str(default))}\b'),
        re.compile(rf'\b{param_name}\s*:\s*{re.escape(str(default))}\b'),
    ]
    for p in patterns:
        m = p.search(body)
        if m:
            # Find the position of the value within the match
            val_match = re.search(rf'(?<!\w){re.escape(str(default))}(?!\w)', m.group())
            if val_match:
                return m.start() + val_match.start()
    return None


def wire_param_at_pos(body: str, pos: int, param_name: str, default) -> str:
    """Insert kwargs.get() at the given position."""
    old_piece = body[pos:pos + len(str(default))]
    new_piece = f"kwargs.get('{param_name}', {old_piece})"
    return body[:pos] + new_piece + body[pos + len(str(default)):]


def remove_from_yaml(factor_id: str, param_name: str) -> bool:
    """Remove a parameter from YAML catalog."""
    data, yaml_path = load_yaml(factor_id)
    if data is None or yaml_path is None:
        return False
    if factor_id not in data:
        return False
    params = data[factor_id].get("params", {})
    if param_name not in params:
        return False
    del params[param_name]
    if not params:
        del data[factor_id]["params"]
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=None, sort_keys=False, allow_unicode=True, width=120)
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    remove_spurious = "--remove-spurious" in sys.argv

    mapping = build_mapping()

    fixed = 0
    cant_fix = 0
    removed = 0
    zero_available = []
    multi_available = []
    conflict_unwired = []  # param whose value is already wired to a different param
    fixed_list = []

    for group, entries in mapping.items():
        for fpath, factor_id in entries:
            content = fpath.read_text()
            body_start = content.find("def compute(")
            if body_start < 0:
                continue
            body = content[body_start:]

            ydata, yaml_path = load_yaml(factor_id)
            if ydata is None:
                continue

            entry_data = ydata.get(factor_id, {})
            params = entry_data.get("params", {})
            if not params:
                continue

            wired = get_wired_params(content)

            for pname, pinfo in list(params.items()):
                if pname in wired:
                    continue

                default = pinfo.get("default")

                # Find all occurrences of the default value in the body
                matches = find_value_in_code(body, default)
                # Filter out matches that are already wired
                available = [(s, e, t) for s, e, t in matches if not is_already_wired(body, s)]
                count = len(available)

                if count == 0:
                    # All occurrences are already wired to other params
                    if matches and all(is_already_wired(body, s) for s, _, _ in matches):
                        conflict_unwired.append((factor_id, pname, default))
                        if remove_spurious and not dry_run:
                            if remove_from_yaml(factor_id, pname):
                                removed += 1
                    else:
                        zero_available.append((factor_id, pname, default))
                    cant_fix += 1
                elif count == 1:
                    # Try name-based match first
                    pos = try_name_match(body, pname, default)
                    if pos is None:
                        pos = available[0][0]  # fall back to the only available occurrence
                    if not dry_run:
                        new_body = wire_param_at_pos(body, pos, pname, default)
                        fpath.write_text(content[:body_start] + new_body)
                        fixed_list.append((factor_id, pname, default))
                        fixed += 1
                    else:
                        fixed += 1
                else:
                    # Multiple available occurrences — try name-based match
                    pos = try_name_match(body, pname, default)
                    if pos is not None:
                        if not dry_run:
                            new_body = wire_param_at_pos(body, pos, pname, default)
                            fpath.write_text(content[:body_start] + new_body)
                            fixed_list.append((factor_id, pname, default))
                            fixed += 1
                        else:
                            fixed += 1
                    else:
                        multi_available.append((factor_id, pname, default, count))
                        cant_fix += 1

    print(f"Pass 2 results:")
    print(f"  Fixed: {fixed}")
    print(f"  Removed (spurious): {removed}")
    print(f"  Still unwired: {cant_fix}")

    if conflict_unwired:
        print(f"\n--- Conflict: value already wired for another param (spurious YAML param) ---")
        for fid, pname, default in sorted(conflict_unwired):
            print(f"  {fid}/{pname}={default}")

    if zero_available:
        collapsible = [x for x in zero_available if x[2] not in (0, 1)]
        trivial = [x for x in zero_available if x[2] in (0, 1)]
        print(f"\n--- available=0 (default not found in code body) ---")
        for fid, pname, default in sorted(collapsible):
            print(f"  {fid}/{pname}={default}")
        if trivial:
            print(f"  ... plus {len(trivial)} params with default=0 or 1")

    if multi_available:
        print(f"\n--- available>=2 (multiple candidates in code body) ---")
        for fid, pname, default, cnt in sorted(multi_available):
            print(f"  {fid}/{pname}={default} (found {cnt}x)")

    if dry_run:
        print(f"\n(Dry run — no files modified)")
    else:
        print(f"\nModified {fixed} Python files, removed {removed} YAML params")


if __name__ == "__main__":
    main()
