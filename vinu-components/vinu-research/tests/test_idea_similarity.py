from __future__ import annotations

from vinu_research.idea_similarity import build_tfidf_vectors, cosine_similarity, tokenize


class TestTokenize:
    def test_lowercases_and_splits_on_non_alnum(self):
        assert tokenize("SMA Crossover, Trend-Following!") == ["sma", "crossover", "trend", "following"]

    def test_single_char_tokens_are_dropped(self):
        assert tokenize("a b cc") == ["cc"]

    def test_empty_string_returns_empty_list(self):
        assert tokenize("") == []


class TestBuildTfidfVectors:
    def test_empty_input_returns_empty_list(self):
        assert build_tfidf_vectors([]) == []

    def test_one_vector_per_input_text(self):
        vectors = build_tfidf_vectors(["a b", "c d", "e f"])
        assert len(vectors) == 3

    def test_a_term_present_in_every_document_scores_lower_than_a_rare_one(self):
        # "strategy" appears in all three; "bollinger" only in one --
        # IDF should reward the distinctive term.
        vectors = build_tfidf_vectors([
            "momentum strategy", "reversion strategy", "bollinger strategy",
        ])
        assert vectors[2]["bollinger"] > vectors[2]["strategy"]


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        vectors = build_tfidf_vectors(["momentum trend following", "unrelated text here"])
        assert cosine_similarity(vectors[0], vectors[0]) == 1.0

    def test_disjoint_vocabularies_score_zero(self):
        vectors = build_tfidf_vectors(["momentum trend following", "bollinger bands mean reversion"])
        assert cosine_similarity(vectors[0], vectors[1]) == 0.0

    def test_empty_vector_scores_zero_not_a_crash(self):
        assert cosine_similarity({}, {"a": 1.0}) == 0.0
        assert cosine_similarity({"a": 1.0}, {}) == 0.0

    def test_shared_vocabulary_scores_between_zero_and_one(self):
        vectors = build_tfidf_vectors([
            "SMA crossover trend following strategy",
            "moving average crossover trend-following strategy",
            "RSI mean reversion for oversold conditions",
        ])
        same_family = cosine_similarity(vectors[0], vectors[1])
        different_family = cosine_similarity(vectors[0], vectors[2])
        assert 0.0 < same_family < 1.0
        assert same_family > different_family
