from __future__ import annotations

import json
import time

from vinu_infra.reflection import Finding, POLARITY_HIGHER_IS_WORSE, ReflectionStore, write_finding

from vinu_reflection.reflection import brain


def _store(tmp_path) -> ReflectionStore:
    return ReflectionStore(tmp_path / "reflection.db")


def _write_belief(store, *, analyst_name="decision_process", scope_type="system",
                   scope_key="orchestrator", cluster="Decision-Process / Cognition", psi=0.3) -> None:
    store.upsert_reference_config(
        analyst_name=analyst_name, scope_type=scope_type, metric_name="retry_rejection_delta",
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
    )
    write_finding(store, Finding(
        analyst_name=analyst_name, cluster=cluster, scope_type=scope_type, scope_key=scope_key,
        signal_json={"retry_rejection_delta": 0.3}, evidence_count=40, primary_metric=0.3,
        metric_name="retry_rejection_delta", psi=psi,
    ))


class _FakeLLM:
    def __init__(self, content: str | None = None, raise_exc: Exception | None = None):
        self._content = content
        self._raise_exc = raise_exc
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None, **kwargs) -> dict:
        self.calls.append(messages)
        if self._raise_exc:
            raise self._raise_exc
        return {"content": self._content}


_VALID_RESPONSE = (
    "```json\n"
    + json.dumps({
        "connections": [],
        "maturity_profile": {c: {"status": "insufficient_evidence", "rationale": ""} for c in brain.CLUSTERS},
        "proposed_action": {
            "type": "threshold_nudge", "description": "watch decision_process",
            "target_analyst_name": "decision_process", "target_scope_type": "system",
            "target_scope_key": "orchestrator",
        },
    })
    + "\n```"
)


class TestGatherSynthesisInputs:
    def test_empty_store_returns_nothing(self, tmp_path):
        assert brain.gather_synthesis_inputs(_store(tmp_path)) == []

    def test_only_non_routine_beliefs_included(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.02)  # routine -> never written
        assert brain.gather_synthesis_inputs(store) == []
        _write_belief(store, psi=0.3)  # notable/significant -> written
        result = brain.gather_synthesis_inputs(store)
        assert len(result) == 1
        assert result[0]["analyst_name"] == "decision_process"


