"""The model server wedges (one frozen request, every call behind it times out) and its health check still says healthy.
scripts/model_guard.py restarts it when the slot has not advanced for STALL_AFTER_SEC (problem log O19)."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("model_guard", Path(__file__).resolve().parents[2] / "scripts" / "model_guard.py")
mg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mg)


def _slot(task=1, decoded=410, busy=True):
    return {"id_task": task, "is_processing": busy, "n_prompt_tokens_processed": 2400, "next_token": [{"n_decoded": decoded}]}


def test_the_signature_is_the_busy_slots_task_and_token_count():
    assert mg.slot_signature([_slot(7, 12)]) == (7, 12, 2400)
    assert mg.slot_signature([_slot(busy=False)]) is None


def test_a_slot_that_keeps_advancing_is_never_restarted():
    state = {}
    for i in range(40):                                              # 40 minutes of a long but healthy generation
        state, restart = mg.decide(state, mg.slot_signature([_slot(1, 100 + i)]), 1000.0 + i * 60)
        assert not restart


def test_a_frozen_slot_is_restarted_once_it_has_been_frozen_long_enough_then_left_alone():
    sig = mg.slot_signature([_slot(1, 410)])
    state, restart = mg.decide({}, sig, 1000.0)
    assert not restart
    state, restart = mg.decide(state, sig, 1000.0 + mg.STALL_AFTER_SEC - 1)
    assert not restart                                               # not yet
    state, restart = mg.decide(state, sig, 1000.0 + mg.STALL_AFTER_SEC)
    assert restart
    state, restart = mg.decide(state, sig, 1000.0 + mg.STALL_AFTER_SEC + 60)
    assert not restart                                               # cooling down while the model loads


def test_an_idle_slot_clears_the_memory_so_the_next_request_starts_a_fresh_count():
    sig = mg.slot_signature([_slot(1, 410)])
    state, _ = mg.decide({}, sig, 1000.0)
    state, restart = mg.decide(state, None, 1100.0)
    assert not restart and "signature" not in state


def test_the_scheduled_task_installer_names_the_script_and_a_one_minute_repeat():
    ps = (Path(__file__).resolve().parents[2] / "scripts" / "install_model_guard.ps1").read_text(encoding="utf-8")
    assert "model_guard.py" in ps and "RepetitionInterval (New-TimeSpan -Minutes 1)" in ps
