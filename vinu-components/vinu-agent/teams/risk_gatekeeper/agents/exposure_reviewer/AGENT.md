---
name: exposure_reviewer
role: exposure-reviewer
prompt_file: prompt.md
depends_on: []
tools: [get_portfolio, get_portfolio_concentration, compute_position_size]
skills: []
---

Checks a strategy artifact's proposed exposure against the current real
portfolio (get_portfolio) -- position sizing vs. account size,
correlation to what's already open, buying power. Also checks
vinu-portfolio's own real, correlation-aware target-weight view
(get_portfolio_concentration) -- the same engine capital_allocator's
funding sizing already relies on, previously not consulted here at all.
Returns APPROVED/REJECTED with the specific rule that drove it. Was the
`risk_gatekeeper` design's `exposure_reviewer`, previously blocked on
"no real position data" -- get_portfolio (broker/alpaca.py) already
provides that, so the blocker no longer applies.
