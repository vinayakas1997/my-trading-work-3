# AAPL — worked comprehension book (example)

**All data below is FABRICATED — invented for this worked example, never
sampled from any real run. Never treat any number here as a real AAPL
signal.** Purpose: make the 3-chapter book structure concrete enough to
actually test, and double as the template for what `TickerSummaryStore`'s
real stored content should eventually look like.

Covers 14 of the 28 real angles (2 per cluster, from
`00-explanation.md` section 3), each at two real timeframes (`1D` and
`1H`) — enough to demonstrate every real pattern this structure needs to
handle: genuine cross-timeframe divergence, corroborating divergence
across independent clusters, and cases where a second timeframe adds
nothing. The remaining 14 angles in each cluster would follow the same
shape, just not duplicated here.

---

## Chapter 1 — Index (raw assembly, no interpretation)

Every angle's latest result, per timeframe, gathered into one place.
This is pure assembly — the layer that doesn't exist anywhere in the
real system today (nothing currently fetches more than `1D`, and
nothing assembles more than one angle's result at a time).

### Cluster A — Classical statistical forecasts

**arima**
| Timeframe | forecast_price | order | aic |
|---|---|---|---|
| 1D | 189.20 | [2,1,1] | 842.1 |
| 1H | 186.10 | [1,1,1] | 210.4 |

**kalman_filters**
| Timeframe | filtered_level | filtered_trend |
|---|---|---|
| 1D | 187.40 | +0.12 |
| 1H | 186.05 | +0.02 |

### Cluster B — Deep-learning / foundation-model forecasts

**patchtst**
| Timeframe | direction | confidence |
|---|---|---|
| 1D | up | 0.61 |
| 1H | flat | 0.30 |

**lpatchtst**
| Timeframe | direction | confidence |
|---|---|---|
| 1D | up | 0.66 |
| 1H | up | 0.35 |

**timesfm**
| Timeframe | point_forecast | model_backend |
|---|---|---|
| 1D | 189.0 | pretrained |
| 1H | 186.0 | pretrained |

### Cluster C — Volatility & drawdown risk

**garch**
| Timeframe | forecast_volatility | persistence |
|---|---|---|
| 1D | 0.021 | 0.95 |
| 1H | 0.026 | 0.93 |

**drawdown_deep_dive**
| Timeframe | current_drawdown_pct | max_drawdown_pct |
|---|---|---|
| 1D | -0.03 | -0.18 |
| 1H | -0.031 | -0.18 |

### Cluster D — Regime & trend structure

**regime_analysis**
| Timeframe | regime | bull_prob | sideways_prob |
|---|---|---|---|
| 1D | bull | 0.58 | 0.19 |
| 1H | sideways | 0.31 | 0.44 |

**trend_lifecycle**
| Timeframe | stage | reversal_signal | knn_similarity_score |
|---|---|---|---|
| 1D | uptrend | false | 0.77 |
| 1H | uptrend | false | 0.52 |

### Cluster E — Shock / personality behavior

**shock_personality**
| Timeframe | gap_fill_rate.mean | vol_persistence |
|---|---|---|
| 1D | 0.60 | 0.88 |
| 1H | 0.60 | 0.93 |

**shock_clustering**
| Timeframe | cluster_members | co_shock_rate |
|---|---|---|
| 1D | [MSFT, GOOGL] | 0.35 |
| 1H | [MSFT, GOOGL] | 0.35 |

### Cluster F — Cross-asset & causality

**peer_relative_strength**
| Timeframe | peer | relative_return_20d |
|---|---|---|
| 1D | MSFT | +0.023 |
| 1H | MSFT | +0.021 |

**news_price_causality**
| Timeframe | granger_p_value | pearson_correlation |
|---|---|---|
| 1D | 0.04 | 0.38 |
| 1H | 0.04 | 0.38 |

### Cluster G — Validation & attribution

**backtesting_44_metrics**
| Timeframe | sharpe | win_rate |
|---|---|---|
| 1D | 1.15 | 0.54 |
| 1H | 1.15 | 0.54 |

**pnl_attribution**
| Timeframe | win_rate | trade_count |
|---|---|---|
| 1D | 0.58 | 19 |
| 1H | 0.58 | 19 |

---

## Chapter 2 — Comprehension (per-angle takeaway, then cluster synthesis)

Reads Chapter 1 only — this is where the glossary (`angle-reference/`)
and the clustering scheme actually earn their keep.

**Cluster A synthesis**: Both classical models agree directionally at
1D (positive trend/forecast) but flatten sharply at 1H — `arima`'s 1H
order even simplifies from (2,1,1) to (1,1,1), consistent with less
structure to fit on a shorter window. Reads as "real daily trend, no
special short-term edge," not a contradiction.

**Cluster B synthesis (consensus-rate style, per `01-plan.md` step 3)**:
At 1D, all 3 sampled models lean up (3/3, moderate confidence
0.61-0.66) — a real, if not overwhelming, consensus. At 1H, that
consensus **breaks down**: only `lpatchtst` still calls up (confidence
drops to 0.35), the other two flip to flat. This is the sharpest signal
in the whole book: the daily uptrend read is real, but the shorter-term
picture shows it stalling, not accelerating.

**Cluster C synthesis**: Volatility ticks up slightly at 1H (0.021 →
0.026) but not dramatically; drawdown is essentially flat across both
timeframes. Reads as mild, not alarming — consistent with a pause
rather than a real risk event.

**Cluster D synthesis**: `regime_analysis` **flips from bull (1D) to
sideways (1H)** — bull probability drops from 0.58 to 0.31, sideways
rises to become the leading probability. `trend_lifecycle` still calls
the daily uptrend intact (no reversal signal either timeframe), but its
own pattern-match confidence weakens at 1H (0.77 → 0.52). Independently
corroborates Cluster B's divergence — two unrelated methods (a
consensus-of-forecasts cluster and a regime classifier) landing on the
same "short-term pause" story.

