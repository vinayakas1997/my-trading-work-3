"""The ticker-book gatekeeper: one shared, deterministic read layer in
front of what the system already stores about a ticker, so no consumer
needs its own private read/parse logic or has to already know how the
book is organized. Reads only -- nothing is reorganized or duplicated
on disk. See missing-pieces-of-system/gatekeeper-initial-analysis/.
"""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool
from .angle_clusters import ANGLE_TO_CLUSTER
from .angle_glossary import explain_angle
from .book_index import CLUSTER_INDEX

_ANGLES_SUBS = ("glossary", "per_ticker", "clusters", "cross_cluster")

_BOOK_MAP: dict[str, Any] = {
    "angles": {
        "title": "Angles",
        "available": True,
        "sub_chapters": {
            "glossary": {"id": "1a", "ticker_independent": True,
                         "description": "What each angle measures -- definitions, not results."},
            "per_ticker": {"id": "1b", "ticker_independent": False,
                           "description": "Per-ticker angle data (latest digest)."},
            "clusters": {"id": "1c", "ticker_independent": False,
                         "description": "7-cluster synthesis, each labeled with its real title."},
            "cross_cluster": {"id": "1d", "ticker_independent": False,
                              "description": "Cross-cluster corroboration and consensus."},
        },
    },
    "experience": {
        "title": "Experience",
        "available": False,
        "reason": "not yet built, see missing-pieces-of-system/recording-the-experiece/",
        "sub_chapters": {
            "shadow_evaluator": {"id": "2b", "status": "planned -- first focus"},
            "simulation_recorded_results": {"id": "2a", "status": "planned -- second"},
        },
    },
}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _glossary(angle_digest: dict[str, Any]) -> dict[str, Any]:
    if not angle_digest:
        return _unavailable("no angles in this ticker's digest to explain")
    return {
        "available": True,
        "data": {
            name: {
                "cluster": ANGLE_TO_CLUSTER.get(name, ""),
                "cluster_title": CLUSTER_INDEX.get(ANGLE_TO_CLUSTER.get(name, ""), {}).get("title", ""),
                "explanation": explain_angle(name),
            }
            for name in angle_digest
        },
    }


def _per_ticker(angle_digest: dict[str, Any]) -> dict[str, Any]:
    if not angle_digest:
        return _unavailable("angle_digest empty on this row")
    return {"available": True, "data": angle_digest}


def _clusters(cluster_digest: dict[str, Any], anomalies: dict[str, Any], only: str) -> dict[str, Any]:
    if not cluster_digest:
        return _unavailable(
            "cluster_digest empty on this row -- comprehension predates cluster "
            "synthesis for this ticker, or hasn't been refreshed since"
        )
    letters = [only] if only else sorted(cluster_digest)
    data: dict[str, Any] = {}
    for letter in letters:
        if letter not in cluster_digest:
            continue
        meaning = CLUSTER_INDEX.get(letter, {})
        data[letter] = {
            "title": meaning.get("title", ""),
            "use": meaning.get("use", ""),
            "synthesis": cluster_digest[letter],
            "anomalies": list(anomalies.get(letter) or []),
        }
    if not data:
        return _unavailable(f"cluster {only} has no synthesis on this row")
    return {"available": True, "data": data}


def _cross_cluster(cross_cluster: dict[str, Any]) -> dict[str, Any]:
    if not cross_cluster:
        return _unavailable("cross_cluster empty on this row -- depends on clusters")
    return {"available": True, "data": cross_cluster}


class AskTickerBookTool(BaseTool):
    name = "ask_ticker_book"
    description = (
        "Ask what the system currently knows about one ticker, without needing to "
        "already know how that knowledge is organized. The book has 2 chapters: "
        "'angles' (sub-chapters: 'glossary' = what each angle measures, 'per_ticker' = "
        "the ticker's latest angle data, 'clusters' = 7-cluster synthesis labeled with "
        "real titles, 'cross_cluster' = cross-cluster corroboration) and 'experience' "
        "(not yet built). chapter='index' lists everything available and needs no "
        "ticker. Each sub-chapter reports its own 'available' flag with a reason when "
        "false -- an unavailable sub-chapter means 'never computed', not 'checked and "
        "found nothing'. source_run_id/updated_at tell you how current the read is; "
        "this is the LATEST read only, not a history."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chapter": {"type": "string", "enum": ["index", "angles", "experience"]},
            "ticker": {"type": "string", "description": "Stock symbol. Not needed for chapter='index'."},
            "sub": {
                "type": "string",
                "enum": list(_ANGLES_SUBS),
                "description": "Optional: narrow chapter='angles' to one sub-chapter. Omit for all 4.",
            },
            "cluster": {
                "type": "string",
                "description": "Optional: one cluster letter A-G to narrow sub='clusters' to just that one.",
            },
        },
        "required": ["chapter"],
    }
    is_readonly = True
    _ticker_summary_store: Any = None

    def execute(self, **kwargs: Any) -> str:
        chapter = str(kwargs.get("chapter") or "").strip().lower()
        if chapter == "index":
            return json.dumps({"chapters": _BOOK_MAP, "cluster_index": CLUSTER_INDEX})
        if chapter == "experience":
            return json.dumps(_BOOK_MAP["experience"] | {"chapter": "experience"})
        if chapter != "angles":
            return json.dumps({"error": f"unknown chapter {chapter!r}; use 'index', 'angles' or 'experience'"})
        return json.dumps(self._angles(kwargs))

    def _angles(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        ticker = str(kwargs.get("ticker") or "").strip().upper()
        if not ticker:
            return {"error": "chapter='angles' needs a ticker"}
        sub = str(kwargs.get("sub") or "").strip().lower()
        if sub and sub not in _ANGLES_SUBS:
            return {"error": f"unknown sub {sub!r}; use one of {list(_ANGLES_SUBS)}"}
        cluster = str(kwargs.get("cluster") or "").strip().upper()
        if cluster and cluster not in CLUSTER_INDEX:
            return {"error": f"unknown cluster {cluster!r}; use one of {sorted(CLUSTER_INDEX)}"}

        if self._ticker_summary_store is None:
            return {"ticker": ticker, **_unavailable("ticker summary store not configured")}
        try:
            row = self._ticker_summary_store.get_summary(ticker)
        except Exception as exc:  # noqa: BLE001 -- fail open, never break the caller
            return {"ticker": ticker, **_unavailable(f"ticker summary store read failed: {exc}")}
        if row is None:
            return {"ticker": ticker, **_unavailable("no comprehension row for this ticker yet")}

        angle_digest = getattr(row, "angle_digest", None) or {}
        builders = {
            "glossary": lambda: _glossary(angle_digest),
            "per_ticker": lambda: _per_ticker(angle_digest),
            "clusters": lambda: _clusters(
                getattr(row, "cluster_digest", None) or {},
                getattr(row, "cluster_anomalies", None) or {},
                cluster,
            ),
            "cross_cluster": lambda: _cross_cluster(getattr(row, "cross_cluster", None) or {}),
        }
        result: dict[str, Any] = {
            "ticker": ticker,
            "source_run_id": getattr(row, "source_run_id", "") or "",
            "updated_at": getattr(row, "updated_at", "") or "",
        }
        for name in ([sub] if sub else _ANGLES_SUBS):
            result[name] = builders[name]()
        return result
