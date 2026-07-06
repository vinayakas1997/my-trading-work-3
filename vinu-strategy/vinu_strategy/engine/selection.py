from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)


def select_all(universe: list[str], params: dict[str, Any] | None = None) -> list[str]:
    return universe


def select_threshold(
    signals: dict[str, float],
    params: dict[str, Any] | None = None,
    signal_context: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    field = (params or {}).get("on", "signal")
    min_val = (params or {}).get("min", 0.0)

    def get_value(sym: str) -> float:
        if field != "signal" and signal_context:
            features = signal_context.get(sym, {}).get("features", {})
            return features.get(field, 0.0)
        return signals.get(sym, 0.0)

    return [sym for sym in signals if get_value(sym) >= min_val]


def select_top_n(signals: dict[str, float], params: dict[str, Any] | None = None) -> list[str]:
    n = (params or {}).get("n", 10)
    sorted_syms = sorted(signals.items(), key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in sorted_syms[:n]]


SELECTION_METHODS = {
    "all": select_all,
    "threshold": select_threshold,
    "top_n": select_top_n,
}


def run_selection(
    method: str,
    universe: list[str],
    signals: dict[str, float] | None = None,
    params: dict[str, Any] | None = None,
    signal_context: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    func = SELECTION_METHODS.get(method)
    if func is None:
        LOG.warning("Unknown selection method '%s', using 'all'", method)
        return universe
    if method == "all":
        return func(universe, params)
    if signals is None:
        return universe
    if method == "threshold":
        return func(signals, params, signal_context)
    return func(signals, params)
