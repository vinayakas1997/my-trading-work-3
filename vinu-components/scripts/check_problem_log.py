"""Check the problem log: every guard it names must still exist, and entries without a guard are listed.

    python scripts/check_problem_log.py            # report; exit 1 if a named test is missing
    python scripts/check_problem_log.py --strict   # also exit 1 while any entry is FIX, NO TEST / PARTIAL

Reads Proper-Project-Implementation/04-problem-log-and-guard-tests/problem-log.md. A guard is written `path/to/test_file.py::test_name`
(relative to vinu-components); the check is a text search for `def test_name` in that file, so it needs no test run.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

COMPONENTS = Path(__file__).resolve().parents[1]
LOG = COMPONENTS.parent / "Proper-Project-Implementation" / "04-problem-log-and-guard-tests" / "problem-log.md"
GUARD = re.compile(r"`([\w./\-]+\.py)::(\w+)`")


def main(strict: bool) -> int:
    text = LOG.read_text(encoding="utf-8")
    entries = re.split(r"\n### (P\d+) ", text)[1:]
    missing, counts, open_entries = [], {}, []
    for i in range(0, len(entries), 2):
        pid, body = entries[i], re.split(r"\n## ", entries[i + 1])[0]     # an entry ends at the next section heading
        title = body.splitlines()[0]
        status = (re.search(r"\*\*Status:\*\*\s*([A-Z, ]+?)(?:\s*\(|$|\n)", body) or [None, "UNKNOWN"])[1].strip()
        counts[status] = counts.get(status, 0) + 1
        if status != "GUARDED":
            open_entries.append((pid, status, title))
        for path, name in GUARD.findall(body):
            f = COMPONENTS / path
            if not f.is_file() or not re.search(rf"def {re.escape(name)}\b", f.read_text(encoding="utf-8", errors="replace")):
                missing.append((pid, path, name))
    print(f"entries: {sum(counts.values())}  " + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    if missing:
        print("\nNAMED GUARD NOT FOUND (renamed, moved or deleted):")
        for pid, path, name in missing:
            print(f"  {pid}  {path}::{name}")
    if open_entries:
        print("\nNOT FULLY GUARDED:")
        for pid, status, title in open_entries:
            print(f"  {pid}  {status:<14} {title}")
    if missing or (strict and open_entries):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main("--strict" in sys.argv))
