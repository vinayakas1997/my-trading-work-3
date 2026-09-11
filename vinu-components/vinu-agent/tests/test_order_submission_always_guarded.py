"""Stage C (C10): architectural tripwire — every live order-submission
call site must go through OrderGuard.

C10's revisit trigger was "only if a code path is found that can submit an
order without going through OrderGuard". The 2026-09-11 audit found none:
the only two `broker.submit_order(` calls in the package are both inside
`tools/trade_tool.py` (one on the replay/backtest branch, one on the live
branch, the latter after `guard.check()` + `guard.pre_approve()` inside
`kill_switch_lock()`), and `POST /broker/order` delegates to that same
`TradeTool`. This test freezes that invariant so a future second path
fails CI instead of silently bypassing the safety layer.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1] / "vinu_agent"
# The only module allowed to call broker.submit_order() / .replace_order().
_ALLOWED = {"tools/trade_tool.py"}


def _order_call_sites() -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for py in _PKG.rglob("*.py"):
        rel = py.relative_to(_PKG).as_posix()
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("submit_order", "replace_order"):
                    # ignore `def submit_order` (that's ast.FunctionDef, not Call)
                    # and the Protocol/base definitions
                    hits.append((rel, node.lineno, node.func.attr))
    return hits


def test_every_order_submission_call_site_is_in_an_allowed_module() -> None:
    offenders = [h for h in _order_call_sites() if h[0] not in _ALLOWED]
    assert not offenders, (
        "New order-submission call site(s) outside OrderGuard's path: "
        + ", ".join(f"{f}:{ln} .{attr}()" for f, ln, attr in offenders)
        + " — route live orders through TradeTool / POST /broker/order so the "
        "mandate + kill-switch checks can't be bypassed."
    )


def test_the_known_allowed_call_sites_still_exist() -> None:
    # guards against this test silently passing because trade_tool was renamed
    known = [h for h in _order_call_sites() if h[0] in _ALLOWED]
    assert len(known) >= 2, "expected the replay + live submit_order calls in trade_tool.py"
