from __future__ import annotations

from typing import Any

import numpy as np

ALPHA_THEMES = frozenset({
    "momentum", "reversal", "volatility", "value", "growth",
    "quality", "size", "liquidity", "sentiment", "seasonality",
    "volume", "microstructure", "other",
})


class AlphaMeta:
    def __init__(
        self,
        id: str,
        theme: str = "other",
        formula_latex: str = "",
        columns_required: list[str] | None = None,
        universe: str = "us_equity",
        frequency: str = "1d",
        decay_horizon: int = 60,
        min_warmup_bars: int = 20,
    ) -> None:
        assert theme in ALPHA_THEMES, f"Invalid theme: {theme}. Must be one of {ALPHA_THEMES}"
        self.id = id
        self.theme = theme
        self.formula_latex = formula_latex
        self.columns_required = columns_required or ["close"]
        self.universe = universe
        self.frequency = frequency
        self.decay_horizon = decay_horizon
        self.min_warmup_bars = min_warmup_bars

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "theme": self.theme,
            "formula_latex": self.formula_latex,
            "columns_required": self.columns_required,
            "universe": self.universe,
            "frequency": self.frequency,
            "decay_horizon": self.decay_horizon,
            "min_warmup_bars": self.min_warmup_bars,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AlphaMeta:
        return cls(
            id=d["id"],
            theme=d.get("theme", "other"),
            formula_latex=d.get("formula_latex", ""),
            columns_required=d.get("columns_required", ["close"]),
            universe=d.get("universe", "us_equity"),
            frequency=d.get("frequency", "1d"),
            decay_horizon=int(d.get("decay_horizon", 60)),
            min_warmup_bars=int(d.get("min_warmup_bars", 20)),
        )
