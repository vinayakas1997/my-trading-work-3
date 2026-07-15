from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_research.shadow.models import ShadowProfile


def generate_html_report(
    profile: ShadowProfile,
    attribution: dict[str, float] | None = None,
    backtest_metrics: dict[str, Any] | None = None,
) -> str:
    sections: list[str] = []
    sections.append(f"<h1>Shadow Account: {profile.shadow_id}</h1>")
    sections.append(f"<p>Generated: {datetime.now(timezone.utc).isoformat()}</p>")
    sections.append(f"<p>{profile.profile_text}</p>")

    sections.append("<h2>Profile Summary</h2>")
    sections.append("<table border='1' cellpadding='4'>")
    sections.append(f"<tr><td>Journal Entries</td><td>{profile.journal_entries}</td></tr>")
    sections.append(f"<tr><td>Profitable Roundtrips</td><td>{profile.profitable_roundtrips}</td></tr>")
    sections.append(f"<tr><td>Rules Extracted</td><td>{len(profile.rules)}</td></tr>")
    sections.append(f"<tr><td>Preferred Markets</td><td>{', '.join(profile.preferred_markets[:10])}</td></tr>")
    sections.append("</table>")

    sections.append("<h2>Extracted Rules</h2>")
    for i, rule in enumerate(profile.rules):
        sections.append(f"<h3>Rule {i + 1}: {rule.human_text}</h3>")
        sections.append("<table border='1' cellpadding='4'>")
        sections.append(f"<tr><td>Weight</td><td>{rule.weight:.4f}</td></tr>")
        if rule.holding_days_range != (0.0, 0.0):
            sections.append(f"<tr><td>Holding Days Range</td><td>{rule.holding_days_range[0]:.0f} - {rule.holding_days_range[1]:.0f}</td></tr>")
        sections.append("</table>")

    if attribution:
        sections.append("<h2>PnL Attribution</h2>")
        sections.append("<table border='1' cellpadding='4'>")
        for k, v in attribution.items():
            sections.append(f"<tr><td>{k}</td><td>{v:+,.2f}</td></tr>")
        sections.append("</table>")

    if backtest_metrics:
        sections.append("<h2>Backtest Performance</h2>")
        sections.append("<table border='1' cellpadding='4'>")
        for k, v in sorted(backtest_metrics.items()):
            label = k.replace("_", " ").title()
            if isinstance(v, float):
                if "return" in k or "drawdown" in k:
                    sections.append(f"<tr><td>{label}</td><td>{v:+.2%}</td></tr>")
                else:
                    sections.append(f"<tr><td>{label}</td><td>{v:.4f}</td></tr>")
            else:
                sections.append(f"<tr><td>{label}</td><td>{v}</td></tr>")
        sections.append("</table>")

    html = "<html><body>" + "\n".join(sections) + "</body></html>"
    return html
