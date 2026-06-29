"""Lead article scoring weights."""

PRIORITY_SCORE = {
    "FLASH": 4,
    "URGENT": 3,
    "BREAKING": 2,
    "ROUTINE": 1,
}

IMPACT_SCORE = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# Lower source_flag is better; invert for scoring
SOURCE_FLAG_SCORE = {0: 3, 1: 2, 2: 1}
