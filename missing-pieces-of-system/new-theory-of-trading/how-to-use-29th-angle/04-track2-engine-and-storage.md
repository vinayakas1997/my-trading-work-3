# Track 2: where the engine lives, and the storage schema

Answers three questions asked directly: (1) where does the calculation
code live so live trading can reuse it unchanged, (2) what does the
actual storage schema look like, (3) how are PRE/DURING/POST window
lengths made configurable rather than hardcoded.

## 1. The engine lives in `vinu_tools`, not in `vinu-initial-analysis`

**Decided**: the code that does the actual detection work — walking a
bar series, finding where price crosses the 2×ATR floor, finding each
subsequent checkpoint (2.5×, 3×, ...), computing rate-of-change between
checkpoints, and raising the volume-divergence flag — is a new module
inside `vinu_tools` (e.g. `vinu_tools/compute/move_detection.py`), next
to the existing 52-indicator library, not inside the angle that calls it.

**Why this matters, concretely**: this is the exact same reasoning
documented in `06-mistake-duplicated-indicator-logic.md` for Track 1's
ADX/RSI mistake — hand-rolling detection logic once for the historical
backfill (`vinu-initial-analysis`, running periodically like every other
angle) and again later for the live detector (`vinu-live`, watching bars
arrive in real time) would let the two implementations quietly drift
apart. If they disagree even slightly on where a checkpoint is or how a
crossing is defined, then evidence recorded historically no longer
describes what the live system will actually detect — the whole point of
Track 2 (informing live decisions with historical evidence) breaks
silently. One shared function, called from both places, is the only way
to guarantee they stay identical.

Concretely, the historical angle and the future live detector both call
the same `detect_moves(bars, atr_period=14, floor_multiple=2.0,
checkpoint_step=0.5) -> list[MoveEvent]` function (naming illustrative,
not final) — the angle calls it over a batch of historical bars, the
live detector calls it incrementally as new bars arrive. Neither
reimplements the crossing/checkpoint math itself.

## 2. Storage schema — mirrors `SignalEvidenceStore`'s proven shape

Per Decision 8's own reasoning (right-sized storage per genuinely
different data shape) and the same "one JSON blob per row, not N literal
SQL columns" pattern from Decision 3, this is a **new store**
(`MoveEvidenceStore`, living in `vinu-research` next to
`SignalEvidenceStore` — same service, same reasoning as Decision 8:
that's where the evidence-recording concern already lives), not an
extension of `SignalEvidenceStore` itself. Three tables, not two,
because there's a third repeating sub-structure (checkpoints) that
`SignalEvidenceStore` never had:

```sql
CREATE TABLE move_events (
    move_id                          TEXT PRIMARY KEY,
    symbol                           TEXT NOT NULL,
    direction                        TEXT NOT NULL,   -- 'up' | 'down'
    outcome                          TEXT NOT NULL,   -- 'extended' | 'failed'
    start_time                       TEXT NOT NULL,
    peak_time                        TEXT,             -- NULL if outcome='failed'
    end_time                         TEXT,
    magnitude_pct                    REAL NOT NULL,
    magnitude_bin                    TEXT,
    duration_bin                     TEXT,             -- 'fast' | 'medium' | 'slow'
    duration_candles_pre             INTEGER,
    duration_candles_during          INTEGER,
    duration_candles_post            INTEGER,
    granularity                      TEXT NOT NULL DEFAULT '15min',
    session                          TEXT,
    day_of_week                      TEXT,
    relative_strength_vs_benchmark   REAL,
    retest_occurred                  INTEGER,          -- 0/1
    retest_held                      INTEGER,          -- 0/1, NULL if retest_occurred=0
    retest_candles                   INTEGER,
    policy_version                   TEXT,
    created_at                       TEXT NOT NULL
);
CREATE INDEX idx_move_events_symbol ON move_events(symbol);
CREATE INDEX idx_move_events_outcome ON move_events(outcome);

-- one row per (move, phase) -- mirrors signal_evidence_indicators exactly
CREATE TABLE move_phase_indicators (
    move_id         TEXT NOT NULL REFERENCES move_events(move_id),
    phase           TEXT NOT NULL,    -- 'pre' | 'during' | 'post'
    indicator_name  TEXT NOT NULL,
    indicator_value TEXT NOT NULL,    -- JSON, same as Decision 3's pattern
    PRIMARY KEY (move_id, phase, indicator_name)
);

-- one row per (move, checkpoint) -- the new sub-structure Track 1 never needed
CREATE TABLE move_checkpoints (
    move_id                 TEXT NOT NULL REFERENCES move_events(move_id),
    atr_multiple            REAL NOT NULL,
    checkpoint_time         TEXT NOT NULL,
    candles_since_prev      INTEGER,
    volume_divergence       INTEGER,   -- 0/1
    PRIMARY KEY (move_id, atr_multiple)
);

-- one row per (move, checkpoint, indicator) -- the checkpoint's own indicator snapshot + rate-of-change
CREATE TABLE move_checkpoint_indicators (
    move_id             TEXT NOT NULL,
    atr_multiple        REAL NOT NULL,
    indicator_name      TEXT NOT NULL,
    indicator_value     TEXT NOT NULL,   -- JSON
    rate_of_change      REAL,             -- NULL for the first checkpoint (no previous to diff against)
    PRIMARY KEY (move_id, atr_multiple, indicator_name),
    FOREIGN KEY (move_id, atr_multiple) REFERENCES move_checkpoints(move_id, atr_multiple)
);
```

Why four tables and not one wide table: exactly Decision 3's reasoning —
52 indicators × 3 phases, plus an unbounded number of checkpoints per
move (a move to 7×ATR has more checkpoint rows than one that dies at
2.5×), makes a normalized child-table shape the only one that doesn't
require a schema change every time the indicator set changes or a move
happens to run further than any move seen before.

## 3. PRE/DURING/POST window lengths — config knobs, not hardcoded, matching Track 1's convention

Track 1 already established the pattern (`min_observations=70`,
`forward_horizon_bars=20`, etc., all env-overridable via
`VINU_SIGNAL_EVIDENCE_<SETTING>` — see `01-track1-how-it-works-today.md`).
Track 2 follows the identical convention, `VINU_MOVE_EVIDENCE_<SETTING>`:

| Setting | Proposed default | Meaning |
|---|---|---|
| `pre_window_candles` | 30 | How many candles back the PRE phase's indicator average is computed over |
| `post_window_candles` | 20 | How many candles forward from peak the POST phase covers, capped by wherever the move actually degrades/flattens first |
| `atr_period` | 14 | Matches Track 1's own `ADX_PERIOD`/`RSI_PERIOD` convention |
| `floor_multiple` | 2.0 | Decision 14 — the 2×ATR floor |
| `checkpoint_step` | 0.5 | The gap between checkpoints (2.0, 2.5, 3.0, ...) |
| `min_observations` | 70 | Same meaning as Track 1's own setting |

**On "dynamic" PRE/POST specifically**: a truly dynamic PRE window (e.g.
"scan backward until the price was quiet by some statistical definition,
however many candles that takes") is a real option but a meaningfully
bigger piece of logic than a fixed candle count, and isn't needed to get
started. The recommendation is to **start with the fixed, config-knob
version above** (same posture as every other Track 1 constant — a
reasonable guessed default, overridable, revisited once real data
exists) and treat a genuinely dynamic PRE-window detector as a documented
future upgrade, not a blocker to building the fixed version now.
