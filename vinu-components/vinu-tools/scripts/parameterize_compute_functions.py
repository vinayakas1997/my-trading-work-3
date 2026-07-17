"""Replace hardcoded numeric constants in compute() with kwargs lookups.

Reads YAML params for each factor, finds the corresponding hardcoded
integer values in the Python compute() function body, and replaces them
with kwargs.get('param_name', default).

Uses simple integer literal matching within the compute() function body.
Params with the same default value consume occurrences in order.

Usage:
    python scripts/parameterize_compute_functions.py
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


def _find_compute_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Return (start_line, end_line) of the compute() function."""
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^def compute\(", line):
            start = i
            break
    if start is None:
        return None
    indent = len(lines[start]) - len(lines[start].lstrip())
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith('"""') and not stripped.startswith("'''"):
            ci = len(lines[i]) - len(lines[i].lstrip())
            if ci <= indent and (stripped.startswith("def ") or stripped.startswith("@")):
                return (start, i)
    return (start, len(lines))


def _find_int_literals(body_lines: list[str]) -> list[tuple[int, int, int, int]]:
    """Find all integer literals >= 1 in the compute body.

    Returns [(line_idx, col_start, col_end, value)].
    """
    result = []
    # Skip lines that are comments, decorators, or the def line itself
    for line_idx, l in enumerate(body_lines):
        stripped = l.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if stripped.startswith("def ") or stripped.startswith("@") or stripped.startswith("return"):
            # Don't skip return lines — they often contain numeric constants
            if stripped.startswith("def ") or stripped.startswith("@") or stripped.startswith("return type:"):
                if stripped.startswith("def ") or stripped.startswith("@") or "type:" in stripped:
                    continue

        # Find integers not part of larger numbers, floats, or identifiers
        for m in re.finditer(r'(?<!\w)(\d+)(?!\w)', l):
            # Skip values used as indices/slices
            val = int(m.group(1))
            if val < 1:
                continue
            # Skip values that are part of larger constructs
            before = l[:m.start()].rstrip()
            after = l[m.end():].lstrip()

            # Skip if it's inside a string
            quote_count = l[:m.start()].count('"') + l[:m.start()].count("'")
            if quote_count % 2 != 0:
                continue

            result.append((line_idx, m.start(), m.end(), val))

    return result


def _parameterize_factor(source: str, factor_id: str, params: dict) -> tuple[str, int]:
    lines = source.split("\n")
    bounds = _find_compute_bounds(lines)
    if bounds is None:
        print(f"  ? no compute() function found for {factor_id}")
        return source, 0

    cstart, cend = bounds
    body = lines[cstart:cend]
    literals = _find_int_literals(body)

    if not literals:
        return source, 0

    # Filter out the def compute(panel...) line itself (line 0 of body)
    literals = [(li, cs, ce, v) for li, cs, ce, v in literals if li > 0]

    # Group literals by value
    by_value: dict[int, list[tuple[int, int, int, int]]] = {}
    for li, cs, ce, v in literals:
        by_value.setdefault(v, []).append((li, cs, ce, v))

    # Sort params by name for deterministic assignment
    sorted_params = sorted(params.items(), key=lambda x: x[0])

    replacements = 0
    consumed: dict[int, int] = {}

    # Group replacements by (abs_line) to apply simultaneously right-to-left
    replacements_by_line: dict[int, list[tuple[int, int, int, str]]] = {}

    for param_name, pdef in sorted_params:
        default = pdef.get("default")
        if not isinstance(default, (int, float)):
            continue
        if isinstance(default, float) and default == int(default):
            default = int(default)
        if not isinstance(default, int) or default < 1:
            continue

        n = consumed.get(default, 0)
        if default not in by_value or n >= len(by_value[default]):
            consumed[default] = n + 1
            continue

        line_idx, col_start, col_end, val = by_value[default][n]
        consumed[default] = n + 1

        abs_line = cstart + line_idx
        replacement = f"kwargs.get('{param_name}', {val})"
        replacements_by_line.setdefault(abs_line, []).append((col_start, col_end, val, replacement))
        replacements += 1

    # Apply replacements right-to-left per line to preserve positions
    for abs_line, reps in replacements_by_line.items():
        # Sort right-to-left
        reps.sort(key=lambda x: -x[0])
        line = lines[abs_line]
        for col_start, col_end, val, rep in reps:
            line = line[:col_start] + rep + line[col_end:]
        lines[abs_line] = line

    return "\n".join(lines), replacements


def main():
    factor_params: dict[str, dict] = {}
    for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for fid, entry in data.items():
            ps = entry.get("params")
            if ps and isinstance(ps, dict) and any(
                isinstance(v, dict) and "default" in v for v in ps.values()
            ):
                factor_params[fid] = ps

    print(f"Found {len(factor_params)} factors with params")

    ID_RE = re.compile(r"""['"]id['"]\s*:\s*['"]([^'"]+)['"]""")
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

    total_rep = 0
    mod_files = 0

    for fid in sorted(factor_params):
        if fid not in id_to_file:
            print(f"  ? no file for {fid}")
            continue

        fpath = id_to_file[fid]
        source = fpath.read_text()

        if "kwargs.get(" in source:
            continue

        modified, count = _parameterize_factor(source, fid, factor_params[fid])

        if count > 0:
            fpath.write_text(modified)
            mod_files += 1
            total_rep += count
            print(f"  {fid}: {count} replacements")

    print(f"\nModified {mod_files} files with {total_rep} total replacements")


if __name__ == "__main__":
    main()
