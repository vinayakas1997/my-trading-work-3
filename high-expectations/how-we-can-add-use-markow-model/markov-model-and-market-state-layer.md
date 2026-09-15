# Adding a present-market-state / Markov layer to the trading system

Written 2026-09-15, grounded in a direct read of the real code (file:line
citations below, all verified this session against
`/home/somic_cps/Vina/my-trading-work-3/vinu-components`), matching the
sibling `missing-pieces-of-system/` docs' style: what exists, what's
genuinely missing, and a staged, bounded plan — not a rewrite.

---

## 0. The short answer to "can I say that?"

**Yes.** The system has a strong *pre-trade* half and a real *in-trade*
half, but no *present-market-state* layer. Concretely:

- Pre-trade preparation is alive: Planner triage → Researcher sweep →
  `author_trade_plan` → `risk_gatekeeper` → `capital_allocator` →
  `PaperRehearsal` + fractional-Kelly sizing + freeze manifest.
- In-trade management is alive: `_evaluate_open_position()` handles
  contingency rules, invalidation, trailing-stop ratchet, bracket-partial,
  and runtime correlation trim every 5 min.
- **But the decision that moves money is nearly regime-blind and has no
  per-candle present-state model.** `regime_analysis` even *already
  computes* a 4-state regime + a full empirical transition matrix — and
  **nothing in `vinu-live` reads it**.
- The phrase "a Markov model" is the right intuition, but there are two
  different things you could mean, and the system has *half* of one:
  1. **An empirical Markov chain over regimes** — already computed as a
     transition matrix (`regime_analysis`), never consumed. Cheapest win.
  2. **A hidden-state model (HMM / Markov-switching)** — not present
     anywhere. This is the genuinely new model, and it should come second,
     behind a flag, once the cheap version has earned its place.

So the accurate statement is: *"the present state of the market is not
represented as a first-class input to either the forecast or the live
position evaluation; the raw ingredients for a discrete-state Markov view
exist but are unwired."* That is what this document plans to fix.

---

## 1. What the system already has (the two working halves)

### 1.1 Pre-trade preparation — complete

| Stage | Where | Cadence | What it does |
|---|---|---|---|
| Planner triage | `vinu-agent/vinu_agent/agent/scheduler_workers.py`, `planner_triage_hook.py` | 30 min | Reads stored summary + all non-terminal statuses, fit tier/priority, consults `HypothesisRegistry`, K-cap |
| Thesis Intake | vinu-agent teams | manual | Human theory checked against evidence, no code |
| Researcher/Executor | `vinu-agent` sweep tools + `vinu-research/trade_plan_authoring.py` | on demand | Sweep/backtest evidence, then `author_trade_plan` |
| Forecast | `trade_plan_authoring.py:787` → `forecast_skill.py:175 generate_forecast` | per plan | One LLM call → direction/confidence/magnitude/horizon |
| Risk band + rules | `_build_risk_band`, `_build_contingency_rules:468`, `_build_invalidation_conditions:510` | per plan | Frozen metric/operator/threshold triples |
| Trade Score gate | `gates/trade_score_gate.py:188 check_trade_score_gate` | per plan | risk/EV/regime-fit sub-scores, tier multiplier |
| Freeze | `freeze_trade_plan:903` | per plan | Immutable CREATED artifact; fails closed with no invalidation rules |
| Isolation fit | `risk_gatekeeper` | 15 min | `BENCHING → PEND`, portfolio-fit only, never re-litigates strategy |
| Funding | `capital_allocator` | 15 min | Whole PEND batch, correlation-aware, `PEND → ACTIVE` only if Kill Switch clear |
| Paper rehearsal | `vinu-research/loop.py::_run_paper_rehearsal` | per plan | 7-day bar-by-bar, same simulator + T+1 + Almgren-Chriss; blocks if Sharpe<0 or >50% degradation |
| Sizing | `vinu-simulator/.../engine/sizing.py`, `vinu_infra/risk_math.py` | per plan | Fractional Kelly (0.25), vol-target, 2–3× ATR stops |
| Lineage freeze | `vinu-infra/vinu_infra/freeze.py` | on demand | Hashes `VINU_*` env + data-root files, contamination check |

