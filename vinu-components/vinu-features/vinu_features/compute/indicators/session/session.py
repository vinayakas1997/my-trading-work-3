"""Market session classification indicator."""

from __future__ import annotations

from datetime import datetime, timezone
import zoneinfo

KIND = "session"
DESCRIPTION = "Market session classification (asia, london, ny_regular, london_ny_overlap, off_hours)"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("session",)
EXAMPLES = ("session",)
LEGACY_ALIASES = {"session": {}}

FEATURE_NAMES = ("session",)
WARMUP_BARS = 1


def matches(name: str) -> bool:
    return name == "session"


def warmup_for(name: str) -> int:
    return 1


def compute(rows: list[dict], *, name: str) -> dict[str, list[str]]:
    try:
        tz_london = zoneinfo.ZoneInfo("Europe/London")
        tz_eastern = zoneinfo.ZoneInfo("US/Eastern")
    except Exception:
        tz_london = None
        tz_eastern = None

    results: list[str] = []
    for row in rows:
        ts = int(row["ts"])
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        if tz_london is not None and tz_eastern is not None:
            dt_london = dt.astimezone(tz_london)
            dt_eastern = dt.astimezone(tz_eastern)
        else:
            from datetime import timedelta
            dt_london = dt
            dt_eastern = dt.astimezone(timezone(timedelta(hours=-5)))

        # London Time: 08:00 - 16:30 London Time
        lon_time = dt_london.hour + dt_london.minute / 60.0
        is_london = (8.0 <= lon_time < 16.5)

        # NY Regular Time: 09:30 - 16:00 US/Eastern Time
        est_time = dt_eastern.hour + dt_eastern.minute / 60.0
        is_ny_reg = (9.5 <= est_time < 16.0)

        # Asia Hours: UTC 00:00 to 07:00 (approx Tokyo/Sydney active times)
        is_asia = (0.0 <= dt.hour < 7.0)

        if is_london and is_ny_reg:
            results.append("london_ny_overlap")
        elif is_london:
            results.append("london")
        elif is_ny_reg:
            results.append("ny_regular")
        elif is_asia:
            results.append("asia")
        else:
            results.append("off_hours")

    return {name: results}
