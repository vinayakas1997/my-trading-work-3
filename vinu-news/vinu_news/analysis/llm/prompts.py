"""LLM prompt templates for article analysis (TASK-N01)."""

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
