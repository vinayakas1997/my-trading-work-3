"""`RankerScheduler`: the same `tick()`/`run_forever()` shape as
`scheduler.Scheduler` (B18's condition-rule scheduler), driving
`RankerRunner` against every active `RankerConfig` on its own
`interval_sec` instead. Kept as a separate class rather than folding into
`Scheduler` -- a ranker cycle and a rule cycle do genuinely different
work (rank a universe vs. evaluate one condition tree), and `cli.py`'s
`scan` subcommand runs both in the same process, ticking each on its own
schedule.
"""

from __future__ import annotations

import logging
import time

from .churn import RankerChurnStore, record_ranking
from .runner import RankerRunner
from .snapshot_store import RankedSnapshotStore
from .store import RankerStore, StoredRanker

LOG = logging.getLogger(__name__)


class RankerScheduler:
    def __init__(
        self,
        ranker_store: RankerStore,
        runner: RankerRunner,
        *,
        snapshot_store: RankedSnapshotStore | None = None,
        churn_store: RankerChurnStore | None = None,
    ) -> None:
        self._ranker_store = ranker_store
        self._runner = runner
        self._snapshots = snapshot_store
        self._churn = churn_store
        self._last_run_at: dict[str, float] = {}

    def _due(self, stored: StoredRanker, now: float) -> bool:
        last = self._last_run_at.get(stored.ranker.ranker_id)
        return last is None or (now - last) >= stored.interval_sec

    def tick(self, *, now: float | None = None) -> list[str]:
        """Runs every active, due ranker once. Returns the ranker_ids that
        actually ran this tick (empty if nothing was due)."""
        now = now if now is not None else time.time()
        ran: list[str] = []
        for stored in self._ranker_store.all(active_only=True):
            if not self._due(stored, now):
                continue
            self._last_run_at[stored.ranker.ranker_id] = now
            try:
                result = self._runner.run(stored.ranker)
            except Exception:  # noqa: BLE001 -- one bad ranker must not stop the scheduler
                LOG.exception("ranker scheduler: %s raised during run()", stored.ranker.ranker_id)
                continue
            if self._snapshots is not None:
                try:
                    # record_ranking reads the PREVIOUS latest snapshot before
                    # overwriting it, diffs against the new top-N, and persists
                    # any entered/exited events -- the same shared path the
                    # on-demand /rank route uses, so a manual re-run can't
                    # create a gap or a double-count in the churn history.
                    record_ranking(self._snapshots, self._churn, stored.ranker.ranker_id, result, now=now)
                except Exception:  # noqa: BLE001 -- a snapshot/churn-write failure must not crash the scheduler
                    LOG.exception("ranker scheduler: failed to persist snapshot/churn for %s", stored.ranker.ranker_id)
            ran.append(stored.ranker.ranker_id)
        return ran

    def run_forever(self, *, poll_sec: float = 30.0, stop_event=None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.tick()
            time.sleep(poll_sec)
