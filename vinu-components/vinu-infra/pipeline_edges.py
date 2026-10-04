"""Pipeline edge manifest -- Phase 1 of newer-thinking-with-discussed/
the-inconsistencies-v2/03-implementation-plan.md.

One declared list of "what output of which service must be consumed by
which other service" (`pipeline_edges.yaml`, sibling file), plus a static
checker that compares that list with the actual source. It exists because
the audits kept finding the same shape of defect: a producer that works,
a consumer that works, and no call between them (e.g. vinu-portfolio's
`/portfolio/daily-allocation` was computed but `vinu-live`'s scheduler read
`/portfolio/state` instead -- 02-logic-audit-2026-10-02.md A1). A runtime log
cannot see that kind of gap, because the consumer never asks, so it never
notices anything missing. A declared list can.

Each edge has a status:

* ``wired`` -- the consumer's source must reference the producer's output.
  If it stops doing so, that is a regression.
* ``gap``   -- a known, documented missing connection (``gap_ref`` points at
  the audit item). The consumer's source must NOT reference it yet. The day
  someone wires it, the check reports ``DRIFT_NOW_WIRED`` and the manifest
  entry must be flipped to ``wired`` -- so the manifest cannot silently rot
  in either direction.

This module only reads files. It never imports another service, never
raises into a caller that did not ask for the check, and has no runtime
side effects -- it is a build-time/CI tool. Runtime recording of edges
(received / empty / stale / missing) is a later phase and will reuse the
edge ids defined here.

Run as a report:  ``python -m vinu_infra.pipeline_edges``
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML ships with the rest of the stack; keep the import soft so
    import yaml  # importing this module never breaks a service that lacks it.
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# vinu-components/ -- the directory that holds every service folder.
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "pipeline_edges.yaml"

# Result codes. The first two are healthy; the rest make the test fail.
OK_WIRED = "OK_WIRED"
OK_GAP = "OK_GAP"
DRIFT_NOW_WIRED = "DRIFT_NOW_WIRED"
DRIFT_NOT_WIRED = "DRIFT_NOT_WIRED"
DRIFT_NOT_INSTRUMENTED = "DRIFT_NOT_INSTRUMENTED"
STALE = "STALE"
INVALID = "INVALID"

HEALTHY = {OK_WIRED, OK_GAP}


@dataclass
class Edge:
    id: str
    producer_service: str
    producer_files: list[str]
    producer_defines: list[str]
    consumer_service: str
    consumer_files: list[str]
    consumer_references: list[str]
    purpose: str = ""
    cadence: str = ""
    empty_ok: bool = False
    status: str = "wired"
    gap_ref: str = ""
    note: str = ""
    # Phase 3: True once the consumer calls `record_edge("<this id>", ...)` at its consumption point
    # (checked statically below); `stale_after_sec` is how old the last observation may be before the
    # runtime report calls the edge stale (None = never judged stale by age).
    instrumented: bool = False
    stale_after_sec: float | None = None
    # Layer B (routing-find-and-fix/01-plan.md): `contract` is the name of the pydantic model in
    # edge_contracts.py that describes the payload on this connection; `contract_none` is the written reason
    # an edge carries no JSON payload to describe. `contract_producer_files` are extra files searched for the
    # producer's field names when the producer's own files only hold the route, not the code that builds it.
    contract: str = ""
    contract_none: str = ""
    contract_producer_files: list[str] = field(default_factory=list)


@dataclass
class EdgeResult:
    edge: Edge
    code: str
    detail: str = ""
    matched: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.code in HEALTHY


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def load_edges(path: Path | None = None) -> list[Edge]:
    """Parse the manifest. Raises ValueError on a malformed entry (this is a
    build-time tool: a bad manifest should fail loudly, unlike runtime code)."""
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load pipeline_edges.yaml")
    manifest = Path(path) if path else DEFAULT_MANIFEST
    raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    edges: list[Edge] = []
    seen: set[str] = set()
    for i, e in enumerate(raw.get("edges", [])):
        try:
            prod = e["producer"]
            cons = e["consumer"]
            edge = Edge(
                id=str(e["id"]),
                producer_service=str(prod["service"]),
                producer_files=_as_list(prod["files"]),
                producer_defines=_as_list(prod["defines"]),
                consumer_service=str(cons["service"]),
                consumer_files=_as_list(cons["files"]),
                consumer_references=_as_list(cons["references"]),
                purpose=str(cons.get("purpose", "")),
                cadence=str(e.get("cadence", "")),
                empty_ok=bool(e.get("empty_ok", False)),
                status=str(e.get("status", "wired")),
                gap_ref=str(e.get("gap_ref", "")),
                note=str(e.get("note", "")),
                instrumented=bool(e.get("instrumented", False)),
                stale_after_sec=(float(e["stale_after_sec"]) if e.get("stale_after_sec") is not None else None),
                contract=str(e.get("contract", "")),
                contract_none=str(e.get("contract_none", "")),
                contract_producer_files=_as_list(e.get("contract_producer_files")),
            )
        except KeyError as exc:
            raise ValueError(f"pipeline_edges entry #{i} is missing field {exc}") from exc
        if edge.status not in ("wired", "gap"):
            raise ValueError(f"edge {edge.id!r}: status must be 'wired' or 'gap', got {edge.status!r}")
        if edge.status == "gap" and not edge.gap_ref:
            raise ValueError(f"edge {edge.id!r}: a 'gap' edge must carry a gap_ref")
        if not edge.producer_defines or not edge.consumer_references:
            raise ValueError(f"edge {edge.id!r}: producer.defines and consumer.references must be non-empty")
        if edge.id in seen:
            raise ValueError(f"duplicate edge id {edge.id!r}")
        seen.add(edge.id)
        edges.append(edge)
    return edges


def _strip_comments(text: str) -> str:
    """Drop whole-line comments so a token that only appears in a `# ...`
    explanation does not count as a real call. Docstrings are not stripped
    (tokens are chosen to be call-shaped, e.g. '/portfolio/daily-allocation')."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _read_all(root: Path, rel_files: list[str]) -> tuple[str, list[str]]:
    """(concatenated text, missing relative paths). Directories are scanned
    recursively for *.py so an edge can point at a whole package."""
    chunks: list[str] = []
    missing: list[str] = []
    for rel in rel_files:
        p = root / rel
        if p.is_dir():
            found = False
            for f in sorted(p.rglob("*.py")):
                if "__pycache__" in f.parts or "tests" in f.parts:
                    continue
                chunks.append(_strip_comments(f.read_text(encoding="utf-8", errors="replace")))
                found = True
            if not found:
                missing.append(rel)
        elif p.is_file():
            chunks.append(_strip_comments(p.read_text(encoding="utf-8", errors="replace")))
        else:
            missing.append(rel)
    return "\n".join(chunks), missing


