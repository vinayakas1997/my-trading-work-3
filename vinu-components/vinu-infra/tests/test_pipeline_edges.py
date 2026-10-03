"""Tests for pipeline_edges.py (Phase 1 of the-inconsistencies-v2/03-implementation-plan.md).

Two layers: the checker's own semantics against throwaway files in tmp_path,
and one test over the REAL manifest + REAL source tree, which is what turns
a missing producer->consumer connection into a failing build.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vinu_infra import pipeline_edges as pe


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")


def _edge(**over) -> pe.Edge:
    base = dict(
        id="a->b",
        producer_service="svc-a", producer_files=["a/prod.py"], producer_defines=["def produce"],
        consumer_service="svc-b", consumer_files=["b/cons.py"], consumer_references=["produce()"],
        status="wired", gap_ref="",
    )
    base.update(over)
    return pe.Edge(**base)


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    _write(tmp_path, "a/prod.py", "def produce():\n    return 1\n")
    _write(tmp_path, "b/cons.py", "from a.prod import produce\nx = produce()\n")
    return tmp_path


# ---------------------------------------------------------------- checker semantics

def test_wired_edge_with_reference_is_ok(tree):
    r = pe.check_edge(_edge(), tree)
    assert r.code == pe.OK_WIRED and r.matched == ["produce()"]


def test_wired_edge_without_reference_is_a_regression(tree):
    _write(tree, "b/cons.py", "x = 1\n")
    r = pe.check_edge(_edge(), tree)
    assert r.code == pe.DRIFT_NOT_WIRED and not r.healthy


def test_gap_edge_still_unwired_is_ok_and_documented(tree):
    _write(tree, "b/cons.py", "x = 1\n")
    r = pe.check_edge(_edge(status="gap", gap_ref="audit A1"), tree)
    assert r.code == pe.OK_GAP and r.healthy and "audit A1" in r.detail


def test_gap_edge_that_becomes_wired_forces_a_manifest_update(tree):
    r = pe.check_edge(_edge(status="gap", gap_ref="audit A1"), tree)
    assert r.code == pe.DRIFT_NOW_WIRED and not r.healthy
    assert "flip this edge to status: wired" in r.detail


def test_reference_only_in_a_comment_does_not_count_as_wired(tree):
    _write(tree, "b/cons.py", "# TODO call produce() here\nx = 1\n")
    assert pe.check_edge(_edge(), tree).code == pe.DRIFT_NOT_WIRED


def test_missing_consumer_file_is_stale(tree):
    r = pe.check_edge(_edge(consumer_files=["b/renamed.py"]), tree)
    assert r.code == pe.STALE and "consumer file" in r.detail


def test_missing_producer_file_is_stale(tree):
    r = pe.check_edge(_edge(producer_files=["a/gone.py"]), tree)
    assert r.code == pe.STALE and "producer file" in r.detail


def test_producer_that_no_longer_defines_the_output_is_stale(tree):
    _write(tree, "a/prod.py", "def renamed():\n    pass\n")
    r = pe.check_edge(_edge(), tree)
    assert r.code == pe.STALE and "no longer defines" in r.detail


def test_directory_scan_skips_tests_and_pycache(tree):
    _write(tree, "b/pkg/real.py", "x = 1\n")
    _write(tree, "b/pkg/tests/test_x.py", "y = produce()\n")
    r = pe.check_edge(_edge(consumer_files=["b/pkg"]), tree)
    assert r.code == pe.DRIFT_NOT_WIRED


# ---------------------------------------------------------------- manifest loading

def _manifest(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "m.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


_GOOD = """
    version: 1
    edges:
      - id: e1
        producer: {service: s, files: [a.py], defines: [x]}
        consumer: {service: t, files: [b.py], references: [y], purpose: p}
        status: wired
"""


def test_load_edges_parses_a_valid_manifest(tmp_path):
    edges = pe.load_edges(_manifest(tmp_path, _GOOD))
    assert [e.id for e in edges] == ["e1"] and edges[0].consumer_references == ["y"]


def test_gap_edge_without_gap_ref_is_rejected(tmp_path):
    body = _GOOD.replace("status: wired", "status: gap")
    with pytest.raises(ValueError, match="gap_ref"):
        pe.load_edges(_manifest(tmp_path, body))


def test_duplicate_ids_are_rejected(tmp_path):
    body = _GOOD + """
      - id: e1
        producer: {service: s, files: [a.py], defines: [x]}
        consumer: {service: t, files: [b.py], references: [y]}
