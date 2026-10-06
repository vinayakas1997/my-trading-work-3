"""Who goes first. Callers name a PURPOSE; only this table turns it into a priority, so no service can mark its own
calls urgent and changing the order is a one-place edit. 1 is the most urgent.

An unknown purpose is rejected (a typo must not silently fall to some default priority).
"""
from __future__ import annotations

PURPOSE_PRIORITY: dict[str, int] = {
    # 1: a trading decision is waiting on this answer
    "live_decision": 1,
    "order_approval": 1,
    # 2: protecting capital: risk checks and live feedback
    "risk_gate": 2,
    "live_feedback": 2,
    # 3: research that produces strategies
    "strategy_writer": 3,
    "risk_critic": 3,
    "idea_generator": 3,
    "forecast_skill": 3,
    "research": 3,
    # 4: preparing context (planner, summaries, per-angle comprehension, news scoring)
    "planner": 4,
    "summary": 4,
    "angle_synthesis": 4,
    "news_sentiment": 4,
    # 5: nobody is waiting on it
    "reflection": 5,
    "hindsight": 5,
    "background": 5,
}

# A caller that does not name a purpose gets its usual one; a caller not listed here must name one.
CALLER_DEFAULT_PURPOSE: dict[str, str] = {
    "vinu-research": "research",
    "vinu-agent": "planner",
    "vinu-initial-analysis": "angle_synthesis",
    "vinu-news": "news_sentiment",
    "vinu-reflection": "reflection",
    "vinu-live": "live_decision",
    "vinu-portfolio": "risk_gate",
    "hindsight": "hindsight",
}


class UnknownPurpose(ValueError):
    pass


def resolve_purpose(caller: str, purpose: str | None) -> tuple[str, int]:
    """(purpose, priority) for a request, or UnknownPurpose with a message the caller can act on."""
    name = (purpose or "").strip() or CALLER_DEFAULT_PURPOSE.get((caller or "").strip(), "")
    if not name:
        raise UnknownPurpose(
            f"caller {caller!r} sent no X-Vinu-Purpose and has no default purpose; known purposes: {sorted(PURPOSE_PRIORITY)}"
        )
    if name not in PURPOSE_PRIORITY:
        raise UnknownPurpose(f"unknown purpose {name!r}; known purposes: {sorted(PURPOSE_PRIORITY)}")
    return name, PURPOSE_PRIORITY[name]
