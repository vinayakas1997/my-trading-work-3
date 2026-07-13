"""LLM prompt templates for article analysis (TASK-N01)."""

MAX_HEADLINE_CHARS = 300
MAX_SUMMARY_CHARS = 300
NO_SUMMARY_PLACEHOLDER = "(not available)"

ANALYSIS_SYSTEM = (
    "You are a financial news analyst. Respond with valid JSON only, no markdown."
)

ANALYSIS_USER_TEMPLATE = """Analyze this financial news article and return JSON with exactly these keys:
- sentiment_score: float from -1.0 (very bearish) to +1.0 (very bullish)
- confidence: integer 0-100
- risk_flags: list of short strings (market risks mentioned)
- summary: one paragraph summary

Headline: {headline}
Summary: {summary}
URL: {url}
"""


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def build_analysis_prompt(headline: str, summary: str | None, url: str) -> str:
    headline_text = _truncate(headline or "", MAX_HEADLINE_CHARS)
    summary_text = _truncate(summary, MAX_SUMMARY_CHARS) if summary else NO_SUMMARY_PLACEHOLDER
    return ANALYSIS_USER_TEMPLATE.format(
        headline=headline_text,
        summary=summary_text,
        url=url,
    )
