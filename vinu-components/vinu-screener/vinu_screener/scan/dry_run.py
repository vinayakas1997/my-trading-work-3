"""Stage B (B19): dry-run/test-rule-before-enable UX, ported from
daily_stock_analysis's `AlertRuleTestResponse` (`api/v1/schemas/alerts.py:
20-147`) -- validate a rule against current market data and report
per-target trigger/degraded/skipped counts *before* it runs unattended,
rather than finding out a rule is misconfigured (wrong symbol, indicator
that never has enough history, a condition that can never be true) only
after it's been silently polling and doing nothing for a week.

Reuses `ScanMonitor.run_cycle()` itself -- a dry run is a real cycle, not a
separate code path (the same "validated is what actually executes"
principle Freqtrade's dry-run/live parity is built around) -- but against a
throwaway `CooldownGate` so a test run never mutates the rule's real live
gating state, and it is the caller's choice whether to also skip B17's
permanent audit table for a dry run (this module never writes to it
itself).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cooldown import CooldownGate
from .monitor import CycleResult, ScanMonitor, ScanRule

# Maps ScanMonitor's per-symbol SymbolOutcome.status onto DSA's own
# triggered/not_triggered/evaluation_error/degraded/skipped taxonomy.
_STATUS_TO_CATEGORY = {
    "fired": "triggered",
    "no_match": "not_triggered",
    "insufficient_history": "skipped",
    "coarse_filtered": "skipped",
    "timeout": "degraded",
    "fetch_error": "evaluation_error",
}


@dataclass
class DryRunReport:
    rule_id: str
    triggered: list[str] = field(default_factory=list)
    not_triggered: list[str] = field(default_factory=list)
    evaluation_error: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    cycle: CycleResult | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "triggered": len(self.triggered),
            "not_triggered": len(self.not_triggered),
            "evaluation_error": len(self.evaluation_error),
            "degraded": len(self.degraded),
            "skipped": len(self.skipped),
        }

    @property
    def universe_size(self) -> int:
        return sum(self.counts.values())


def run_dry_run(monitor: ScanMonitor, rule: ScanRule, *, now: float | None = None) -> DryRunReport:
    """One throwaway cycle for `rule` on `monitor`'s data source/library,
    reported per-target rather than just a fired list. Never mutates
    `monitor`'s own `CooldownGate` -- builds a fresh one so a dry run can
    never suppress (or be suppressed by) a real subsequent cycle's edge
    detection."""
    scratch_monitor = ScanMonitor(
        monitor._data_source,  # noqa: SLF001 -- deliberately reusing the same data source/library, only the gate is throwaway
        library=monitor._library,
        cooldown_gate=CooldownGate(),
        fetch_timeout_sec=monitor._fetch_timeout_sec,
        interval_sec=monitor.interval_sec,
    )
    cycle = scratch_monitor.run_cycle(rule, now=now)

    report = DryRunReport(rule_id=rule.rule_id, cycle=cycle)
    for outcome in cycle.outcomes:
        category = _STATUS_TO_CATEGORY.get(outcome.status, "skipped")
        getattr(report, category).append(outcome.symbol)
    return report
