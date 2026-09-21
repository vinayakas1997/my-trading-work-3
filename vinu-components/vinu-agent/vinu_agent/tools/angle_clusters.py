"""Canonical 7-cluster grouping of the 28 real vinu-initial-analysis
angles -- the same fixed A-G scheme `angle_synthesizer/prompt.md`'s
"Cluster synthesis (Phase 9)" section states verbatim, kept here as real
importable data so `cluster_digest_validator.py` can check an LLM's
`cluster_digest` output against real membership instead of trusting it.

Source of truth for both: `angles.yaml`'s 28 real angle ids, split into
this fixed scheme by real similarity. If a real angle is ever added or
renamed in `angles.yaml`, this dict is the other place that needs
updating alongside the prompt text.
"""

from __future__ import annotations

ANGLE_CLUSTERS: dict[str, list[str]] = {
    "A": ["arima", "exponential_smoothing", "kalman_filters"],
    "B": [
        "chronos", "dlinear", "itransformer", "kronos", "lag_llama",
        "lpatchtst", "lstm", "moirai", "moment", "patchtst", "tft",
        "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
    ],
    "C": ["garch", "drawdown_deep_dive"],
    "D": ["regime_analysis", "trend_lifecycle", "trend_session_structure"],
    "E": ["shock_clustering", "shock_personality"],
    "F": ["peer_relative_strength", "news_price_causality"],
    "G": ["backtesting_44_metrics", "pnl_attribution"],
}

# Reverse lookup: real angle id -> its one real cluster letter.
ANGLE_TO_CLUSTER: dict[str, str] = {
    angle: cluster
    for cluster, angles in ANGLE_CLUSTERS.items()
    for angle in angles
}

ALL_REAL_ANGLE_IDS: frozenset[str] = frozenset(ANGLE_TO_CLUSTER.keys())
