"""Sector category refinement waterfall (Fincept Section 6B)."""

CATEGORY_KEYWORDS = [
    ("EARNINGS", ("earnings", "quarterly results", "eps", "guidance")),
    ("CRYPTO", ("crypto", "bitcoin", "ethereum", "blockchain")),
    ("DEFENSE", ("missile", "troops", "pentagon", "military")),
    (
        "ECONOMIC",
        ("fed ", "federal reserve", "inflation", "gdp", "interest rate", "central bank"),
    ),
    ("MARKETS", ("s&p 500", "nasdaq", "dow jones", "stock market")),
    ("ENERGY", ("energy", "crude", "opec", "natural gas", "oil price")),
    ("TECH", ("tech", " ai ", "artificial intelligence", "semiconductor", "startup")),
    (
        "GEOPOLITICS",
        ("nato", "ukraine", "russia", "china", "gaza", "sanctions", "geopolit"),
    ),
]


def refine_category(combined_text: str, default: str = "MARKETS") -> str:
    """Override feed default category using first matching keyword group."""
    lower = combined_text.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return category
    return default
