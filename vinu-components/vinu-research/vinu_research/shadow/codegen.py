from __future__ import annotations

import ast
import logging
from pathlib import Path

from vinu_research.shadow.models import ShadowProfile

LOG = logging.getLogger(__name__)


def generate_signal_engine(
    profile: ShadowProfile,
    output_path: str | Path | None = None,
) -> str:
    lines: list[str] = []
    lines.append('"""')
    lines.append(f"Signal Engine generated from Shadow Profile: {profile.shadow_id}")
    lines.append("")
    lines.append(profile.profile_text)
    lines.append('"""')
    lines.append("")
    lines.append("from typing import Any")
    lines.append("import pandas as pd")
    lines.append("import numpy as np")
    lines.append("")
    lines.append("")
    lines.append("class SignalEngine:")
    lines.append("    def __init__(self, config: dict[str, Any] | None = None):")
    lines.append("        self.config = config or {}")
    lines.append("")
    lines.append("    def compute_signals(self, data: pd.DataFrame) -> pd.Series:")
    lines.append('        """')
    lines.append("        Compute trading signals based on extracted shadow rules.")
    lines.append("")
    lines.append("        Parameters")
    lines.append("        ----------")
    lines.append("        data : pd.DataFrame")
    lines.append("            OHLCV data with columns: open, high, low, close, volume")
    lines.append("")
    lines.append("        Returns")
    lines.append("        -------")
    lines.append("        pd.Series")
    lines.append("            Trading signals: +1 (long), -1 (short), 0 (neutral)")
    lines.append('        """')
    lines.append("        signals = pd.Series(0.0, index=data.index)")

    for i, rule in enumerate(profile.rules):
        ec = rule.entry_condition
        lines.append("")
        lines.append(f"        # Rule {i}: {rule.human_text}")
        if "holding_days_min" in ec and "holding_days_max" in ec:
            lo = ec["holding_days_min"]
            hi = ec["holding_days_max"]
            lines.append(f"        # Entry: hold {lo:.0f}-{hi:.0f} days")
            lines.append(f"        # TODO: Implement entry logic based on profile constraints")

    lines.append("")
    lines.append("        return signals")

    code = "\n".join(lines)

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")

    return code


def validate_generated_code(code: str) -> bool:
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("eval", "exec", "__import__"):
                        return False
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec", "__import__"):
                        return False
            if isinstance(node, ast.Import) and any(
                alias.name in ("os", "subprocess", "shutil") for alias in node.names
            ):
                return False
            if isinstance(node, ast.ImportFrom) and node.module in ("os", "subprocess", "shutil"):
                return False
        return True
    except SyntaxError:
        return False
