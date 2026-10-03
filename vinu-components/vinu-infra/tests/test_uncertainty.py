"""v2 B2: the single read-only uncertainty assessment."""

from vinu_infra.uncertainty import assess_uncertainty


def _known(**kw):
    base = dict(novelty={"status": "ok", "novelty_high": False}, outcomes_recorded=50, evidence_ok=True,
                maturity_tier="mature", precondition_tested=True)
    base.update(kw)
    return assess_uncertainty(**base)


def test_everything_known_is_low_with_no_reasons():
    r = _known()
    assert r == {"level": "low", "points": 0, "reasons": [], "missing_inputs": []}


def test_high_novelty_alone_is_medium_and_with_thin_evidence_is_high():
    assert _known(novelty={"status": "ok", "novelty_high": True})["level"] == "medium"
    r = _known(novelty={"status": "ok", "novelty_high": True}, outcomes_recorded=0, maturity_tier="paper_only")
    assert r["level"] == "high" and "novelty_high" in r["reasons"] and "no_recorded_outcomes" in r["reasons"]


def test_missing_inputs_are_named_and_distinct_from_a_neutral_known_state():
    r = _known(live_snapshot_present=False, evidence_ok=False, strategy_config_present=False)
    assert r["level"] == "high"
    assert {"live_snapshot", "signal_evidence", "strategy_config"} <= set(r["missing_inputs"])


def test_an_unrun_novelty_check_is_listed_missing_but_not_scored():
    r = _known(novelty=None)
    assert r["level"] == "low" and r["missing_inputs"] == ["novelty"] and r["points"] == 0


def test_few_outcomes_and_untested_precondition_add_points_and_unknown_values_are_ignored():
    r = _known(outcomes_recorded=5, precondition_tested=False)
    assert r["points"] == 2 and r["level"] == "medium"
    r = assess_uncertainty()   # nothing passed: only the unrun novelty is flagged
    assert r["level"] == "low"
