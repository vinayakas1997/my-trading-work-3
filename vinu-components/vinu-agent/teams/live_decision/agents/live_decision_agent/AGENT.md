---
name: live_decision_agent
role: live-decision-maker
prompt_file: prompt.md
depends_on: []
# get_move_evidence (Track 2) is not in this list -- checked directly,
# there is no such agent tool yet. Track 2 moves still reach this agent
# through get_live_decision_context's `unconfirmed_moves[]` field (GET
# vinu-research's /research/unconfirmed-moves), so this is coverage, not
# a gap -- register a dedicated tool here only once one exists, not
# before, since an unregistered tool name would break this agent's tool
# resolution.
tools: [get_live_decision_context, get_signal_evidence, get_reflection_synthesis]
skills: []
---

Decides whether to act on a (ticker, strategy) pair vinu-live's
candle-close poller + stage/state tracker have already marked
`ready_to_execute` -- reads the current live indicator snapshot, the
strategy's precondition/must-condition definition, and historical
must-condition evidence for this ticker, then recommends
EXECUTE/SKIP/EXTEND_GRACE_WINDOW. Structurally cannot place an order or
write to any store: no execution or write tool is in this list (same
"enforced by omission, not a prompt instruction" pattern
thesis_intake/theory_reviewer already uses for backtests).

Also handles the exit-mechanism fix's review mode (missing-pieces-of-
system/new-theory-of-trading/system-wide-audit-and-design/
04-synthesis-built-vs-missing-2026-09-28.md): on a periodic cadence for
an already-open live_decision position, recommends HOLD/EXIT using the
same evidence sources -- prompt.md's own "Review mode" section, selected
by the task text carrying `Mode: POSITION_REVIEW`. Same tool list, same
"cannot place an order, only recommend" posture either way.
