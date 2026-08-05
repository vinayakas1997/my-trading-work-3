"""Tests for the 9 Section-1 (news-only, ingest-time) analysis methods
in `vinu_news/analysis/methods/`. Every test asserts a real, computed
value against real input — not a smoke test.
"""

import math

from vinu_news.analysis.enrichment.sentiment import score_sentiment
from vinu_news.analysis.methods.event_type_classification import classify_event_type
from vinu_news.analysis.methods.llm_sentiment_classifier_alternatives import classify_non_llm
from vinu_news.analysis.methods.multi_source_triangulation import find_triangulated_stories
from vinu_news.analysis.methods.named_entity_recognition import (
    aggregate_top_entities,
    extract_entities_full,
)
from vinu_news.analysis.methods.news_embedding_regime_detection import detect_regime_shift
from vinu_news.analysis.methods.structured_event_tuple_embeddings import extract_event_tuple
from vinu_news.analysis.methods.tfidf_semantic_clustering import cluster_semantic
from vinu_news.analysis.methods.vader_finance_tuned_sentiment import score_vader_finance
from vinu_news.analysis.methods.velocity_spike_anomaly_detection import (
    detect_velocity_spike,
    detect_zscore_deviation,
)


class TestEventTypeClassification:
    def test_earnings_miss(self):
        text = "Company reports quarterly results that miss estimates, shares fall"
        assert classify_event_type(text, "") == "EARNINGS_MISS"

    def test_ma_announcement(self):
        text = "Acme Corp to acquire Widget Inc for $2 billion"
        assert classify_event_type(text, "") == "MA_ANNOUNCEMENT"

    def test_default_other(self):
        text = "Company announces new logo for anniversary"
        assert classify_event_type(text, "") == "OTHER"


class TestNamedEntityRecognition:
    def test_per_article_extraction(self):
        result = extract_entities_full(
            "Powell warns as Beijing tensions rise, Nvidia surges", ""
        )
        assert result["people"] == ["Jerome Powell"]
        assert result["countries"] == ["CN"]
        assert result["organizations"] == ["NVIDIA"]
        assert result["tickers"] == []

    def test_batch_aggregate_top_entities(self):
        article_a = extract_entities_full(
            "Powell warns as Beijing tensions rise, Nvidia surges", ""
        )
        article_b = extract_entities_full("Powell speaks again on inflation outlook", "")
        agg = aggregate_top_entities([article_a, article_b])
        assert agg["people"][0] == ("Jerome Powell", 2)
        assert agg["organizations"] == [("NVIDIA", 1)]
        assert agg["countries"] == [("CN", 1)]

    def test_cap_at_five_per_category(self):
        headline = "Powell Musk Yellen Bezos Cook Zuckerberg all speak at summit"
        result = extract_entities_full(headline, "")
        assert len(result["people"]) <= 5


class TestVelocitySpikeAnomalyDetection:
    def test_ratio_spike_high_severity(self):
        result = detect_velocity_spike(recent_count=15, older_count=3)
        assert result == {"velocity_spike": True, "severity": "high", "ratio": 5.0}

    def test_ratio_no_spike_below_threshold(self):
        result = detect_velocity_spike(recent_count=2, older_count=1)
        assert result["velocity_spike"] is False
        assert result["severity"] is None

    def test_ratio_no_spike_when_absolute_volume_too_low(self):
        # ratio=4.0 (>=3.0) but recent_count=4 (<5) -> must not fire.
        result = detect_velocity_spike(recent_count=4, older_count=1)
        assert result["velocity_spike"] is False

    def test_zscore_critical_deviation(self):
        history = [3, 4, 5, 6, 7] * 6  # 30 samples, mean=5, pstdev=sqrt(2)
        result = detect_zscore_deviation(history, current_count=20)
        assert result["deviation"] is True
        assert result["severity"] == "critical"
        assert result["z_score"] == 10.6066

    def test_zscore_insufficient_sample_size(self):
        result = detect_zscore_deviation([5] * 10, current_count=20)
        assert result == {"deviation": False, "severity": None, "z_score": 0.0}


