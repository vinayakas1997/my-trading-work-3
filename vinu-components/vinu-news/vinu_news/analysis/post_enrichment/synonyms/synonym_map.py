"""Synonym replacement map (Fincept news_intelligence_pipeline Section 4)."""

# Longest phrases first when applying in normalize.py
SYNONYM_MAP = {
    # Sanctions / rates (Fincept starter)
    "sanctioned": "sanction",
    "sanctions": "sanction",
    "interest rates": "interest_rate",
    "interest rate": "interest_rate",
    "rate hikes": "rate_hike",
    "rate hike": "rate_hike",
    "rate hiked": "rate_hike",
    "hiked rates": "rate_hike",
    "rate cuts": "rate_cut",
    "rate cut": "rate_cut",
    "cutting rates": "rate_cut",
    "rates": "interest_rate",
    "rate": "interest_rate",
    "hikes": "rate_hike",
    "hiked": "rate_hike",
    "cuts": "rate_cut",
    "cutting": "rate_cut",
    # Earnings
    "earnings beat": "earnings_beat",
    "beats estimates": "earnings_beat",
    "beat estimates": "earnings_beat",
    "earnings miss": "earnings_miss",
    "misses estimates": "earnings_miss",
    "miss estimates": "earnings_miss",
    "revenue beat": "revenue_beat",
    "revenue miss": "revenue_miss",
    "eps beat": "eps_beat",
    "eps miss": "eps_miss",
    # M&A
    "mergers": "merger",
    "acquisitions": "acquisition",
    "takeover bid": "takeover",
    "buyout offer": "buyout",
    # Macro
    "inflationary": "inflation",
    "consumer price index": "cpi",
    "gross domestic product": "gdp",
    "unemployment rate": "unemployment",
    "jobless claims": "unemployment",
    # Crypto
    "bitcoin price": "bitcoin",
    "ethereum price": "ethereum",
    "crypto market": "crypto",
}
