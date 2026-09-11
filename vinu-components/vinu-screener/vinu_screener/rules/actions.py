"""Stage B (B16): `actions` JSON bag on a rule, ported from FinceptTerminal's
`ScanWatch` (`actions.toast`/`actions.providers` fan-out on the watch object
itself, per `13-fincept-terminal.md`). Each screener rule independently
picks which channel(s) a fire should reach without a new schema per
notification channel — `actions: {"toast": true, "providers": {"telegram":
true, "discord": false}}`, same shape FinceptTerminal's own watch row uses.

Kept strictly decoupled per B15: this module only *resolves* what a rule
wants (a small, declarative "what should happen" description) — it never
sends anything itself. Dispatching to Telegram/Discord/a toast is the
caller's job (`vinu-agent`'s existing notify paths, or whatever consumes
`vinu-screener`'s fires), same boundary FinceptTerminal's own comment
describes as "fully decoupled from evaluation."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionsConfig:
    toast: bool = True                              # FinceptTerminal's own default
    providers: dict[str, bool] = field(default_factory=dict)  # e.g. {"telegram": True, "discord": False}

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "ActionsConfig":
        raw = raw or {}
        return cls(
            toast=bool(raw.get("toast", True)),
            providers=dict(raw.get("providers", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"toast": self.toast, "providers": dict(self.providers)}


def resolve_targets(actions: ActionsConfig) -> list[str]:
    """The enabled dispatch targets for one fire -- `"toast"` plus every
    provider name whose flag is truthy. The caller maps these names to
    actual senders; this function never knows how to send anything."""
    targets = []
    if actions.toast:
        targets.append("toast")
    targets.extend(name for name, enabled in actions.providers.items() if enabled)
    return targets