class TestMultiSourceTriangulation:
    def test_three_independent_sources_confirm_story(self):
        articles = [
            {
                "id": "a1",
                "headline": "NVIDIA reports record quarterly revenue growth surge",
                "summary": "",
                "source": "REUTERS",
            },
            {
                "id": "a2",
                "headline": "NVIDIA reports record quarterly revenue growth surge today",
                "summary": "",
                "source": "BLOOMBERG",
            },
            {
                "id": "a3",
                "headline": "NVIDIA reports record quarterly revenue growth surge again",
                "summary": "",
                "source": "CNBC",
            },
            {
                "id": "a4",
                "headline": "Tesla recalls vehicles over battery defect issue",
                "summary": "",
                "source": "AP",
            },
        ]
        signals = find_triangulated_stories(articles)
        assert len(signals) == 1
        assert signals[0]["triangulation"] is True
        assert signals[0]["severity"] == "medium"
        assert set(signals[0]["sources"]) == {"REUTERS", "BLOOMBERG", "CNBC"}
        assert set(signals[0]["article_ids"]) == {"a1", "a2", "a3"}

    def test_single_source_never_triangulates(self):
        articles = [
            {"id": "a1", "headline": "Solo scoop about a niche event", "summary": "", "source": "REUTERS"},
        ]
        assert find_triangulated_stories(articles) == []


class TestTfidfSemanticClustering:
    def test_clusters_sorted_largest_first(self):
        articles = [
            {"id": "a1", "headline": "NVIDIA reports record quarterly revenue growth surge", "summary": ""},
            {"id": "a2", "headline": "NVIDIA reports record quarterly revenue growth surge today", "summary": ""},
            {"id": "a3", "headline": "NVIDIA reports record quarterly revenue growth surge again", "summary": ""},
            {"id": "a4", "headline": "Tesla recalls vehicles over battery defect issue", "summary": ""},
        ]
        clusters = cluster_semantic(articles)
        assert clusters[0] == ["a1", "a2", "a3"]
        assert clusters[1] == ["a4"]


class TestVaderFinanceTunedSentiment:
    def test_compound_matches_vader_normalization_of_existing_lexicon(self):
        text = "NVIDIA profit surges, beats estimates, but chip shortage fears warning looms"
        base = score_sentiment(text)
        result = score_vader_finance(text)
        expected_compound = round(
            base["sentiment_score"] / math.sqrt(base["sentiment_score"] ** 2 + 15), 4
        )
        assert result["compound"] == expected_compound
        assert result["sentiment"] == "BULLISH"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_neutral_zero_hit_text(self):
        result = score_vader_finance("Report released today discussing quarterly schedule")
        assert result == {"compound": 0.0, "sentiment": "NEUTRAL", "confidence": 0.0}


class TestLlmSentimentClassifierAlternativesNonLlmPath:
    def test_wraps_finbert_output_shape(self, monkeypatch):
        def fake_score_finbert(text: str) -> dict:
            return {"finbert_label": "positive", "finbert_score": 0.83}

        monkeypatch.setattr(
            "vinu_news.analysis.methods.llm_sentiment_classifier_alternatives.score_finbert",
            fake_score_finbert,
        )
        result = classify_non_llm("Apple beats earnings estimates")
        assert result == {"label": "positive", "score": 0.83}


class TestStructuredEventTupleEmbeddings:
    def test_extracts_actor_action_object_and_event_type(self):
        result = extract_event_tuple("Elon Musk sues Apple over patent claims", "")
        assert result == {
            "actor": "Elon Musk",
            "action": "sues",
            "object": "Apple",
            "event_type": "LITIGATION",
        }

    def test_no_action_verb_present(self):
        result = extract_event_tuple("A quiet day at Apple headquarters", "")
        assert result["action"] is None


class TestNewsEmbeddingRegimeDetection:
    def test_detects_shift_at_topic_boundary_not_within_similar_buckets(self):
        bucket1 = [
            "Fed raises interest rates amid inflation concerns today",
            "Federal Reserve interest rate hike surprises markets today",
            "Interest rate hike expected as inflation concerns persist today",
        ]
        bucket2 = [
            "Fed raises interest rates amid inflation concerns again",
            "Federal Reserve interest rate hike surprises markets again",
            "Interest rate hike expected as inflation concerns continue again",
        ]
        bucket3 = [
            "Apple unveils new smartphone with advanced camera",
            "Tech giant launches latest AI powered device",
            "New iPhone model announced with innovative features",
        ]
        result = detect_regime_shift([bucket1, bucket2, bucket3])
        assert result["regime_shift"] is True
        assert result["shift_boundaries"] == [1]
        assert len(result["centroid_distances"]) == 2
        assert result["centroid_distances"][0] < 0.5
        assert result["centroid_distances"][1] >= 0.5
        assert len(result["dispersion"]) == 3

    def test_single_bucket_no_shift(self):
        result = detect_regime_shift([["Only one bucket of news here"]])
        assert result["regime_shift"] is False
        assert result["shift_boundaries"] == []
