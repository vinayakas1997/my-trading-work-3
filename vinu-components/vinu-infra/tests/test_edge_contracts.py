"""Layer B: every wired connection has a contract (a pydantic model) or a written reason for having none, and
the contract is backed by the source on both sides."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra import edge_contracts as ec
from vinu_infra.pipeline_edges import Edge, load_edges


def _edge(tmp_path: Path, *, producer: str, consumer: str, edge_id: str = "portfolio.state->live.scheduler",
          **kw) -> tuple[Edge, Path]:
    (tmp_path / "p.py").write_text(producer, encoding="utf-8")
    (tmp_path / "c.py").write_text(consumer, encoding="utf-8")
    edge = Edge(
        id=edge_id, producer_service="a", producer_files=["p.py"], producer_defines=["x"],
        consumer_service="b", consumer_files=["c.py"], consumer_references=["x"],
        contract=kw.pop("contract", "PortfolioState"), **kw,
    )
    return edge, tmp_path


GOOD_PRODUCER = 'out = {"weights": [], "status": "ok", "correlation_matrix": None, "n_strategies": 0,\n' \
                '       "name": 1, "symbol": 2, "target_weight": 3, "kind": 4}\n'
GOOD_CONSUMER = 'rows = data.get("weights")\nname, symbol, target_weight = "name", "symbol", "target_weight"\n'


# ---- the real manifest

def test_every_wired_edge_has_a_contract_or_a_reason():
    problems = []
    for e in load_edges():
        problems += ec.static_problems(e)
    assert problems == []


def test_a_contract_none_reason_is_not_a_blank_excuse():
    for e in load_edges():
        if e.contract_none:
            assert len(e.contract_none) > 25, e.id


def test_every_registered_contract_belongs_to_a_real_edge_and_names_match():
    by_id = {e.id: e for e in load_edges()}
    for edge_id, model in ec.CONTRACTS.items():
        assert edge_id in by_id, f"{model.__name__} is registered for unknown edge {edge_id}"
        assert by_id[edge_id].contract == model.__name__


def test_every_contract_has_examples_that_validate():
    for edge_id, model in ec.CONTRACTS.items():
        examples = model.model_config["json_schema_extra"]["examples"]
        assert examples, model.__name__
        for ex in examples:
            assert model.model_validate(ex) is not None, (edge_id, ex)


def test_contracted_edge_count_is_reported_and_not_shrinking():
    contracted = [e for e in load_edges() if e.contract]
    assert len(contracted) >= 15


# ---- check_payload (what layer C will call)

def test_check_payload_accepts_the_example_and_extra_keys():
    ex = dict(ec.contract_example("portfolio.state->live.scheduler"), brand_new_key=1)
    assert ec.check_payload("portfolio.state->live.scheduler", ex) == []


def test_check_payload_names_a_missing_required_field():
    problems = ec.check_payload("portfolio.state->live.scheduler", {"status": "ok"})
    assert problems and problems[0].startswith("weights")


def test_check_payload_names_a_bad_nested_value():
    bad = {"weights": [{"name": "a", "target_weight": "lots"}]}
    problems = ec.check_payload("portfolio.state->live.scheduler", bad)
    assert any("weights.0.target_weight" in p for p in problems)


def test_check_payload_on_a_non_object_is_a_problem_not_a_crash():
    assert ec.check_payload("portfolio.state->live.scheduler", [1, 2])
    assert ec.check_payload("portfolio.state->live.scheduler", None)


def test_check_payload_for_an_edge_without_a_contract_is_clean():
    assert ec.check_payload("halt_flag->live.scheduler", {"anything": 1}) == []
    assert ec.check_payload("no.such->edge", {}) == []


def test_empty_answers_stay_valid_shapes():
    assert ec.check_payload("portfolio.state->live.scheduler", {"status": "empty", "weights": []}) == []
    assert ec.check_payload("reflection.synthesis->agent.idea_generator", {"status": "none"}) == []
    assert ec.check_payload("reflection.notable_beliefs->agent.live_decision_context", {"beliefs": []}) == []


def test_status_none_on_a_non_ok_answer_does_not_hide_a_missing_key():
    # a producer that renames `beliefs` must be visible
    assert ec.check_payload("reflection.notable_beliefs->agent.live_decision_context", {"items": []})


def test_schema_and_example_helpers():
    schema = ec.contract_schema("portfolio.state->live.scheduler")
    assert "weights" in schema["properties"]
    assert ec.contract_schema("halt_flag->live.scheduler") is None
    assert ec.contract_example("halt_flag->live.scheduler") is None


def test_field_names_marks_nested_fields_required_only_through_required_parents():
    names = dict(ec.field_names(ec.PortfolioState))
    assert names["weights"] is True and names["target_weight"] is True
    assert names["status"] is False
    # correlation_matrix is optional, so what is inside it is not something a consumer must read
    assert names["strategies"] is False and names["values"] is False


# ---- the static check catches drift on either side (mutation checks)

def test_static_check_passes_when_both_sides_mention_the_fields(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER + '"strategies": 1, "values": 2\n', consumer=GOOD_CONSUMER)
    assert ec.static_problems(edge, root) == []


def test_static_check_catches_a_field_renamed_in_the_producer(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER.replace('"weights"', '"allocations"') + '"strategies": 1, "values": 2\n',
                       consumer=GOOD_CONSUMER)
    problems = ec.static_problems(edge, root)
    assert any("'weights' is not mentioned in the producer" in p for p in problems)


def test_static_check_catches_a_required_field_the_consumer_no_longer_reads(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER + '"strategies": 1, "values": 2\n',
                       consumer='x = 1\n')
    problems = ec.static_problems(edge, root)
    assert any("required field 'weights' is not mentioned in the consumer" in p for p in problems)


def test_static_check_does_not_demand_optional_fields_from_the_consumer(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER + '"strategies": 1, "values": 2\n', consumer=GOOD_CONSUMER)
    assert not any("required field 'status'" in p for p in ec.static_problems(edge, root))


def test_static_check_extra_producer_files_are_searched(tmp_path):
    (tmp_path / "more.py").write_text('"strategies": 1, "values": 2\n', encoding="utf-8")
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER, consumer=GOOD_CONSUMER,
                       contract_producer_files=["more.py"])
    assert ec.static_problems(edge, root) == []


def test_static_check_requires_a_contract_or_a_reason(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER, consumer=GOOD_CONSUMER, contract="")
    assert any("no contract and no contract_none" in p for p in ec.static_problems(edge, root))
    edge.contract_none = "in-process call, nothing on the wire"
    assert ec.static_problems(edge, root) == []


def test_static_check_rejects_an_unregistered_model_name(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER, consumer=GOOD_CONSUMER,
                       edge_id="not.registered->anywhere", contract="Ghost")
    assert any("not registered" in p for p in ec.static_problems(edge, root))


def test_static_check_rejects_a_manifest_name_that_differs_from_the_registered_model(tmp_path):
    edge, root = _edge(tmp_path, producer=GOOD_PRODUCER + '"strategies": 1, "values": 2\n', consumer=GOOD_CONSUMER,
                       contract="DailyAllocation")
    assert any("registered model is 'PortfolioState'" in p for p in ec.static_problems(edge, root))


def test_gap_edges_are_not_held_to_a_contract(tmp_path):
    edge, root = _edge(tmp_path, producer="", consumer="", contract="")
    edge.status = "gap"
    assert ec.static_problems(edge, root) == []


def test_duplicate_registration_is_refused():
    with pytest.raises(ValueError):
        @ec.contract_for("portfolio.state->live.scheduler")
        class _Dup(ec.EdgeContract):  # noqa: F841
            x: int = 0
