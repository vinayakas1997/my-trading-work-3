---
task: 05-position-sizing-risk-gatekeeper.md
status: complete
---

# Status: task 05 — add a real position-sizing formula to `risk_gatekeeper`

## Files touched

- `vinu-agent/vinu_agent/agent/position_sizing.py` — NEW: pure deterministic sizing math
  (`full_kelly_fraction`, `fractional_kelly_size`, `fixed_fractional_size`, `atr_stop_size`,
  `compute_position_size`).
- `vinu-agent/vinu_agent/tools/position_sizing_tool.py` — NEW: `ComputePositionSizeTool` (name
  `compute_position_size`), a thin read-only wrapper over the pure math.
- `vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py` — recomputes the formula size from the verdict's
  recorded `sizing_inputs` and stores `min(formula, headroom cap)`; records the inputs in the PEND ledger event.
- `vinu-agent/vinu_agent/config.py` — new `AgentConfig` knobs: `position_sizing_method` ("fractional_kelly"),
  `kelly_fraction` (0.25), `risk_per_trade_pct` (0.02), `atr_stop_multiple` (2.0), all env-backed.
- `vinu-agent/vinu_agent/tools/__init__.py` — `build_registry` accepts `config` and injects `tool._config`
  (opt-in, nothing forced on existing tools).
- `vinu-agent/vinu_agent/agent/scheduler_workers.py` — passes `config=service.config` into `build_registry`.
- `vinu-agent/teams/risk_gatekeeper/manager_prompt.md` — final JSON now includes `sizing_inputs`; mandates
  forwarding the formula output exactly.
- `vinu-agent/teams/risk_gatekeeper/agents/exposure_reviewer/AGENT.md` — added `compute_position_size` to tools.
- `vinu-agent/teams/risk_gatekeeper/agents/exposure_reviewer/prompt.md` — two-step sizing: headroom cap
  (existing) + formula size via the tool (deterministic); never Kelly in the head; fixed-fractional fallback
  when edge inputs aren't available (never invent an edge).
- `vinu-agent/tests/test_position_sizing.py` — NEW: 24 tests.

## What I did

- Confirmed the gap: `risk_gatekeeper`'s `exposure_reviewer` computed only a concentration-limit headroom
  (`approved_size` = cap), never an edge-based recommended size; `apply_risk_gatekeeper_verdict` stored
  whatever the LLM reported, formula-less. `approved_size` already existed on `Artifact` (reused, no new field).
- Ported the math from `jarvis-trading-bot/risk_manager.py`'s `kelly_criterion` (same guards: win_rate ≤ 0 /
  ≥ 1 or non-positive payoff → 0; f* = (p·b − q)/b, clamped ≥ 0) and `calculate_position_size` (fixed-
  fractional "1-2% rule", plus the ATR stop = 2·ATR risk-per-unit variant). Implemented as pure, testable
  functions — deterministic math, never LLM arithmetic.
- Wired it so the verdict path is authoritative: the manager records `sizing_inputs` (from the tool's real
  call), and the hook recomputes the formula deterministically and stores
  `min(formula_size, concentration_headroom)` — formula decides, cap bounds. No `sizing_inputs` (pre-task-05
  verdicts) → manager's number passes through unchanged (existing tests unmodified and passing).
- Made method/fraction configurable: `AgentConfig` knobs + env vars, injected via `build_registry(config=...)`;
  the tool falls back to `load_config()` (env) when nothing is injected (e.g. chat-session path).

## What is achieved

- `risk_gatekeeper`'s APPROVED path now carries a real, formula-derived size traceable to the exact inputs
  (win-rate, payoff ratio, equity, method, fraction) stored in the PEND ledger event — with zero/negative
  edge always yielding 0, and the headroom cap still enforced.

## Alignment with plan-justification

- Task's "not an LLM call" requirement is honored twice: the tool is the formula (LLM only supplies inputs),
  and the hook recomputes it deterministically from the recorded inputs before storing.
- Task's "make Kelly fraction / method configurable, not hardcoded" — done via AgentConfig + env.
- The recommendation (fractional Kelly 25-50%, ATR-normalized) is implemented as the default method
  (fractional_kelly @ 0.25) with fixed_fractional and atr_stop available as alternates — the design doc's
  open question is now a config switch, not a code change.

## Testing

- `python3 -m pytest vinu-agent/tests/test_position_sizing.py -q` → 24 passed (unit suite covers normal case,
  zero/negative-edge → no positive Kelly size, fixed-fractional comparison case, ATR fallback, tool config
  injection, hook capping + backward-compat).
- `python3 -m pytest vinu-agent/tests -q` → 830 passed (806 prior + 24 new).
- `python3 -m py_compile` clean on all edited modules.