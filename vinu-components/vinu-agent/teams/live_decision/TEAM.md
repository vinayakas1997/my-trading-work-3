---
name: live_decision
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---

Live Decision team: point 5 of missing-pieces-of-system/new-theory-of-
trading/system-wide-audit-and-design/reverse-engineering/. Reached when
vinu-live's candle-close poller + stage/state tracker (points 2-4,
already built) mark a (ticker, strategy) pair `ready_to_execute` -- a
must-condition has genuinely fired (and, if the strategy has them, its
confirmation conditions already held within their grace window). This
team's one job: decide whether to actually act on it, using real
evidence, not just because the condition fired. Writes no orders itself
-- the tool list structurally excludes any execution tool, same "writes
no code/orders, ever, enforced by omission" pattern thesis_intake's
theory_reviewer already uses for backtests. The decision this team
returns is a recommendation; vinu-live's own execution path (still
subject to its own risk-limit checks, see item #24 in
../../missing-pieces-of-system/new-theory-of-trading/system-wide-audit-
and-design/02-open-questions-strategy-and-simulation.md) is what
actually places anything.