This half is real. The only structural weakness worth naming is the
already-known one: `author_trade_plan`'s forecast prompt sees only
**2 of the 28 angles** as structured data plus a 2000-char collapsed
summary — documented in `project-understanding/01-new-full-explanation-v2.md`
("two separate 28-angle stories").

### 1.2 In-trade management — complete

`vinu-live/vinu_live/trade_plan/orchestrator.py`, trade-plan-worker every
`trade_plan_worker_interval_sec=300` (`config.py:48`):

- **Entry gate chain** (`_maybe_enter:1116`), each an observable
  `entry_blocked_by_*`: entry_decision WAIT → emergency halt → broker
  outage → signal conflict → stale signal (`SIGNAL_MAX_AGE_HOURS=72`) →
  data freshness (`PRICE_MAX_AGE_HOURS=96`) → zero size → CVaR tail gate
  (`CVAR_THRESHOLD=0.03`) → event blackout → spread/liquidity
  (`MAX_SPREAD_BPS=25`) → borrow → cooldown → turbulence
  (`TURBULENCE_VOL=0.05`). Then forecast-confidence scaling
  (`FORECAST_SCALING_FLOOR=0.5`) and vol-target scaling
  (`VOL_TARGET=0.15`).
- **Open-position chain** (`_evaluate_open_position:1616`): time-stop
  (`MAX_HOLD_DAYS=30`) → optional thesis re-check → invalidation
  (`find_triggered_rules`, `condition_evaluator.py:38`) → contingency
  (tighten/reduce) → rebalance request (advisory) → trailing ratchet
  (`trailing_stop_for:664`, `TRAILING_ATR_MULT=2.0`, bookkeeping only) →
  bracket-partial at 1R+ (`:1760`, 25%→75% scaled).
- **Runtime correlation trim** (`_check_runtime_correlation:2075`):
  DCC/shrinkage covariance, `RUNTIME_CORR_THRESHOLD=0.85`, 25% reduce,
  3600s cooldown.
- **OOD detector** (`_check_ood`), dormant by default
  (`VINU_LIVE_OOD_DETECTOR=off`): crisis correlation 0.95, vol explosion
  0.08, gap move 0.10.
- **Breaker / Kill Switch**: real filesystem `/tmp/vinu-trading-halt`,
  checked in `OrderGuard.check()`; reduce-only exempted only under
  `VINU_LIVE_HALT_POLICY=entries_only` (default).

This half is proven by the engineered scenarios in
`the-resaoning-ineffciency/scenarios-test/01-07`.

---

## 2. The missing middle: present market state

Every gap below was confirmed by reading the code, not inferred.

| # | Gap | Evidence |
|---|---|---|
| 1 | **No live regime consumer.** `regime_analysis` computes `current_regime` (`compute.py:131`) and a full transition matrix with `transition_prob` + `n_from_regime` (`compute.py:174-198`), but `vinu-live` never imports or fetches it. | `grep -rn "regime" vinu-live/` yields only a comment and the `regime_change_error` label in `loss_classifier.py` |
| 2 | **Regime is size-only, never direction.** `fetch_current_regime:193` and `_regime_size_multiplier:206` run **after** `generate_forecast:787`, tilt `max_position_size_pct` by `±regime_size_tilt_bound` (default 0.3, `config.py:243`). `current_regime_alignment` is one confluence vote (`fetch_angle_signals:233`). It can never flip `long/short/neutral`. | `trade_plan_authoring.py:874-882` |
| 3 | **Forecast prompt is present-state blind.** `_build_forecast_prompt:224` emits exactly: Ticker Summary, optional Angle Digest, Personality Features (only `shock_personality`/`shock_clustering`, `:178`), Risk State (recomputed GARCH/VaR/Kelly, `:71`). System prompt says "size only from the Risk State + Personality numbers." No regime, no GARCH angle, no Kalman, no candle. | `forecast_skill.py:162-254` |
| 4 | **`MarketState` exists but never reaches the prompt.** `MarketState` (`market_state.py:25`) aggregates angles/features/liquidity/news/options/risk/validation; `trade_plan_tool.py:178` builds it, but `:544-557` forwards only `summary_context + extra_checklist`. Structured present-state is dropped. | `trade_plan_tool.py` |
| 5 | **No candle/OHLC handling in live.** `_fetch_prices:2454` reads only `bars[-1].close`; `_fetch_recent_prices:2522` reads only `close`; `volume` is used only for ADV participation (`_participation_pct:2494`). `open/high/low` and any candle-pattern state are never read in `vinu-live`. | `orchestrator.py` |
| 6 | **Daily granularity for live decisions.** `_fetch_prices` is `interval="1d", days=5`; `_fetch_recent_prices` default `1d, 90d`. `compute_live_metrics` (`live_metrics.py:28`) takes only `recent_returns`/`previous_close` — no forming-bar state. (Intraday plans get `15m` via `_interval_for_plan:77`, but only as a **closed-bar close series**.) | `orchestrator.py:2454,2522`; `live_metrics.py` |
| 7 | **`invalidation action="trim"` is silently a full exit.** `_build_invalidation_conditions:510` emits a `p_failure>=0.3 → action:trim, reduce_by_pct:0.5` rule, but `_apply_invalidation:1899` ignores `action` and always submits a **full** `reduce_only` close. (contingency `reduce_position` handles partials correctly at `:1960`.) | `trade_plan_authoring.py:539-548`; `orchestrator.py:1899` |
| 8 | **No Markov/HMM anywhere.** No `hmmlearn`, no Markov-switching, no state-persistence probability. `regime_analysis` gives an *empirical* transition matrix; `tips_regime_aware_transformer` and `kalman_filters` are present-state-ish angles but not consumed by any decision path. | angle catalogue + greps |

