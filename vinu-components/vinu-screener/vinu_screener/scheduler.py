"""The other "wire it up" piece: something that actually calls
`ScanMonitor.run_cycle()` on each active rule's own interval, in a running
process, instead of a human calling it by hand. `Scheduler.tick()` is the
whole decision (`now`-driven, so it's fully testable without real sleeping
or threads); `run_forever()` is the thin real-process loop around it.

Ties Phase B-2 (`ScanMonitor`), B-4 (`WatchAuditStore`, one-shot
deactivation via `CycleResult.deactivate_rule`), and the new `RuleStore`
together. Still decoupled per B15: `on_fire` is an injected callback the
caller supplies for actually dispatching a notification (Telegram/Discord/
whatever `resolve_targets()` names) -- this module never sends anything
itself, same as `rules/actions.py`.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .audit.watch_history import FiredWatchRecord, WatchAuditStore
from .rules.store import RuleStore, StoredRule
from .scan.monitor import CycleResult, ScanMonitor

LOG = logging.getLogger(__name__)

OnFireCallback = Callable[[StoredRule, str], None]


class Scheduler:
    def __init__(
        self,
        rule_store: RuleStore,
        monitor: ScanMonitor,
        *,
        audit_store: WatchAuditStore | None = None,
        on_fire: OnFireCallback | None = None,
    ) -> None:
        self._rule_store = rule_store
        self._monitor = monitor
        self._audit = audit_store
        self._on_fire = on_fire
        # In-process only -- which rules are "due" is scheduling state, not
        # something that needs to survive a restart (a restart just means
        # every active rule looks due again on the first tick, which is
        # correct: nothing was missed, at worst one rule runs slightly
        # early).
        self._last_run_at: dict[str, float] = {}

    def _due(self, stored: StoredRule, now: float) -> bool:
        last = self._last_run_at.get(stored.rule.rule_id)
        return last is None or (now - last) >= stored.interval_sec

    def tick(self, *, now: float | None = None) -> list[CycleResult]:
        """Run every active rule that's due, exactly once each. Returns the
        `CycleResult`s produced this tick (empty if nothing was due) -- the
        real loop ignores the return value, tests use it directly."""
        now = now if now is not None else time.time()
        results: list[CycleResult] = []
        for stored in self._rule_store.all(active_only=True):
            if not self._due(stored, now):
                continue
            self._last_run_at[stored.rule.rule_id] = now
            try:
                result = self._monitor.run_cycle(stored.rule, now=now)
            except Exception:  # noqa: BLE001 -- one bad rule must not stop the scheduler
                LOG.exception("scheduler: rule %s raised during run_cycle", stored.rule.rule_id)
                continue
            results.append(result)
            self._handle_result(stored, result, now)
        return results

    def _handle_result(self, stored: StoredRule, result: CycleResult, now: float) -> None:
        if result.fired:
            if self._audit is not None:
                try:
                    self._audit.record_many(
                        [FiredWatchRecord(stored.rule.rule_id, s, now) for s in result.fired]
                    )
                except Exception:  # noqa: BLE001 -- audit failure must not block dispatch/deactivation
                    LOG.exception("scheduler: failed to record fires for rule %s", stored.rule.rule_id)
            if self._on_fire is not None:
                for symbol in result.fired:
                    try:
                        self._on_fire(stored, symbol)
                    except Exception:  # noqa: BLE001 -- one bad dispatch must not block the rest
                        LOG.exception("scheduler: on_fire callback failed for %s/%s", stored.rule.rule_id, symbol)
        if result.deactivate_rule:
            self._rule_store.set_active(stored.rule.rule_id, False)

    def run_forever(self, *, poll_sec: float = 5.0, stop_event=None) -> None:
        """The real process loop -- checks every `poll_sec` for rules that
        have become due, rather than sleeping per-rule; a rule's own
        `interval_sec` (floored at `MIN_INTERVAL_SEC` by `RuleStore`) is
        what actually paces it, `poll_sec` is just how granular the
        due-check is. `stop_event` (a `threading.Event`-like object with
        `.is_set()`) lets a caller shut the loop down cleanly; `None` runs
        forever."""
        while stop_event is None or not stop_event.is_set():
            self.tick()
            time.sleep(poll_sec)
