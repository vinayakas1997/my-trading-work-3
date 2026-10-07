# Vigorous LLM testing

**Status: checkpoint 01 (`forecast_skill`) run for real, 2026-09-22.**
Grounding in `00-explanation.md`. Real LLM endpoint stood up
(`hindsight-llm`, llama.cpp `b11065`, `Qwen3.5-4B-Q4_K_M.gguf`, local
Docker container). All 5 checkpoint-01 trials sent to it using the
**exact real production call settings** — see
`checkpoints/01-checkpoint-forecast_skill/00-checkpoint-info.md`'s
CRITICAL FINDING: 4 of 5 trials never converged to an answer at all
under those real settings (the model got stuck in an unbounded
"thinking" loop and burned the entire real 8000-token budget without
emitting a final answer) — a real, severe reliability finding, not a
theoretical one. A secondary thinking-disabled pass (not how production
calls it) got real answers for the underlying business-logic questions;
worst result there: **trial 04 (prompt injection) is a confirmed,
exact-match exploit** — an instruction embedded in an `angle_digest`
field fully overrode the system prompt.
Checkpoint 02 (screener) not yet run.

## The idea, in one paragraph

Before trusting any test of whether the LLM reaches the *correct*
decision, there has to be a cheaper, earlier check that a single call
behaves at all: same fixed input, called repeatedly, does it come back in
reasonable time, does it respect its own timeout, does it stay inside
context, and does it come back the same way twice (no garbage, no verdict
flipping on identical input). Only once that's clean is a full
known-correct-answer scenario test actually trustworthy — otherwise a
scenario "failure" could just as easily be sampling noise or a silent
timeout as a real reasoning bug.

## Where this came from

Came out of a conversation about the system being strong mechanically but
never having tested the LLM decision layer's own consistency. Reading the
existing code to ground that conversation found this isn't a fresh
problem — `project-understanding/04-situation-test/llm-scenarios-test/`
already has all 5 planned scenarios built and passing (15 behavior
tests), but every one runs against a scripted, canned `ScriptedLLM`, never
a real model call. That folder's own README already names "swap in a real
LLM call" as its next, not-yet-started step. This folder is the specific
prerequisite work that swap needs — not a parallel idea.

## What's in this folder

- **`00-explanation.md`** — the detailed writeup:
  1. The two-stage principle (this folder first, then the real-LLM swap
     in `llm-scenarios-test/`) and why the order matters.
  2. The four things being checked — response time, timeout, context
     length, output consistency — each grounded in real file/line
     citations from `vinu-infra/llm/`, `vinu-agent/agent/llm.py`, and
     `vinu-agent/agent/loop.py`.
  3. **Two real gaps found just from reading the code**, not from running
     anything yet: a real timeout (`ReadTimeout`) gets zero retries while
     a dropped connection gets a full retry budget, and the `outcome`
     field's documented `"timeout"` value is never actually set —
     `telemetry.db` currently can't distinguish a slow model from a dead
     endpoint. Also: the shared client (`vinu-infra/llm/client.py`) has
     no context-window awareness at all, unlike `vinu-agent`'s own
     tool-calling loop, which already had to fix a real incident here
     (a hardcoded `128000` against a real `32000`-token model).
  4. The proposed harness shape (fixed input, N repeated real calls,
     deliberate timeout/oversized-prompt edge cases, cross-checked
     against `telemetry.db`) — not yet built.
  5. A mermaid call-site map showing **two structurally different LLM
     paths**: Path A (`vinu-agent`'s 5 team loops —
     `screener`/`research`/`risk_gatekeeper`/`capital_allocator`/
     `thesis_intake`, each own per-provider retry, bypasses the shared
     client) vs Path B (`forecast_skill.py::generate_forecast`, one
     direct call through the shared `vinu-infra/llm/client.py`, the same
     path all of section 2's findings apply to). Stage 1 testing has to
     cover both separately — they don't share a retry/timeout/telemetry
     implementation.

## Current state

Nothing built. This is the explanation/grounding pass only — next step is
picking the first real call site (`forecast_skill.py::generate_forecast`
is the recommendation in `00-explanation.md`, section 3) and a real fixed
input to test it against.
