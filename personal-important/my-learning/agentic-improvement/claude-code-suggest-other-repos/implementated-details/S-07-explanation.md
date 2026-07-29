# S-07: Goal Budget & Compliance Guardrail — Explanation & Status

## What It Is

Adds spend-and-time budgets to research goals and validates them before execution, preventing runaway LLM costs or excessive runtime.

## Components

1. **`Goal` dataclass in `models.py`** — extended with four budget fields: `llm_calls_budget`, `llm_calls_used`, `time_budget_seconds`, `time_used_seconds`. Each goal expresses its own limits and tracks consumption.

2. **`_has_violated_goal_constraints()` in `service.py`** — checks if any budget (LLM calls or wall-clock time) is exceeded against the goal's allowance. Returns `True` if the goal is over budget.

3. **Live-execution pattern check** — `run_research()` scans user ideas for keywords like `"place order"`, `"execute trade"`, etc. and flags them to prevent accidental live trading during research.

4. **Goal budget wired into `run_research()`** — `_has_violated_goal_constraints()` is called before research starts. If constraints are violated, a warning is logged and the function exits early, avoiding wasted LLM calls.

## Current Status: ✅ IMPLEMENTED

Budget-aware goals prevent runaway execution; live-trade keywords are flagged early.
