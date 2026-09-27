from __future__ import annotations

# Relocated to vinu_tools (system-wide-audit-and-design item #14, senior-
# quant composite-sizing follow-up): vinu-simulator's position sizer now
# needs this exact same DCC-GARCH/Gerber math for correlation-aware
# sizing, and reimplementing a second, independently-derived copy of it
# would risk the same "duplicated computation logic" class of bug this
# whole audit series has repeatedly found and fixed elsewhere. Re-exported
# here unchanged so every existing caller/test of this module keeps
# working without modification.
from vinu_tools.compute.risk.shock_correlation import (  # noqa: F401
    _garch_conditional_variance,
    _gerber_correlation,
    dcc_shock_correlation,
)
