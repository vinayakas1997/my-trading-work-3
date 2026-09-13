"""Tests for the kill switch, including its check-then-act race fix
(`New-talk-agents/new-thinking/new-restructure/phases/
phase-3-kill-switch/04-implement-test.md`'s follow-up -- "accepted, not
closed" is now actually closed). See broker/kill_switch.py.
"""

from __future__ import annotations

import json
import threading
import time
from unittest.mock import patch

import pytest

from vinu_agent.broker.kill_switch import (
    AuditLogger,
    halt_trading,
    is_trading_halted,
    kill_switch_lock,
    resume_trading,
)


@pytest.fixture(autouse=True)
def _isolated_safety_ledger(tmp_path):
    # A37: halt_trading()/resume_trading() now also append to the safety
    # ledger -- point it at a tmp file so these tests don't write to the
    # real ~/.vinu/safety_ledger.jsonl.
    from vinu_agent.broker.audit_ledger import HashChainedLedger, reset_safety_ledger

    reset_safety_ledger(HashChainedLedger(tmp_path / "safety_ledger.jsonl"))
    yield
    reset_safety_ledger(None)


@pytest.fixture(autouse=True)
def _clean_kill_switch_state():
    resume_trading()
    resume_trading(scope="TESTSYM")
    yield
    resume_trading()
    resume_trading(scope="TESTSYM")


class TestHaltResumeStillWorkThroughTheLock:
    def test_global_halt_and_resume_round_trip(self) -> None:
        assert is_trading_halted() is False
        halt_trading()
        assert is_trading_halted() is True
        resume_trading()
        assert is_trading_halted() is False

    def test_scoped_halt_and_resume_round_trip(self) -> None:
        assert is_trading_halted(scope="TESTSYM") is False
        halt_trading(scope="TESTSYM")
        assert is_trading_halted(scope="TESTSYM") is True
        assert is_trading_halted(scope="OTHERSYM") is False
        resume_trading(scope="TESTSYM")
        assert is_trading_halted(scope="TESTSYM") is False

    def test_global_halt_takes_precedence_over_scoped_check(self) -> None:
        halt_trading()
        assert is_trading_halted(scope="TESTSYM") is True


class TestKillSwitchLockRealMutualExclusion:
    def test_second_acquirer_blocks_until_first_releases(self) -> None:
        """Real OS-level lock, not just an in-process one -- proves a
        second holder genuinely cannot enter its critical section while
        the first is inside theirs."""
        events: list[str] = []
        first_has_lock = threading.Event()

        def holder() -> None:
            with kill_switch_lock():
                events.append("A_start")
                first_has_lock.set()
                time.sleep(0.2)
                events.append("A_end")

        def waiter() -> None:
            first_has_lock.wait(timeout=2)
            with kill_switch_lock():
                events.append("B_start")
                events.append("B_end")

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=waiter)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert events == ["A_start", "A_end", "B_start", "B_end"]

    def test_halt_trading_blocks_while_a_critical_section_holds_the_lock(self) -> None:
        """The actual bug this closes: halt_trading() (a different
        "process" in production) must not be able to complete while a
        check-then-act critical section (capital_allocator_hook.py's
        check-then-mark_active, trade_tool.py's pre_approve-then-
        submit_order) is mid-flight."""
        events: list[str] = []
        critical_section_entered = threading.Event()

        def critical_section() -> None:
            with kill_switch_lock():
                events.append("critical_section_start")
                critical_section_entered.set()
                time.sleep(0.2)
                events.append("critical_section_end")

        def halt() -> None:
            critical_section_entered.wait(timeout=2)
            halt_trading()
            events.append("halted")

        t1 = threading.Thread(target=critical_section)
        t2 = threading.Thread(target=halt)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert events == ["critical_section_start", "critical_section_end", "halted"]


class TestAuditLoggerFailsOpenOnUnwritablePath:
    """situation-test/18-audit-logger-unwritable-path-crashes-order-pipeline.md:
    found by real testing that a filesystem error writing the audit entry
    (disk full, a permissions/mount problem, ...) raised straight out of
    `AuditLogger.log()`, and most `trade_tool.py` call sites (the earliest
    checks especially) call it completely unwrapped -- so the error
    propagated all the way out of `TradeTool.execute()`, crashing an order
    rejection/pause response instead of just failing to record it. The
    audit log is a secondary, observability-only side effect of every real
    check in this codebase, never itself a safety gate, so it must fail
    open the same way every other optional store lookup in `order_guard.py`
    already does."""

    def test_log_does_not_raise_when_the_log_path_is_unwritable(self, tmp_path) -> None:
        # A file where log()'s mkdir(parents=True) expects a directory --
        # a real, reproducible OSError (FileExistsError on Windows,
        # NotADirectoryError on POSIX), not a mocked one.
        blocking_file = tmp_path / "not_a_directory"
        blocking_file.write_text("i am a file, not a directory")
        bad_log_path = blocking_file / "trade_audit.log"

        with patch.object(AuditLogger, "LOG_PATH", bad_log_path):
            AuditLogger.log("order_rejected", {"symbol": "AAPL"}, session_id="s1", symbol="AAPL")
            # Must not raise -- the call above completing at all is the assertion.

    def test_real_trade_tool_execute_still_returns_when_audit_log_is_unwritable(self, tmp_path) -> None:
        """End-to-end: the real invalid-qty rejection path in
        TradeTool.execute() calls AuditLogger.log() before any try/except
        of its own -- confirms the fix actually protects that real call
        site, not just a direct unit test of log() in isolation."""
        from vinu_agent.tools.trade_tool import TradeTool

        blocking_file = tmp_path / "not_a_directory"
        blocking_file.write_text("i am a file, not a directory")
        bad_log_path = blocking_file / "trade_audit.log"

        tool = TradeTool()
        tool._as_of = None
        tool._session_id = "s1"

        with patch.object(AuditLogger, "LOG_PATH", bad_log_path):
            result = json.loads(tool.execute(symbol="AAPL", qty=-5, side="buy"))

        assert result["status"] == "rejected"
        assert result["reason_code"] == "invalid_qty"
