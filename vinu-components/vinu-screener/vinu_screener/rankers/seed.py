"""The default starter `RankerConfig` -- closes the "no real recipe
exists" gap: until this module, the only way to create a `RankerConfig`
at all was a manual `PUT /screener/rankers/{id}` call, so a fresh deploy
had a fully working ranking engine and nothing to rank.

`CORE_STARTER_UNIVERSE` (below) is the built-in fallback universe -- a
curated subset (well-known, liquid US large-caps), not the full
~8000-symbol catalog. `RankerRunner` fetches full OHLCV history for
every symbol in a ranker's `universe` on every run with no cheap
pre-filter stage (see `scan/universe.py`'s `CoarseFilter`, which exists
but is only wired into `ScanMonitor`, not the ranker path). Widening
this to the real catalog is a deliberate later step once fetch cost at
that scale is measured, not something to default to silently here.

The universe is deliberately NOT baked permanently into the image: at
seed time, `_load_universe_override()` first checks for a JSON file at
`VINU_SCREENER_SEED_CONFIG` (default `{VINU_SCREENER_DATA_ROOT}/
seed_universe.json`, i.e. the same host-mounted `/data` volume the
ranker DB itself already lives in -- editable in place, no image
rebuild, survives redeploys). Shape: `{"universe": ["AAPL", "MSFT",
...]}`. Missing file, unreadable file, or a missing/empty `universe`
key all fail open to `CORE_STARTER_UNIVERSE` below -- this is read only
once, at seed time (not re-read live by the scan loop), so a later edit
to the file only takes effect on the ranker's *next* seed-eligible
start, same as any other seed-time-only value. A future writer (a
discovery process, an operator script) can grow this file over time
without touching code.

Factor weights are a documented starting point, not a tuned strategy --
same static-until-tuned caveat as every other `FactorSpec` in this
package. `pct_change` is fractional (a 5% move is 0.05) while `rsi` is
0-100, so `rsi`'s weight is scaled down two orders of magnitude to stay
in a comparable range rather than dominating the score.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .config import RankerConfig
from .store import RankerStore
from ..pipeline.hard_filter import HardFilterConfig
from ..pipeline.scorer import FactorSpec

LOG = logging.getLogger(__name__)

CORE_STARTER_RANKER_ID = "core_starter"

CORE_STARTER_UNIVERSE: tuple[str, ...] = (
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "AVGO", "JPM",
    "LLY", "V", "UNH", "XOM", "MA", "HD", "PG", "COST", "JNJ", "ABBV",
    "MRK", "WMT", "BAC", "CVX", "KO", "PEP", "ADBE", "CRM", "NFLX", "AMD",
    "TMO", "LIN", "ACN", "MCD", "ABT", "CSCO", "WFC", "DHR", "TXN", "ORCL",
    "PM", "IBM", "GE", "CAT", "INTU", "VZ", "AMGN", "NOW", "QCOM", "SPGI",
)

CORE_STARTER_FACTORS: tuple[FactorSpec, ...] = (
    FactorSpec(name="momentum_short", indicator="pct_change", weight=5.0, params={"period": 10}),
    FactorSpec(name="momentum_medium", indicator="pct_change", weight=3.0, params={"period": 30}),
    FactorSpec(name="rsi_extreme_penalty", indicator="rsi", weight=-0.01, params={"period": 14}),
)

CORE_STARTER_HARD_FILTER = HardFilterConfig(min_price=5.0, min_dollar_volume=1_000_000.0)


def _seed_config_path() -> Path:
    override = os.environ.get("VINU_SCREENER_SEED_CONFIG")
    if override:
        return Path(override)
    data_root = Path(os.environ.get("VINU_SCREENER_DATA_ROOT", str(Path.home() / ".vinu")))
    return data_root / "seed_universe.json"


def _load_universe_override() -> tuple[str, ...] | None:
    path = _seed_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        universe = data.get("universe")
        if not universe:
            return None
        return tuple(str(s).strip().upper() for s in universe if str(s).strip())
    except (json.JSONDecodeError, OSError, AttributeError) as exc:
        LOG.warning("failed to read seed universe override at %s, falling back to built-in default: %s", path, exc)
        return None


def build_core_starter_config() -> RankerConfig:
    universe = _load_universe_override() or CORE_STARTER_UNIVERSE
    return RankerConfig(
        ranker_id=CORE_STARTER_RANKER_ID,
        universe=universe,
        factors=CORE_STARTER_FACTORS,
        top_n=20,
        hard_filter=CORE_STARTER_HARD_FILTER,
    )


def seed_default_ranker(store: RankerStore) -> bool:
    """Idempotent: only creates `core_starter` if it doesn't already
    exist, so this is safe to call on every container start without
    ever clobbering an operator's own edits to the same ranker_id.
    Returns True if a ranker was created, False if one already existed."""
    if store.get(CORE_STARTER_RANKER_ID) is not None:
        return False
    store.upsert_ranker(build_core_starter_config())
    return True
