"""Canonical 7-cluster grouping of the 25 real vinu-initial-analysis
angles -- the same fixed A-G scheme `angle_synthesizer/prompt.md`'s
"Cluster synthesis (Phase 9)" section states verbatim, kept here as real
importable data so `cluster_digest_validator.py` can check an LLM's
`cluster_digest` output against real membership instead of trusting it.

Source of truth for both: `angles.yaml`'s 25 real angle ids, split into
this fixed scheme by real similarity. If a real angle is ever added or
renamed in `angles.yaml`, this dict is the other place that needs
updating alongside the prompt text.
"""

from __future__ import annotations

# 2026-10-07: garch, exponential_smoothing, kalman_filters and search_trends are switched off (vinu_infra.system_manifest
# .PERMANENTLY_DISABLED_ANGLES), so they are not members here; a test fails if one of them is listed again.
ANGLE_CLUSTERS: dict[str, list[str]] = {
    "A": ["arima"],
    "B": [
        "chronos", "dlinear", "itransformer", "kronos",
        "lpatchtst", "lstm", "patchtst", "tft",
        "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
    ],
    "C": ["drawdown_deep_dive"],
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