**Net:** the pipeline analyzes the market richly and often, then throws
almost all of the *structured* present-state away before the money
decision — and never represents "what state are we in right now, and how
likely is it to change on the next candle?" at all.

---

## 3. What "a Markov model" means here

Two distinct models, in increasing order of cost. The plan uses the first
immediately and adds the second behind a flag.

### 3.1 Empirical Markov chain over regimes (exists, unwired)

`regime_analysis/compute.py` already produces:

- `current_regime ∈ {bull, bear, high_vol, sideways}`
  (`classify_regime:40`, point-in-time safe: `ret_20d` vs `±1%`,
  `vol_trailing_z > 1.0` against a 120-bar trailing baseline — leak-fixed
  per the module docstring).
- `metric="transition"` rows: `regime_from`, `regime_to`, `count`,
  `n_from_regime`, `transition_prob` (`compute.py:181-198`). The
  `(bull→high_vol)` probability is literally the one-step Markov
  transition probability, already calculated, honestly paired with its
  sample size.

This is a first-order Markov chain, empirically estimated. It needs a
consumer, not a model.

### 3.2 Hidden Markov / Markov-switching model (new)

The regime classifier is rule-based on observed quantities. An HMM infers
a **latent** state from an observation sequence (returns, realized vol,
range, volume) and gives:

- filtered state probability `P(S_t = s | x_{1:t})` — the present state,
  with uncertainty rather than a single label;
- transition matrix `P(S_{t+1} | S_t)` — persistence and flare risk;
- expected duration in the current state `1/(1 - p_self)`.

This matters because the honest answer to "how confident am I in the
present state?" is not a hard label — it is a probability distribution.
That distribution is exactly the "confidence" the user is reaching for.

---

## 4. Design: one contract, three consumers

### 4.1 `MarketStateSnapshot` (new, shared)

Define once (suggested: `vinu-infra/vinu_infra/market_state.py` so
`vinu-live` and `vinu-research` can both import it without a cross-service
dependency):

```python
@dataclass(frozen=True)
class MarketStateSnapshot:
    symbol: str
    as_of: str                       # bar_ts / timestamp of the state
    interval: str                    # "15m" | "1h" | "1d"

    # --- discrete state (rule chain OR HMM, same contract) ---
    state: str                       # bull|bear|high_vol|sideways
    state_prob: float                # confidence in `state` (0-1)
    state_probs: dict[str, float]    # full distribution (HMM mode)
    expected_duration_bars: float    # 1/(1-p_self), from transition matrix
    next_state_probs: dict[str, float]   # P(S_{t+1}|S_t=state)
    vol_z: float                     # vol_trailing_z
    trend_strength: float            # ret_20d (or |ret_20d|/vol)
    model: str                       # "rule" | "hmm" | "hybrid"

    # --- candle / forming-bar state ---
    bar_complete: bool
    open: float; high: float; low: float; close: float
    range_pct: float
    body_pct: float                  # |close-open| / (high-low)
    candle_state: str                # trend_bar|inside|outside|lower_wick|upper_wick|doji
    gap_vs_prev_close_pct: float

    # --- output ---
    confidence_delta: float          # in [-1, +1], the single number acted on
    reasons: list[str]
```

