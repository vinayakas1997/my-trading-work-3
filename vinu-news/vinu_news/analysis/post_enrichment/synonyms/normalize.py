"""Apply synonym normalization for dedup vectorization."""

from vinu_news.analysis.post_enrichment.synonyms.synonym_map import SYNONYM_MAP


def normalize_text(text: str) -> str:
    """Lowercase, apply synonym replacements, collapse whitespace."""
    result = text.lower()
    for phrase, replacement in sorted(SYNONYM_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(phrase, replacement)
    return " ".join(result.split())
