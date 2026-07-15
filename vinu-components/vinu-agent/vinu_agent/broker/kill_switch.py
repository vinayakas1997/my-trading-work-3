"""Global filesystem-based kill switch for trading.

Trading is halted when KILL_SWITCH_PATH exists.
Touch the file to halt all trades; remove it to resume.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KILL_SWITCH_PATH = Path("/tmp/vinu-trading-halt")


def halt_trading() -> None:
    KILL_SWITCH_PATH.touch(exist_ok=True)
    logger.warning("TRADING HALTED via %s", KILL_SWITCH_PATH)


def resume_trading() -> None:
    if KILL_SWITCH_PATH.exists():
        KILL_SWITCH_PATH.unlink()
        logger.info("Trading resumed — %s removed", KILL_SWITCH_PATH)


def is_trading_halted() -> bool:
    return KILL_SWITCH_PATH.exists()