Discipline to preserve: every probability must be paired with its sample
size (`n_from_regime` already does this — `compute.py:191`); the doc's
project-wide "never present a rate without n" rule applies.

### 4.2 `confidence_delta` semantics

One bounded number, consistent with the codebase's existing bounded-tilt
philosophy (`±0.3` regime size tilt, `±20-30%` screener tilt,
`RUNTIME_CORR_REDUCE_PCT=0.25`). Advisory first; never a hard exit in v1.

Suggested mapping (all thresholds env-tunable, defaults conservative):

| Condition | `confidence_delta` | Action |
|---|---|---|
| State stable (`state_prob ≥ 0.7`, `p_self ≥ 0.8`), aligned with position | `+0.2 … +0.3` | hold / optionally loosen stop by ≤10% (opt-in only) |
| State stable, **misaligned** (`bear` on long) | `-0.3 … -0.5` | tighten stop 30%, no new adds |
| `P(→high_vol)` on next bar `≥ 0.35` | `-0.3` | tighten stop 30% |
| `P(→high_vol) ≥ 0.5` **and** forming bar adverse | `-0.5` | reduce 25–50% |
| Candle breaks prior bar range against position while in `high_vol` | `-0.5` | reduce 25% (not full exit) |
| `state_prob < 0.4` (model uncertain) | `0.0` | no change — uncertainty is not a signal |
| `doji`/`inside` in `sideways` | `0.0` | no change — noise, explicitly no exit |

The key rule: **uncertainty defaults to no action**, and **v1 never
full-exits on state alone** — invalidation/contingency rules remain the
only full-exit authority. This mirrors how `_regime_size_multiplier`
refuses to act on `sideways`.

### 4.3 Consumers

1. **Forecast prompt** — add a `=== Present Market State ===` block to
   `_build_forecast_prompt:224`, built from the same snapshot. This closes
   gap #3/#4 and gives the LLM regime/vol/candle context as *structured*
   input, not prose. Keep "size only from Risk State + Personality numbers"
   or deliberately revise it to include state.
2. **Entry gate** — a `state`-derived size tilt plus one honest gate:
   block new longs when `state == high_vol` **and** `P(→crisis)` elevated
   (opt-in; default tilt-only). Insert in `_maybe_enter` after
   data-freshness (`:1195`), before CVaR.
3. **Open-position** — feed `confidence_delta` into
   `_evaluate_open_position:1616` (after invalidation/contingency, before
   trailing ratchet) to modulate tighten/reduce. Log every adjustment to
   `TickerLedger` and the calibration log
   (`vinu-infra/vinu_infra/calibration_log.py`).

---

## 5. Per-candle handling (intraday)

The user's specific ask: "when a candlestick comes, how to handle it so
that confidence is there."

Design: a small, deterministic `on_candle(snapshot, position, plan)` that
runs at the top of `_evaluate_open_position` and inside `_maybe_enter`,
using **intraday bars** while keeping daily bars for planning.

- **Fetch**: `vinu-stock-price`'s `/stock/candles/{symbol}` already accepts
  arbitrary `interval` (default `1m`, `routes_read.py:77-81`). Add a
  `_fetch_candles(symbol, interval="15m", days=2)` that parses full OHLCV,
  distinct from `_fetch_prices` (spot close) and `_fetch_recent_prices`
  (close series).
- **Forming vs closed bar**: `bar_complete=False` for the last bar when its
  `bar_ts` is inside the current interval window. Forming-bar state drives
  *warnings and stop-tightening only*; a full action waits for
  `bar_complete=True`. This prevents wick-driven false trims.