"""
    with pytest.raises(ValueError, match="duplicate"):
        pe.load_edges(_manifest(tmp_path, body))


def test_unknown_status_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="status"):
        pe.load_edges(_manifest(tmp_path, _GOOD.replace("wired", "maybe")))


def test_missing_field_is_rejected(tmp_path):
    body = """
        edges:
          - id: e1
            producer: {service: s, files: [a.py], defines: [x]}
    """
    with pytest.raises(ValueError, match="consumer"):
        pe.load_edges(_manifest(tmp_path, body))


def test_report_lists_gaps_and_summary():
    edges = [_edge(id="ok"), _edge(id="g", status="gap", gap_ref="audit A1", note="why")]
    results = [pe.EdgeResult(edges[0], pe.OK_WIRED), pe.EdgeResult(edges[1], pe.OK_GAP, "known gap")]
    out = pe.format_report(results)
    assert "2 edges: 1 wired, 1 known gaps, 0 drifted/stale" in out and "audit A1 -- why" in out


# ---------------------------------------------------------------- the real manifest

def test_real_manifest_matches_real_source_tree():
    """The point of the whole file: every declared edge is either wired as
    declared, or a documented gap that is still a gap. Anything else --
    a regression, a newly wired gap, a renamed file -- fails the build."""
    results = pe.check_all()
    bad = [f"{r.code} {r.edge.id}: {r.detail}" for r in results if not r.healthy]
    assert not bad, "pipeline_edges.yaml out of sync with the code:\n" + "\n".join(bad)


def test_real_manifest_covers_the_money_path():
    ids = {e.id for e in pe.load_edges()}
    for required in (
        "portfolio.state->live.scheduler",
        "portfolio.daily_allocation->live.scheduler",
        "research.active_trade_plans->live.orchestrator",
        "halt_flag->live.scheduler",
        "breaker.limits->live.scheduler",
    ):
        assert required in ids
    assert len(ids) >= 20


def test_every_real_gap_points_at_an_audit_item():
    for e in pe.load_edges():
        if e.status == "gap":
            assert e.gap_ref and e.note, f"gap edge {e.id} must say which audit item and why"


# ---------------------------------------------------------------- Phase 3: instrumented / stale_after_sec

def test_loader_parses_instrumented_and_stale_after_sec(tmp_path):
    body = """
        edges:
          - id: e1
            producer: {service: s, files: [a.py], defines: [x]}
            consumer: {service: t, files: [b.py], references: [y]}
            instrumented: true
            stale_after_sec: 7200
          - id: e2
            producer: {service: s, files: [a.py], defines: [x]}
            consumer: {service: t, files: [b.py], references: [y]}
    """
    e1, e2 = pe.load_edges(_manifest(tmp_path, body))
    assert (e1.instrumented, e1.stale_after_sec) == (True, 7200.0)
    assert (e2.instrumented, e2.stale_after_sec) == (False, None)


def test_instrumented_edge_must_mention_its_id_in_the_consumer(tree):
    # consumer references the producer but never names the edge id -> not actually instrumented
    r = pe.check_edge(_edge(instrumented=True), tree)
    assert r.code == pe.DRIFT_NOT_INSTRUMENTED and not r.healthy


def test_instrumented_edge_with_the_id_literal_in_the_consumer_is_ok(tree):
    _write(tree, "b/cons.py", 'from a.prod import produce\nx = produce()\nrecord_edge("a->b", "received")\n')
    assert pe.check_edge(_edge(instrumented=True), tree).code == pe.OK_WIRED


def test_an_id_that_only_appears_in_a_comment_does_not_count_as_instrumented(tree):
    _write(tree, "b/cons.py", 'from a.prod import produce\nx = produce()\n# record_edge("a->b", "received")\n')
    assert pe.check_edge(_edge(instrumented=True), tree).code == pe.DRIFT_NOT_INSTRUMENTED


def test_a_non_instrumented_edge_is_unaffected(tree):
    assert pe.check_edge(_edge(instrumented=False), tree).code == pe.OK_WIRED

