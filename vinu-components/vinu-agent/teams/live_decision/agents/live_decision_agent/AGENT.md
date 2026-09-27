---
name: live_decision_agent
role: live-decision-maker
prompt_file: prompt.md
depends_on: []
# get_move_evidence (Track 2) is not in this list -- checked directly,
# it does not exist as a real tool yet (Track 2 is design-only, see
# ../../../../missing-pieces-of-system/new-theory-of-trading/
# how-to-use-29th-angle/05-track2-how-to-ask.md). Add it here once it's
# built, not before -- an unregistered tool name would break this
# agent's tool resolution.
tools: [get_live_decision_context, get_signal_evidence]
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
