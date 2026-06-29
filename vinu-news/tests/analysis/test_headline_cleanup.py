"""Tests for headline cleanup."""

from vinu_news.analysis.post_enrichment.headline_cleanup import clean_headline_for_dedup


def test_strips_breaking_prefix():
    assert clean_headline_for_dedup("BREAKING: Fed holds rates") == "Fed holds rates"


def test_strips_bracket_prefix():
    assert clean_headline_for_dedup("[UPDATE] Oil prices surge") == "Oil prices surge"