class TestRunSynthesis:
    def test_nothing_to_synthesize_writes_nothing_and_skips_the_llm_call(self, tmp_path):
        store = _store(tmp_path)
        llm = _FakeLLM(content=_VALID_RESPONSE)
        assert brain.run_synthesis(store, llm) is None
        assert llm.calls == []
        assert store.get_latest_synthesis() is None

    def test_valid_response_writes_a_real_row(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        llm = _FakeLLM(content=_VALID_RESPONSE)
        synthesis_id = brain.run_synthesis(store, llm)
        assert synthesis_id
        row = store.get_latest_synthesis()
        assert row["synthesis_id"] == synthesis_id
        assert row["proposed_action_type"] == "threshold_nudge"
        assert row["resolution_criteria"]
        assert row["evidence_count_at_synthesis"] == 40
        assert row["inputs_snapshot"][0]["analyst_name"] == "decision_process"
        assert row["resolve_by"] > time.time()

    def test_malformed_llm_response_writes_nothing(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        llm = _FakeLLM(content="not json at all")
        assert brain.run_synthesis(store, llm) is None
        assert store.get_latest_synthesis() is None

    def test_llm_missing_maturity_profile_writes_nothing(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        llm = _FakeLLM(content="```json\n" + json.dumps({"connections": []}) + "\n```")
        assert brain.run_synthesis(store, llm) is None

    def test_llm_call_failure_fails_open_writes_nothing(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        llm = _FakeLLM(raise_exc=ConnectionError("down"))
        assert brain.run_synthesis(store, llm) is None
        assert store.get_latest_synthesis() is None

    def test_invalid_action_type_is_dropped_not_crashed_on(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        body = {
            "connections": [],
            "maturity_profile": {c: {"status": "insufficient_evidence"} for c in brain.CLUSTERS},
            "proposed_action": {"type": "something_made_up"},
        }
        llm = _FakeLLM(content="```json\n" + json.dumps(body) + "\n```")
        synthesis_id = brain.run_synthesis(store, llm)
        assert synthesis_id
        row = store.get_latest_synthesis()
        assert row["proposed_action_type"] is None


class TestResolvePendingSyntheses:
    def test_no_pending_rows_resolves_nothing(self, tmp_path):
        store = _store(tmp_path)
        assert brain.resolve_pending_syntheses(store) == 0

    def test_narrative_only_action_resolves_inconclusive(self, tmp_path):
        store = _store(tmp_path)
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={"proposed_action": {"type": "narrative_only"}},
            proposed_action_type="narrative_only", resolution_criteria="", resolve_by=1.0,
            evidence_count_at_synthesis=0,
        )
        assert brain.resolve_pending_syntheses(store) == 1
        row = store.get_latest_synthesis()
        assert row["outcome_match"] == "inconclusive"

    def test_threshold_nudge_resolves_correct_when_belief_unchanged_since_synthesis(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        belief = store.get_belief("decision_process", "system", "orchestrator")
        store.record_synthesis(
            trigger_reason="scheduled",
            inputs_snapshot=[{"analyst_name": "decision_process", "scope_type": "system",
                               "scope_key": "orchestrator", "computed_at": belief["computed_at"]}],
            prediction_json={"proposed_action": {
                "type": "threshold_nudge", "target_analyst_name": "decision_process",
                "target_scope_type": "system", "target_scope_key": "orchestrator",
            }},
            proposed_action_type="threshold_nudge", resolution_criteria="x", resolve_by=1.0,
            evidence_count_at_synthesis=40,
        )
        assert brain.resolve_pending_syntheses(store) == 1
        row = store.get_latest_synthesis()
        assert row["outcome_match"] == "correct"

    def test_threshold_nudge_resolves_incorrect_when_still_significant(self, tmp_path):
        store = _store(tmp_path)
        _write_belief(store, psi=0.3)
        belief = store.get_belief("decision_process", "system", "orchestrator")
        store.record_synthesis(
            trigger_reason="scheduled",
            inputs_snapshot=[{"analyst_name": "decision_process", "scope_type": "system",
                               "scope_key": "orchestrator", "computed_at": belief["computed_at"]}],
            prediction_json={"proposed_action": {
                "type": "threshold_nudge", "target_analyst_name": "decision_process",
                "target_scope_type": "system", "target_scope_key": "orchestrator",
            }},
            proposed_action_type="threshold_nudge", resolution_criteria="x", resolve_by=1.0,
            evidence_count_at_synthesis=40,
        )
        # A fresh write for the same scope, still significant -- simulates
        # the nudge not having helped.
        _write_belief(store, psi=0.3)
        assert brain.resolve_pending_syntheses(store) == 1
        row = store.get_latest_synthesis()
        assert row["outcome_match"] == "incorrect"

    def test_threshold_nudge_missing_target_belief_is_inconclusive(self, tmp_path):
        store = _store(tmp_path)
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[],
            prediction_json={"proposed_action": {
                "type": "threshold_nudge", "target_analyst_name": "nobody",
                "target_scope_type": "system", "target_scope_key": "nothing",
            }},
            proposed_action_type="threshold_nudge", resolution_criteria="x", resolve_by=1.0,
            evidence_count_at_synthesis=0,
        )
        assert brain.resolve_pending_syntheses(store) == 1
        row = store.get_latest_synthesis()
        assert row["outcome_match"] == "inconclusive"

    def test_resolved_rows_are_not_resolved_again(self, tmp_path):
        store = _store(tmp_path)
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type=None, resolution_criteria="", resolve_by=1.0,
            evidence_count_at_synthesis=0,
        )
        assert brain.resolve_pending_syntheses(store) == 1
        assert brain.resolve_pending_syntheses(store) == 0