**Cluster E synthesis**: `shock_personality`'s `vol_persistence` ticks
up at 1H (0.88 → 0.93) — mildly consistent with Cluster C's own
volatility uptick. `shock_clustering`'s cluster membership and co-shock
rate are **identical** at both timeframes — this is a real, structural
statistic (which symbols this one tends to shock alongside), not
something that should be expected to change hour to hour.

**Cluster F synthesis**: `peer_relative_strength` (a 20-day rolling
stat) is nearly identical at both timeframes, as expected — an hourly
read of a 20-day window isn't meaningfully different information.
`news_price_causality`'s Granger test result is **identical** at both
timeframes (same p-value, same correlation) — this angle measures
whether news events precede price moves over the requested window;
re-running it hourly on the same underlying window doesn't produce new
information.

**Cluster G synthesis**: Both validation angles are byte-for-byte
identical across timeframes — `backtesting_44_metrics` and
`pnl_attribution` are backward-looking track-record statistics, not
readings of current market state, so they aren't expected to vary by
the timeframe of the *request* at all.

---

## Chapter 3 — Cross-analysis (is the second timeframe earning its cost)

Reads Chapter 2 only — this is `02-time-format-richness.md`'s question,
answered concretely for this one (fabricated) cycle.

**Real signal found (worth the extra fetch)**:
- **Cluster B**: daily consensus (3/3 up) materially weakens at 1H
  (1/3 up) — a genuine divergence, not noise.
- **Cluster D**: `regime_analysis` flips its leading regime entirely
  (bull → sideways) between timeframes.
- These two are **not independent confirmations of the same underlying
  fact by coincidence** — they're two different methods (model
  consensus, regime classification) agreeing with each other *and*
  diverging from the 1D picture together. That combination is a real
  confluence signal: "the daily uptrend is real but stalling right now,"
  not "the data is just noisy."

**No real signal added (redundant this cycle)**:
- **Cluster E's `shock_clustering`**, **Cluster F's
  `news_price_causality`**, and **all of Cluster G** returned
  byte-for-byte identical reads at both timeframes. Per
  `02-time-format-richness.md`'s recommendation, this is exactly the
  kind of observation that should accumulate into a real
  `AngleCalibrationEntry`-style record (once it carries `time_format`)
  — not acted on from one cycle, but tracked, so that after enough real
  cycles there's an actual, measured answer to "is checking
  `news_price_causality` at 1H ever worth it," instead of a guess from
  one example.

**What this chapter would tell `forecast_skill`, if wired that far**:
lean toward a lower-confidence, still-`long`-leaning forecast — the
underlying trend hasn't reversed (no cluster called a reversal), but the
short-term stall is real and corroborated, not a single noisy angle.
That's a materially different, better-grounded statement than what
today's 1D-only, unclustered flat digest could ever produce.

---

## Status

Worked example only — demonstrates the 3-chapter structure end to end
with realistic (fabricated) divergence and redundancy patterns. Real
implementation still follows `01-plan.md`'s ordered steps; this file is
the target shape that plan is building toward, not something built
directly from it yet.