- **Minimal candle state machine** (no candlestick-pattern library needed):
  `doji`, `inside`, `outside`, `trend_bar`, `lower_wick`, `upper_wick`,
  derived from `open/high/low/close` and the prior bar's range. This is
  deliberately tiny — the value is in *state-transition* handling, not in
  pattern recognition.
- **Handler composition**: `candle_state` only ever *scales*
  `confidence_delta`; it never edits `invalidation_conditions` or bypasses
  the breaker. Same posture as `trailing_stop_for` and
  `_check_runtime_correlation` — best-effort, never blocks `hold`.

Suggested cadence note: keep the worker at 300s. A 15m bar closes roughly
every third cycle; `bar_complete` prevents acting on partial bars and
naturally rate-limits. Do **not** move to a tick/websocket rewrite in this
phase (that's a later, separate decision).

---

## 6. Implementation plan

### Phase 0 — contract only (no behavior change)

1. Add `MarketStateSnapshot` (§4.1) in `vinu-infra/vinu_infra/market_state.py`.
2. Add `compute_confidence_delta(snapshot, position, direction)` as a pure,
   unit-tested function with the §4.2 table. No I/O.
3. Define `VINU_LIVE_MARKET_STATE_MODE=off|log|rule|hmm|hybrid` default
   `off`; in `log` mode compute + emit to `TickerLedger` and the
   calibration log but change nothing. This is how every optional feature
   in this repo rolls out (`VINU_LIVE_OOD_DETECTOR`, `regime_analogue_enabled`,
   `options_iv_enabled`, `debate_signal_enabled`).

### Phase 1 — reuse the existing regime chain (no new model)

4. **`vinu-live/vinu_live/trade_plan/regime_fetcher.py`** (new):
   - primary: `GET {initial_analysis_api_url}/analysis/angle/regime_analysis/{symbol}`,
     select `metric == "current_regime"` and all `metric == "transition"` rows;
   - fallback: local `classify_regime(ret_20d, vol_z)` reusing the exact
     point-in-time formula from `compute.py:40-79` on
     `_fetch_recent_prices()` (keeps working when the analysis service is
     down; same fail-open posture as everything else).
   - cache per cycle; never per-position.
5. **`_fetch_candles()`** (§5) + candle-state derivation; wire into
   `_evaluate_open_position` and `_maybe_enter`.
6. **`vinu-research`**: build the snapshot server-side in
   `author_trade_plan` (it already fetches `current_regime` at `:874`) and
   pass it into `generate_forecast`. Add the `=== Present Market State ===`
   block in `_build_forecast_prompt:224`. Optionally widen `angle_digest`
   by adding a `regime_analysis` compactor to `angle_context.py`
   (alongside `compact_trend_lifecycle:61` etc.) so the full transition
   matrix reaches the prompt without prose.
7. **Fix gap #7** while in this area: make `_apply_invalidation:1899`
   honor `action` (`trim` → `reduce_by_pct`, `exit` → close). Small,
   independently testable, real behavior bug.

### Phase 2 — the actual Markov/HMM model (behind flag)

8. **New angle** `vinu-initial-analysis/.../angles/market_state_hmm/`
   (or a model in `vinu-tools`, persisted like Chronos/Kronos):
   - observations: returns, realized vol, high-low range, volume z;
   - 3–4 latent states, Gaussian emissions or `hmmlearn.GaussianHMM`;
   - **walk-forward fit only** — same no-lookahead discipline as
     `regime_analysis`'s leak fix and `PaperRehearsal`. No full-sample fit.
   - outputs: filtered `state_probs`, transition matrix, `expected_duration_bars`,
     `next_state_probs`.
9. Register in `vinu-infra/models.py` **only if** it needs a downloaded
   checkpoint; a fitted HMM is trained online/offline, not
   `snapshot_download()`-ed, so it likely persists to `data/` instead.
   Keep `make models-list` semantics clean.
10. In `vinu-live`, `VINU_LIVE_MARKET_STATE_MODE=hmm|hybrid` selects the
    HMM snapshot; `rule` remains the default until A/B evidence exists.
    `hybrid` = rule chain for the state label, HMM for the probabilities.
11. **Regime-conditioned evaluation**: extend `PaperRehearsal` /
    `backtesting_44_metrics` to report per-regime Sharpe (pooled Sharpe
    hides exactly the regime-dependence this whole layer is about).

### Phase 3 — prove it (follow the repo's own pattern)

12. New scenarios under `the-resaoning-ineffciency/scenarios-test/` (or the
    equivalent for this layer), each with a known-correct answer:
    - bull→high_vol flip mid-position → assert tighten, not full exit;
    - gap-down forming bar → assert `bar_complete=False` defers action;
    - doji inside range in `sideways` → assert **no** exit (noise);
    - `P(→high_vol)≥0.5` + adverse outside bar → assert 25% reduce only;
    - regime service down → assert fail-open, hold, no crash.
13. LLM-side: a `llm-scenarios-test/` case where the forecast prompt
    contains a mean-reverting regime and the plan must not blindly trend-follow.
14. Calibration: log every `confidence_delta` + threshold to
    `calibration_log` gated on a real broker connection (existing pattern),
    then review before promoting `mode` from `log` to `rule`.

---

## 7. Wiring map

```mermaid
flowchart LR
    subgraph SRC["Sources (already exist)"]
        RA["regime_analysis angle<br/>current_regime + transition matrix"]
        GAR["garch angle<br/>next_period_volatility"]
        KAL["kalman_filters angle<br/>filtered state"]
        OOD["vinu-live OOD detector<br/>crisis corr / vol / gap"]
    end

    subgraph NEW["New"}
        SNAP["MarketStateSnapshot<br/>(vinu-infra)"]
        HMM["market_state_hmm<br/>Phase 2, flag-gated"]
        CD["compute_confidence_delta<br/>pure fn"]
        CAND["candle state machine<br/>15m OHLC + bar_complete"]
    end

    RA --> SNAP
    GAR --> SNAP
    KAL --> SNAP
    HMM -.->|mode=hmm/hybrid| SNAP
    CAND --> SNAP
    OOD -.-> SNAP
    SNAP --> CD

    CD -->|forecast prompt block| F["forecast_skill._build_forecast_prompt"]
    CD -->|size tilt + optional gate| E["_maybe_enter (after freshness)"]
    CD -->|tighten / reduce only| O["_evaluate_open_position"]
    CD -->|log| TL[("TickerLedger")]
    CD -->|log| CAL[("calibration_log")]
```

---

## 8. Reuse inventory (build on, don't reinvent)

| Need | Already exists | Reuse how |
|---|---|---|
| Regime state | `regime_analysis` | read `current_regime` row |
| Transition probs | `regime_analysis` `metric="transition"` | read directly, keep `n_from_regime` |
| Present-state estimator | `kalman_filters`, `tips_regime_aware_transformer` | add compactors to `angle_context.py` |
| Vol forecast | `garch` angle (currently recomputed in `fetch_risk_state:71`) | read the stored row, stop duplicating |
| Outlier detections | `_check_ood` | feed as snapshot flags instead of a separate silent path |
| Bounded tilt pattern | `_regime_size_multiplier:206`, `vinu-portfolio` `_regime_alignment_multiplier` | copy the shape |
| Point-in-time discipline | `regime_analysis` leak fix | HMM must walk-forward |
| Optional-feature rollout | `OOD_DETECTOR`, `regime_analogue_enabled`, `options_iv_enabled`, `debate_signal_enabled` | same `off/log/on` pattern |
| Observation record | `vinu_infra/calibration_log.py` | log deltas + thresholds |
| Lineage | `vinu_infra/freeze.py` | new `VINU_*` knobs auto-hashed |
| Proof harness | `scenarios-test/01-07`, `04-situation-test/` | add engineered regime scenarios |
| Intraday data | `/stock/candles/{symbol}?interval=15m` | already supports arbitrary intervals |

---

## 9. Risks and mitigations

| Risk | Why it's real here | Mitigation |
|---|---|---|
| **Stale/partial bar drives false trims** | 5-min polling vs 15m bar; forming bar has a wick | `bar_complete` gate; forming bar only tightens, never reduces |
| **Over-trading on regime noise** | `sideways` and low `state_prob` are common | uncertainty → `delta=0`; min persistence; cooldown reusing `RUNTIME_CORR_COOLDOWN_SEC=3600` pattern |
| **Look-ahead creep** | HMM is easy to fit on full history by accident | walk-forward fit; tests that assert train window ends before decision bar |
| **Regime/label thrash between cycles** | rule threshold + rolling z can flip near boundaries | add hysteresis (require 2 consecutive bars) or use HMM `state_prob` smoothing |
| **Double-counting vol/high_vol** | sizing multiplier, confluence vote, `regime_analysis`, GARCH all already touch vol | one snapshot feeds all; remove duplicated GARCH recompute in `fetch_risk_state` |
| **Cost / latency** | extra intraday fetch per symbol per cycle | per-cycle cache, batch endpoint `/candles/batch`, fetch only open positions + entry candidates |
| **Fail-closed mistakes** | "confidence" pressure to make it a gate | v1 is advisory + logging only; never full-exit on state alone; invalidation remains sole full-exit authority |
| **Silent data fallback** | the repo has a documented pattern of mechanisms never fed real data (see screener doc #5) | assert `snapshot.model != "unavailable"` before acting; log source; `mode=log` first |

---

## 10. Suggested env knobs

| Var | Default | Meaning |
|---|---|---|
| `VINU_LIVE_MARKET_STATE_MODE` | `off` | `off` / `log` / `rule` / `hmm` / `hybrid` |
| `VINU_LIVE_MARKET_STATE_INTERVAL` | `15m` | candle interval for live state |
| `VINU_LIVE_MARKET_STATE_MIN_PERSIST` | `0.7` | min `state_prob` to act |
| `VINU_LIVE_MARKET_STATE_SELF_TRANS` | `0.8` | min `p_self` for a "stable" state |
| `VINU_LIVE_MARKET_STATE_FLARE_THRESHOLD` | `0.35` | `P(→high_vol)` that triggers tighten |
| `VINU_LIVE_MARKET_STATE_REDUCE_THRESHOLD` | `0.5` | `P(→high_vol)` that triggers reduce |
| `VINU_LIVE_MARKET_STATE_REDUCE_PCT` | `0.25` | reduce fraction |
| `VINU_LIVE_MARKET_STATE_COOLDOWN_SEC` | `3600` | per-symbol action cooldown |
| `VINU_RESEARCH_REGIME_DIGEST_ENABLED` | `false` | add regime/transition digest to forecast prompt |

All of these are hashed by `freeze.py` automatically, so lineage stays intact.

---

## 11. Honest status and open decisions

**Uncertain:**
- Whether the rule chain or the HMM is the better default — genuinely an
  empirical question, which is why `mode=log` exists first and
  per-regime backtests (Phase 2.11) gate the promotion.
- Whether the forecast prompt should be allowed to use state for
  *direction* or only for *size/confidence* — the current system prompt
  deliberately withholds it. Recommend: first pass exposes state as
  context + confidence, and only a later, A/B-tested change allows it to
  influence direction.
- Whether an HMM belongs as a new angle (runs hourly with the other 28,
  stored in `vinu-initial-analysis`) or as a `vinu-tools` model used by
  `vinu-live` directly. Angle form is more consistent with the repo; model
  form is lower-latency for live. Lean angle-first, with `regime_fetcher`
  reading the stored rows.

**Not in scope for this doc (deliberately):**
- Fixing the broader 28-vs-2-angle disconnect (documented separately in
  `project-understanding/01-new-full-explanation-v2.md`). This layer fixes
  it *for market state specifically*; the full fix is its own project.
- Any tick/websocket event-driven rewrite. 15m polling with `bar_complete`
  is the bounded step.
- Live money. Everything above is provable offline first.

**One-paragraph summary:** the system already contains the raw material of
a Markov view of the market (`regime_analysis`'s state + transition
matrix, GARCH, Kalman, an OOD detector) but represents none of it as a
first-class present-state input to the forecast or to live position
management, and has no per-candle state handling. The smallest correct
move is a shared `MarketStateSnapshot` + a pure `confidence_delta`, wired
first in `log` mode, reusing the existing regime chain and 15m candle
endpoint; the HMM is a genuine but later addition, flag-gated, walk-forward
fitted, and only promoted after regime-conditioned backtests and engineered
scenarios prove it.
