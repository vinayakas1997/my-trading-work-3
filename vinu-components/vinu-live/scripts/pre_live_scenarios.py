#!/usr/bin/env python3
"""Run the pre-live acceptance scenarios as a standalone gate -- meant to
be run by an operator once before flipping real capital on, not just
quietly passing in CI. Thin wrapper around `tests/test_pre_live_scenarios.py`
(pytest -v) rather than a second copy of the scenario logic -- one set of
scenarios, two ways to run them.

Usage:
    python scripts/pre_live_scenarios.py

Exit code is pytest's own: 0 means every scenario's known-correct answer
held against the real orchestrator code; non-zero means something in the
entry / trailing-stop / invalidation-exit chain did not behave as the
scenario said it must.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCENARIOS = _ROOT / "tests" / "test_pre_live_scenarios.py"


def main() -> int:
    print("=" * 72)
    print("vinu-live pre-live acceptance scenarios")
    print("Deterministic, known-answer checks -- no LLM, no real network.")
    print("=" * 72)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", str(_SCENARIOS)],
        cwd=str(_ROOT),
    )
    print("=" * 72)
    if result.returncode == 0:
        print("PASS -- every scenario's known-correct answer held.")
    else:
        print("FAIL -- see the failures above before trusting this build with real capital.")
    print("=" * 72)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
