"""Tests for rule-based NER."""

from vinu_news.analysis.post_enrichment.ner.extract_entities import extract_entities


def test_powell_extracted():
    entities = extract_entities("Powell warns on inflation", "")
    assert "Jerome Powell" in entities["people"]


def test_beijing_maps_to_cn():
    entities = extract_entities("Markets react as Beijing announces policy", "")
    assert "CN" in entities["countries"]
