# Analysis angles in scope (the number to use when anyone asks "how many angles ran")

Counted 2026-10-07 against the running initial-analysis service, then changed the same day (four angles switched off, see below).

REGISTERED ANGLES: 27
MODEL ANGLES: 11
SWITCHED-OFF ANGLES: 4
IN-SCOPE ANGLES: 12

## The rule
Every count of angles is measured against the **12 in scope**, never against 27, and never against the older numbers (25, 28, 30, 31) in the earlier design documents. Two groups are out of scope on purpose, and neither is a failure or a gap:
- **11 model angles**, because the models container is dormant (owner rule).
- **4 switched-off angles**, because they repeat another angle or nobody reads them.

- Correct: "AMD has 12 of 12 in-scope angles completed."
- Wrong: "13 of 31 angles ran."
- Where to read it live: `GET /analysis/coverage/{ticker}` gives `angles_with_data` against `required_angle_count` (the 12). Out-of-scope angles show as `not_required`.

## The 12 in scope
| # | Angle | Why it stays |
|---|---|---|
| 1 | arima | the one classical forecast baseline |
| 2 | backtesting_44_metrics | portfolio metrics; used by research and the trade plan |
| 3 | drawdown_deep_dive | drawdown percentages, duration and recovery with news attribution (15-minute capable) |
| 4 | news_price_causality | the only news-impact angle |
| 5 | peer_relative_strength | continuous peer co-movement (kept for now; the weakest overlap with shock_clustering) |
| 6 | pnl_attribution | fed by live results; the feedback loop's own record |
| 7 | regime_analysis | regime tags; used by research, portfolio, strategy |
| 8 | shock_clustering | which peers shock together; used by live and reflection |
| 9 | shock_personality | post-shock behaviour; used by live, reflection, research |
| 10 | signal_evidence | feeds the evidence store |
| 11 | trend_lifecycle | peak and trough library; exit thresholds in percent |
| 12 | trend_session_structure | per-session drawdown and recovery, derived from trend_lifecycle; the 24-hour angle |

## Switched off on 2026-10-07 (4) and why
| Angle | Reason |
|---|---|
| garch | Its own spec says it was extracted from shock_personality, which already fits the same GARCH. A duplicate. |
| exponential_smoothing | Estimates a level and trend from close prices; the same model family as kalman_filters. |
| kalman_filters | Same reason. arima stays as the single classical baseline. |
| search_trends | No other service reads it (0 references), and it depends on an unofficial Google API. |

**How they are switched off:** by name in `vinu-infra/system_manifest.py` (`PERMANENTLY_DISABLED_ANGLES`). The code, the tests and the stored history stay; to switch one back on, delete its name from that list and change the numbers at the top of this file in the same change. The agent's cluster list no longer includes them (cluster A is `arima` only; cluster C is `drawdown_deep_dive` only).

## Out of scope while models are off (11, category: model)
chronos, dlinear, itransformer, kronos, lpatchtst, lstm, patchtst, tft, timer_timerxl, timesfm, tips_regime_aware_transformer.
moirai, moment and lag_llama were removed outright on 2026-10-04; they are not in the 27.

## Known limits of the 12 (so "12 of 12" is not read as "fully 24-hour")
- The angles are computed on regular-session bars today; only trend_session_structure reports by session, and not for the overnight session.
- `VINU_CORRELATION_MARKET_HOURS_ONLY` and `VINU_CORRELATION_SESSION_BREAK_ON_CLOSE` are both `true` (see `03-guards-configs-and-settings`).
- `VINU_STAGE1_START_DATE` is a temporary test value (2026-06-17), so the analysis window is short.
- Run time per angle is **not measured**: the run log records no duration, and re-running on a stored ticker only returns "skipped_existing".

## If the number changes
The guard test `test_the_angle_counts_written_in_the_requirements_pack_match_the_code` fails until the numbers at the top of this file match the angle specs and the switch-off list.
