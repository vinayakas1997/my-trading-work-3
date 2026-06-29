"""Source credibility flagging (Fincept Section 6I)."""

STATE_MEDIA_SOURCES = frozenset({
    "XINHUA",
    "CGTN",
    "GLOBAL TIMES",
    "RT",
    "TASS",
    "SPUTNIK",
    "PRESS TV",
    "KCNA",
    "TRT WORLD",
    "AL ARABIYA",
})

CAUTION_SOURCES = frozenset({
    "ZEROHEDGE",
    "INFOWARS",
    "DAILY MAIL",
    "NY POST",
})

SOURCE_FLAG_NONE = 0
SOURCE_FLAG_STATE_MEDIA = 1
SOURCE_FLAG_CAUTION = 2


def check_source_flag(source: str) -> int:
    """Return credibility flag: 0=NONE, 1=STATE_MEDIA, 2=CAUTION."""
    upper = source.upper().strip()
    if upper in STATE_MEDIA_SOURCES:
        return SOURCE_FLAG_STATE_MEDIA
    if upper in CAUTION_SOURCES:
        return SOURCE_FLAG_CAUTION
    return SOURCE_FLAG_NONE
