"""The reflection layer's analysts -- see missing-pieces-of-system/
maturity-agentic-system/thinking-1/02-decided-pattern/. Each module here
implements the shared `run(data_root_paths, service_clients) -> list[Finding]`
interface (02-analyst-interface.md); `decision_process` (analysis D) is
the first one built, per 05-to-do.md's recommended build order.

Lives in its own `vinu-reflection` service/package (not inside
vinu-agent) -- see 05-to-do.md #5's 2026-09-19 update for why, and why
that's a cheap decision to reverse later if it turns out not to be
worth the mount overhead: every analyst here only ever reads other
services' storage classes in-process (same posture
vinu-agent/broker/research_link.py already established for
vinu-research), so moving this package back inside vinu-agent later is
a folder move, not a rewrite.
"""
