"""Which money a stack is trading: `paper` (Alpaca paper, play money) or `real`.

One place reads the setting so no service guesses. Every record that carries money is tagged with the mode it was made
under (`account_mode`), and a sum or join across the two modes is a bug (plan: Proper-Project-Implementation/
05-handling-system-portfolio-allocator).

Settings (environment):
  VINU_ACCOUNT_MODE   paper | real          (default paper; anything else is refused loudly)
  VINU_REAL_CAPITAL   dollars, e.g. 20      (the capital base sizes are computed from; empty = no cap, the account is the base)
  VINU_CAPITAL_RESERVE_FRACTION             (default 0.4, share of real capital never allocated)
"""
from __future__ import annotations

import os

ACCOUNT_MODES = ("paper", "real")
DEFAULT_MODE = "paper"
DEFAULT_RESERVE_FRACTION = 0.4


def current_account_mode() -> str:
    raw = (os.getenv("VINU_ACCOUNT_MODE") or DEFAULT_MODE).strip().lower()
    if raw not in ACCOUNT_MODES:
        raise ValueError(f"VINU_ACCOUNT_MODE must be one of {ACCOUNT_MODES}, got {raw!r}")
    return raw


def real_capital() -> float | None:
    """The capital base in dollars, or None when no base is configured. Real mode without a base is refused: the
    allocator has nothing to size from."""
    raw = (os.getenv("VINU_REAL_CAPITAL") or "").strip()
    if not raw:
        if current_account_mode() == "real":
            raise ValueError("VINU_ACCOUNT_MODE=real needs VINU_REAL_CAPITAL (the money the sizes are computed from)")
        return None
    value = float(raw)
    if value <= 0:
        raise ValueError("VINU_REAL_CAPITAL must be positive")
    return value


def reserve_fraction() -> float:
    value = float(os.getenv("VINU_CAPITAL_RESERVE_FRACTION") or DEFAULT_RESERVE_FRACTION)
    if not (0.0 <= value < 1.0):
        raise ValueError("VINU_CAPITAL_RESERVE_FRACTION must be in [0, 1)")
    return value


def require_mode(value: str | None) -> str:
    """Validate a tag read from a record or a request; an empty or unknown tag is refused, never defaulted."""
    if value not in ACCOUNT_MODES:
        raise ValueError(f"account_mode must be one of {ACCOUNT_MODES}, got {value!r}")
    return value