def check_edge(edge: Edge, root: Path | None = None) -> EdgeResult:
    root = Path(root) if root else DEFAULT_ROOT

    producer_text, prod_missing = _read_all(root, edge.producer_files)
    if prod_missing:
        return EdgeResult(edge, STALE, f"producer file(s) not found: {prod_missing}")
    if not any(tok in producer_text for tok in edge.producer_defines):
        return EdgeResult(
            edge, STALE,
            f"producer no longer defines any of {edge.producer_defines} in {edge.producer_files}",
        )

    consumer_text, cons_missing = _read_all(root, edge.consumer_files)
    if cons_missing:
        return EdgeResult(edge, STALE, f"consumer file(s) not found: {cons_missing}")

    matched = [tok for tok in edge.consumer_references if tok in consumer_text]

    if edge.status == "wired":
        if matched:
            if edge.instrumented and f'"{edge.id}"' not in consumer_text and f"'{edge.id}'" not in consumer_text:
                return EdgeResult(
                    edge, DRIFT_NOT_INSTRUMENTED,
                    f"declared instrumented, but {edge.consumer_files} never mention the literal edge id "
                    f"{edge.id!r} (expected a record_edge(...) call)",
                    matched=matched,
                )
            return EdgeResult(edge, OK_WIRED, matched=matched)
        return EdgeResult(
            edge, DRIFT_NOT_WIRED,
            f"declared wired, but {edge.consumer_files} reference none of {edge.consumer_references}",
        )

    # status == "gap"
    if matched:
        return EdgeResult(
            edge, DRIFT_NOW_WIRED,
            f"declared a gap ({edge.gap_ref}) but the consumer now references {matched} -- "
            f"flip this edge to status: wired",
            matched=matched,
        )
    return EdgeResult(edge, OK_GAP, f"known gap, {edge.gap_ref}")


def check_all(edges: list[Edge] | None = None, root: Path | None = None) -> list[EdgeResult]:
    edges = edges if edges is not None else load_edges()
    return [check_edge(e, root) for e in edges]


def format_report(results: list[EdgeResult]) -> str:
    lines = [f"{'STATUS':<16} {'EDGE'}"]
    for r in results:
        lines.append(f"{r.code:<16} {r.edge.id}")
        if r.code in (OK_GAP,):
            lines.append(f"{'':<16}   gap: {r.edge.gap_ref} -- {r.edge.note}")
        elif not r.healthy:
            lines.append(f"{'':<16}   {r.detail}")
    n_gap = sum(1 for r in results if r.code == OK_GAP)
    n_bad = sum(1 for r in results if not r.healthy)
    lines.append("")
    lines.append(
        f"{len(results)} edges: {sum(1 for r in results if r.code == OK_WIRED)} wired, "
        f"{n_gap} known gaps, {n_bad} drifted/stale"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    results = check_all()
    print(format_report(results))
    return 1 if any(not r.healthy for r in results) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
