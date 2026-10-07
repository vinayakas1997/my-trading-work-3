# Checkpoints — index

One subfolder per real LLM call site identified in `../00-explanation.md`
section 5 (the call-site map). Six checkpoints, matching the six real call
sites, not an arbitrary number:

| # | Checkpoint | Real call site | LLM path |
|---|---|---|---|
| 01 | `forecast_skill` | `vinu-research/vinu_research/forecast_skill.py:176` `generate_forecast` | Path B — shared `vinu-infra/llm/client.py` |
| 02 | `screener` | `vinu-agent/teams/screener/` (Summary Agent) | Path A — team loop |
| 03 | `research` | `vinu-agent/teams/research/` (idea_generator + Researcher/Executor) | Path A — team loop |
| 04 | `risk_gatekeeper` | `vinu-agent/teams/risk_gatekeeper/` | Path A — team loop |
| 05 | `capital_allocator` | `vinu-agent/teams/capital_allocator/` | Path A — team loop |
| 06 | `thesis_intake` | `vinu-agent/teams/thesis_intake/` | Path A — team loop |

Numbered in the order testing should actually happen, per
`00-explanation.md` section 3/5's reasoning — `forecast_skill` first
because it's a single isolable call with one fixed prompt shape, not a
multi-turn team loop where "the response" is really an unpredictable
number of calls.

## Two different things a "trial" means here

**Checkpoint 01 (`forecast_skill`, Path B)** — a trial is literally what
the template implies: one fixed system+user prompt, sent directly, one
response. This is the simple case.

**Checkpoints 02–06 (the five team loops, Path A)** — these are
multi-turn, tool-calling conversations (a manager `AgentLoop` delegating
to one or more specialist `AgentLoop`s via `delegate_to_agent`). There is
no single "the prompt" for a whole team cycle. A trial here instead:

- Holds the **manager's real system prompt** (`manager_prompt.md`,
  verbatim) and a **fixed task string** (what the manager is told to do)
  constant.
- **Scripts the specialist's response** the manager delegates to, the
  same way `llm-scenarios-test/_scenario_helpers.py`'s `ScriptedLLM`
  already does elsewhere in this project (a real, existing precedent, not
  a new technique invented here) — so the trial tests the **manager's own
  real LLM reasoning** over a specific, adversarial specialist result, in
  isolation from whatever the specialist's own LLM would have said.
- Each checkpoint 02–06's `00-checkpoint-info.md` says explicitly which
  specialist gets scripted and what its scripted response contains.

This means checkpoints 02–06 only test **one link in each team's chain**
per trial (usually the manager, reacting to a scripted specialist) — not
full team behavior end-to-end with every specialist also live. Testing
every specialist's own reasoning independently, and eventually the whole
team with nothing scripted, is real follow-on work once single-link
trials are clean — same "Stage 1 before Stage 2" ordering discussed in
`00-explanation.md` section 1, just one level more granular.

## Status

All six checkpoint folders and their first trial(s) are written and
ready to run. Nothing has actually been executed yet — every trial's
"Response received" section is empty, pending a real, reachable LLM
endpoint (see the parent folder's `README.md` for the current container
blocker).
