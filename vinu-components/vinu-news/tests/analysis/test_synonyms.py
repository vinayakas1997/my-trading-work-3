"""Tests for synonym normalization."""

from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text


def test_sanctioned_becomes_sanction():
    result = normalize_text("Russia sanctioned over trade dispute")
    assert "sanction" in result
    assert "sanctioned" not in result


def test_rate_synonyms():
    result = normalize_text("Fed cuts rates amid inflation")
    assert "interest_rate" in result or "rate_cut" in result
