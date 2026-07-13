"""Rule-based entity extraction from headline and summary."""

from vinu_news.analysis.post_enrichment.ner.country_map import COUNTRY_MAP
from vinu_news.analysis.post_enrichment.ner.people_map import PEOPLE_MAP


def extract_entities(headline: str, summary: str) -> dict[str, list[str]]:
    """Extract people and country codes from combined text."""
    text = f"{headline} {summary}".lower()
    people: list[str] = []
    countries: list[str] = []
    seen_people: set[str] = set()
    seen_countries: set[str] = set()

    for phrase, canonical in sorted(PEOPLE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in text and canonical not in seen_people:
            seen_people.add(canonical)
            people.append(canonical)

    for phrase, code in sorted(COUNTRY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in text and code not in seen_countries:
            seen_countries.add(code)
            countries.append(code)

    return {"people": people, "countries": countries}
