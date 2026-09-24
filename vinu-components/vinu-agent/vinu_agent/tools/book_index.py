"""Meaning for the 7 real angle clusters -- the one shared place any
consumer (the ticker-book gatekeeper, forecast_skill's digest line)
reads a cluster's title/use from, instead of each rendering a bare
letter or keeping its own copy. Membership stays owned by
`angle_clusters.ANGLE_CLUSTERS`; this module only adds meaning on top.
See missing-pieces-of-system/gatekeeper-initial-analysis/01-plan.md.
"""

from __future__ import annotations

from .angle_clusters import ANGLE_CLUSTERS

_CLUSTER_MEANING: dict[str, tuple[str, str]] = {
    "A": (
        "Classical statistical forecasts",
        "cheap, transparent baseline forecasts -- sanity-check the heavier models against these",
    ),
    "B": (
        "Deep-learning / foundation-model forecasts",
        "the ensemble -- consensus across 14 models catches signal one model alone would miss or fake",
    ),
    "C": (
        "Volatility & drawdown risk",
        "how rough the ride could get, independent of direction",
    ),
    "D": (
        "Regime & trend structure",
        "what kind of market this is, so the forecasts get read in the right context",
    ),
    "E": (
        "Shock / personality behavior",
        "flags a ticker reacting abnormally, so a 'normal-behavior' forecast isn't trusted blindly",
    ),
    "F": (
        "Cross-asset & causality",
        "checks whether the move is really about this ticker or just following peers/news",
    ),
    "G": (
        "Validation & attribution",
        "grades the system's own past calls, so confidence is earned, not assumed",
    ),
}

CLUSTER_INDEX: dict[str, dict] = {
    letter: {"title": title, "use": use, "members": list(ANGLE_CLUSTERS[letter])}
    for letter, (title, use) in _CLUSTER_MEANING.items()
}


def cluster_title(letter: str) -> str:
    return CLUSTER_INDEX.get(str(letter).strip().upper(), {}).get("title", "")
