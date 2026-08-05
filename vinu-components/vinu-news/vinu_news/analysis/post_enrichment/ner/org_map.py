"""Known organization/institution name mappings (Fincept NER).

New dictionary — organizations are the "genuinely new capability" flagged
in `02-named-entity-recognition.md`'s notes (nothing in `vinu-news`
previously extracted *who* an article is about beyond ticker mentions).
Same style/shape as `people_map.py` and `country_map.py`: lowercase
phrase -> canonical display name, longest-phrase-first matching handled
by the caller.
"""

ORG_MAP = {
    # Central banks / regulators
    "the fed": "Federal Reserve",
    "federal reserve": "Federal Reserve",
    "european central bank": "European Central Bank",
    "ecb": "European Central Bank",
    "bank of england": "Bank of England",
    "bank of japan": "Bank of Japan",
    "people's bank of china": "People's Bank of China",
    "sec": "Securities and Exchange Commission",
    "securities and exchange commission": "Securities and Exchange Commission",
    "department of justice": "Department of Justice",
    "doj": "Department of Justice",
    "federal trade commission": "Federal Trade Commission",
    "ftc": "Federal Trade Commission",
    "imf": "International Monetary Fund",
    "world bank": "World Bank",
    "opec": "OPEC",
    "nato": "NATO",
    "united nations": "United Nations",
    # Big tech / frequently mentioned companies
    "nvidia": "NVIDIA",
    "apple": "Apple",
    "microsoft": "Microsoft",
    "amazon": "Amazon",
    "google": "Google",
    "alphabet": "Alphabet",
    "meta": "Meta",
    "facebook": "Meta",
    "tesla": "Tesla",
    "openai": "OpenAI",
    "berkshire hathaway": "Berkshire Hathaway",
    "goldman sachs": "Goldman Sachs",
    "jpmorgan": "JPMorgan",
    "jp morgan": "JPMorgan",
    "morgan stanley": "Morgan Stanley",
    "blackrock": "BlackRock",
    "moody's": "Moody's",
    "standard & poor's": "S&P Global",
    "s&p global": "S&P Global",
    "fitch ratings": "Fitch Ratings",
    # Exchanges / indices
    "nasdaq": "Nasdaq",
    "new york stock exchange": "NYSE",
    "nyse": "NYSE",
    "world health organization": "World Health Organization",
    "who": "World Health Organization",
}
