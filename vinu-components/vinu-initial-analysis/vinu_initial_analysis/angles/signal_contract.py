"""Signal-usage contract — tags angle output with what it's actually proven
for, so the constraint travels with the value instead of living only in a
docstring a caller has to go read separately.

Source of truth for the tags below: the confirmed negative result on
direction prediction (rule-based sentiment_score, then FinBERT finbert_score,
tested against AAPL/TSLA/JNJ, ~50% sign-agreement — see
`significance_model.py`'s module docstring and
`01-the-stage-2-claude/full-plan.md:68-74`) and the leak-safety notes in
`regime_features.py`. Add a field here only when there's an actual tested
result backing the proven_for/not_proven_for split — this is not a place to
guess.
"""

from __future__ import annotations

SIGNAL_USAGE_CONTRACT: dict[str, dict[str, list[str] | str]] = {
    "significance_score": {
        "proven_for": ["magnitude_prioritization", "surprise_prediction"],
        "not_proven_for": ["direction", "sign_of_price_move"],
        "evidence_ref": "01-the-stage-2-claude/full-plan.md:68-74",
    },
    "regime_feature": {
        "proven_for": ["volatility_bucketing", "regime_labeling"],
        "not_proven_for": ["direction_prediction", "forward_return_prediction"],
        "evidence_ref": "vinu_initial_analysis/angles/news_price_causality/regime_features.py",
    },
}


def tag_row(row: dict, field: str) -> dict:
    """Attach proven_for/not_proven_for/evidence_ref for `field` onto `row`,
    in place. No-op if `field` has no registered contract."""
    contract = SIGNAL_USAGE_CONTRACT.get(field)
    if contract is not None:
        row[f"{field}_proven_for"] = contract["proven_for"]
        row[f"{field}_not_proven_for"] = contract["not_proven_for"]
        row[f"{field}_evidence_ref"] = contract["evidence_ref"]
    return row
