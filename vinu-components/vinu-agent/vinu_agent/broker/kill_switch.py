"""Multi-scope filesystem-based kill switch for trading.

Global halt: /tmp/vinu-trading-halt
Per-strategy: /tmp/vinu-trading-halt-{strategy_name}
Per-symbol: /tmp/vinu-trading-halt-{symbol}

Check-then-act race, closed: `halt_trading()`/`resume_trading()` and every
real check-then-act critical section that gates money-moving/status-
changing code on a halt check (`capital_allocator_hook.py`'s check-then-
mark_active, `trade_tool.py`'s pre_approve-then-submit_order) now share
one real OS-level lock (`kill_switch_lock()` below) -- previously this was
"accepted, not closed" (two independent operations, no shared lock; see
`New-talk-agents/new-thinking/new-restructure/phases/
phase-3-kill-switch/04-implement-test.md`). A halt can no longer complete
while either critical section is mid-flight, and vice versa -- genuinely
mutually exclusive, not just a narrowed window.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

KILL_SWITCH_PATH = Path("/tmp/vinu-trading-halt")
KILL_SWITCH_DIR = Path("/tmp/vinu-trading-halt.d")
KILL_SWITCH_LOCK_PATH = Path("/tmp/vinu-trading-halt.lock")


@contextlib.contextmanager
def kill_switch_lock() -> Iterator[None]:
    """Real mutual exclusion, not an in-process-only threading lock --
    `halt_trading()` can be called from a completely different process
    (e.g. vinu-portfolio's drawdown monitor, via /broker/halt) than the
    one holding this lock mid check-then-act, so this has to be an actual
    OS-level file lock, not `threading.Lock()`. `fcntl.flock` on POSIX
    (every real deployment -- python:3.12-slim containers); `msvcrt.locking`
    as the Windows dev-environment fallback. Blocks until acquired --
    every real critical section this guards is already a handful of
    in-memory/local-disk operations, never network I/O, so the wait is
    bounded and short by construction."""
    KILL_SWITCH_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KILL_SWITCH_LOCK_PATH.exists():
        KILL_SWITCH_LOCK_PATH.write_bytes(b"\0")
    f = open(KILL_SWITCH_LOCK_PATH, "r+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


def halt_trading(scope: str | None = None) -> None:
    """Halt trading globally or for a specific scope (strategy name or symbol)."""
    with kill_switch_lock():
        if scope is None:
            KILL_SWITCH_PATH.touch(exist_ok=True)
            logger.warning("TRADING HALTED globally via %s", KILL_SWITCH_PATH)
        else:
            KILL_SWITCH_DIR.mkdir(parents=True, exist_ok=True)
            (KILL_SWITCH_DIR / f"{scope}.halt").touch(exist_ok=True)
            logger.warning("TRADING HALTED for %s via %s/%s.halt", scope, KILL_SWITCH_DIR, scope)


def resume_trading(scope: str | None = None) -> None:
    """Resume trading globally or for a specific scope."""
    with kill_switch_lock():
        if scope is None:
            if KILL_SWITCH_PATH.exists():
                KILL_SWITCH_PATH.unlink()
                logger.info("Trading resumed globally — %s removed", KILL_SWITCH_PATH)
        else:
            path = KILL_SWITCH_DIR / f"{scope}.halt"
            if path.exists():
                path.unlink()
                logger.info("Trading resumed for %s — %s removed", scope, path)


def is_trading_halted(scope: str | None = None) -> bool:
    """Check if trading is halted globally or for a specific scope.

    A global halt always takes precedence over a scoped halt.
    """
    if KILL_SWITCH_PATH.exists():
        return True
    if scope is not None:
        return (KILL_SWITCH_DIR / f"{scope}.halt").exists()
    return False


class AuditLogger:
    """Structured audit logging for every trading and agent-governor action.

    Writes under the container data root (VINU_AGENT_DATA_ROOT=/data in the
    Docker stack) — the only writable mount — never a hardcoded absolute path
    like /var/log/vinu, which is read-only in the container (rootfs is
    immutable; only /data is bind-mounted rw). Before the fix, every order
    (rejected or executed) raised OSError writing the audit entry and masked
    the real trade response with a 500.

    Schema (mirrors ref-fincept-terminal's AuditEntry):
      {id, action, session_id, symbol, details, metadata, paper_trading, timestamp}
    """

    LOG_PATH = Path(
        os.environ.get(
            "VINU_AGENT_AUDIT_LOG",
            os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu")) + "/trade_audit.log",
        )
    )

    # --- action constants ---
    RISK_CHECK_PASSED = "RiskCheckPassed"
    RISK_CHECK_FAILED = "RiskCheckFailed"
    ORDER_PLACED = "OrderPlaced"
    ORDER_FILLED = "OrderFilled"
    ORDER_REJECTED = "order_rejected"
    ORDER_PENDING_CONFIRMATION = "order_pending_confirmation"
    ORDER_EXECUTING = "order_executing"
    ORDER_ERROR = "order_error"
    GROUND_TRUTH_INJECTED = "GroundTruthInjected"
    AUDIT_VERDICT_FAIL = "AuditVerdictFail"
    AUDIT_VERDICT_STALE = "AuditVerdictStale"
    JOURNAL_ENTRY_CREATED = "JournalEntryCreated"
    JOURNAL_STATUS_CHANGED = "JournalStatusChanged"
    FACT_REGISTRY_WRITE = "FactRegistryWrite"

    @classmethod
    def log(
        cls,
        action: str,
        details: dict | None = None,
        *,
        session_id: str = "",
        symbol: str = "",
        metadata: dict | None = None,
        paper_trading: bool = False,
    ) -> None:
        """Write a structured audit entry."""
        import uuid
        from datetime import datetime, timezone

        entry: dict = {
            "id": uuid.uuid4().hex[:16],
            "action": action,
            "session_id": session_id,
            "symbol": symbol,
            "details": details or {},
            "metadata": metadata or {},
            "paper_trading": paper_trading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cls.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with cls.LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        logger.info("AUDIT: %s %s", action, json.dumps(details or {}))
