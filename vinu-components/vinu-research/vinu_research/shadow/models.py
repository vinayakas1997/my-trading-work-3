from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShadowRule:
    rule_id: str
    human_text: str
    entry_condition: dict[str, Any] = field(default_factory=dict)
    exit_condition: dict[str, Any] = field(default_factory=dict)
    holding_days_range: tuple[float, float] = (0.0, 0.0)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "human_text": self.human_text,
            "entry_condition": self.entry_condition,
            "exit_condition": self.exit_condition,
            "holding_days_range": list(self.holding_days_range),
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ShadowRule:
        hdr = d.get("holding_days_range", [0.0, 0.0])
        if isinstance(hdr, list):
            hdr = (float(hdr[0]), float(hdr[1]))
        return cls(
            rule_id=d["rule_id"],
            human_text=d["human_text"],
            entry_condition=d.get("entry_condition", {}),
            exit_condition=d.get("exit_condition", {}),
            holding_days_range=hdr,
            weight=float(d.get("weight", 1.0)),
        )


@dataclass
class ShadowProfile:
    shadow_id: str
    journal_hash: str
    rules: list[ShadowRule] = field(default_factory=list)
    profile_text: str = ""
    preferred_markets: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    journal_entries: int = 0
    profitable_roundtrips: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shadow_id": self.shadow_id,
            "journal_hash": self.journal_hash,
            "rules": [r.to_dict() for r in self.rules],
            "profile_text": self.profile_text,
            "preferred_markets": self.preferred_markets,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "journal_entries": self.journal_entries,
            "profitable_roundtrips": self.profitable_roundtrips,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ShadowProfile:
        return cls(
            shadow_id=d["shadow_id"],
            journal_hash=d.get("journal_hash", ""),
            rules=[ShadowRule.from_dict(r) for r in d.get("rules", [])],
            profile_text=d.get("profile_text", ""),
            preferred_markets=list(d.get("preferred_markets", [])),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            journal_entries=int(d.get("journal_entries", 0)),
            profitable_roundtrips=int(d.get("profitable_roundtrips", 0)),
        )
