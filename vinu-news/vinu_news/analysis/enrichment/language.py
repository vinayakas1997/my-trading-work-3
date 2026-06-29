"""Language detection from headline Unicode scripts (Fincept Section 6G)."""

KANA_RANGE = (0x3040, 0x30FF)
HANGUL_RANGE = (0xAC00, 0xD7AF)
CJK_RANGE = (0x4E00, 0x9FFF)
CYRILLIC_RANGE = (0x0400, 0x04FF)
ARABIC_RANGE = (0x0600, 0x06FF)
DEVANAGARI_RANGE = (0x0900, 0x097F)

SCRIPT_RANGES = {
    "zh": CJK_RANGE,
    "ru": CYRILLIC_RANGE,
    "ar": ARABIC_RANGE,
    "hi": DEVANAGARI_RANGE,
}

MAJORITY_THRESHOLD = 0.10


def _in_range(code: int, bounds: tuple[int, int]) -> bool:
    return bounds[0] <= code <= bounds[1]


def detect_language(headline: str) -> str:
    """Detect language from headline script blocks."""
    if not headline:
        return "en"

    for char in headline:
        code = ord(char)
        if _in_range(code, KANA_RANGE):
            return "ja"
        if _in_range(code, HANGUL_RANGE):
            return "ko"

    total = len(headline)
    if total == 0:
        return "en"

    counts = {lang: 0 for lang in SCRIPT_RANGES}
    for char in headline:
        code = ord(char)
        for lang, bounds in SCRIPT_RANGES.items():
            if _in_range(code, bounds):
                counts[lang] += 1
                break

    for lang, count in counts.items():
        if count / total > MAJORITY_THRESHOLD:
            return lang

    return "en"
