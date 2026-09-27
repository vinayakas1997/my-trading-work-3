"""Item #23 findings #2/#3 fix: cross-process visibility for
PortfolioDrawdownMonitor's real halve/flat/halt state, so
compute_daily_allocation() can actually read it (see
drawdown_status.py's own docstring for why an in-memory read alone
can't work here).
"""

from __future__ import annotations

from vinu_portfolio.storage.drawdown_status import DrawdownStatusStore


def _store(tmp_path) -> DrawdownStatusStore:
    return DrawdownStatusStore(str(tmp_path / "drawdown_status.db"))


class TestDrawdownStatusStore:
    def test_never_written_defaults_to_ok_not_a_crash(self, tmp_path) -> None:
        store = _store(tmp_path)
        status = store.get()
        assert status.action == "ok"
        assert status.current_drawdown == 0.0
        assert status.threshold_breached is False

    def test_record_then_get_round_trips(self, tmp_path) -> None:
        store = _store(tmp_path)
        store.record(action="halve", current_drawdown=-0.12, threshold_breached=False)

        status = store.get()
        assert status.action == "halve"
        assert status.current_drawdown == -0.12
        assert status.threshold_breached is False
        assert status.updated_at  # stamped, not blank

    def test_repeated_record_overwrites_not_accumulates(self, tmp_path) -> None:
        store = _store(tmp_path)
        store.record(action="halve", current_drawdown=-0.12, threshold_breached=False)
        store.record(action="halt", current_drawdown=-0.22, threshold_breached=True)

        status = store.get()
        assert status.action == "halt"
        assert status.threshold_breached is True

    def test_a_second_store_instance_on_the_same_file_sees_the_write(self, tmp_path) -> None:
        """The whole point -- one process (the monitor loop) writes,
        another (the API server) reads, no shared Python object."""
        db_path = str(tmp_path / "drawdown_status.db")
        writer = DrawdownStatusStore(db_path)
        writer.record(action="flat", current_drawdown=-0.16, threshold_breached=False)
        writer.close()

        reader = DrawdownStatusStore(db_path)
        try:
            status = reader.get()
        finally:
            reader.close()
        assert status.action == "flat"
