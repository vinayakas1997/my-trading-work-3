# BUG-05 🔴 Simulator exec() Fails on LLM Code Without Imports

**Component:** `vinu-simulator`
**Files Changed:** `vinu-simulator/vinu_simulator/service.py`
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

The LLM generates strategy code starting with `class UserStrategy(BaseStrategy):` but
**omits required imports** (`from __future__ import annotations`, `import pandas as pd`,
`import numpy as np`, `from vinu_simulator.engine.strategies import BaseStrategy`).
When the simulator's `exec()` runs this code, it fails with:
- `NameError: name 'BaseStrategy' is not defined`
- `NameError: name 'pd' is not defined`

This caused `POST /research/run` to silently produce `total_iterations=0` because the
iteration exception was caught and the loop stopped.

## Root Cause

The LLM generation prompt (`LLM_GEN_SYSTEM_PROMPT`) tells the LLM to include imports,
but the LLM frequently ignores this instruction, especially during refinement (iteration 2+)
where it focuses on modifying the logic rather than preserving boilerplate.

Additionally, the system prompt had `from __future__ import annotations` (without `from`),
which is not a valid import and the LLM copied it verbatim.

## Suggested Fix

Prepend required imports before `exec()` in the simulator, regardless of whether the
LLM included them or not.

## Actual Fix

Added import prepending logic in `simulator/service.py:242-249`:

```python
REQUIRED_IMPORTS = [
    "from __future__ import annotations",
    "import pandas as pd",
    "import numpy as np",
    "from vinu_simulator.engine.strategies import BaseStrategy",
]

# Prepend required imports if code doesn't start with them
if not strategy_code.startswith(("from ", "import ")):
    strategy_code = "\n".join(REQUIRED_IMPORTS) + "\n\n" + strategy_code
```

Also fixed the system prompt in `llm_generator.py` to use valid Python syntax:
```python
# Before
"from __future__ import annotations\n"

# After
"from __future__ import annotations\n"
```
(Note: this was already correct in the prompt, the issue was LLM non-compliance)

## Verification

1. Generate strategy code without imports
2. Confirm simulator prepends required imports
3. Confirm `exec()` succeeds
4. Run full research pipeline — confirm `total_iterations > 0`

## Lessons Learned

- Never trust LLM to include boilerplate — always inject it at the execution layer
- The system prompt is a suggestion, not a guarantee
- `exec()` requires the namespace to contain ALL referenced symbols
- Silent catch-all exception handlers in the research loop hide these errors
