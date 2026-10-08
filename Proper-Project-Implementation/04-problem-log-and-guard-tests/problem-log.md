# Problem log (every error fixed, and the test that keeps it fixed)

Started 2026-10-07 from this project's fixes up to today. Each entry has: what was seen, the root cause, the fix, the **guard** (a test that fails if the problem returns, written `path::test_name` so `scripts/check_problem_log.py` can verify it exists), what else must agree, and a **status**:

- **GUARDED**: fixed, and a named test exists.
- **FIX, NO TEST**: the fix is in the code, but no test guards it yet. These are the first thing to close.
- **PARTIAL**: a related guard exists but does not cover this exactly.
- **OPEN**: not fixed.

Read `how-to-use-this-log.md` for the rules.

---

## A. Research and strategy validation

### P01 A passed strategy could not be checked (only one bar size, AI said PASS)
- **Seen:** the first research PASS on the AI path could not be verified; the AI's word was the verdict.
- **Root cause:** nothing re-ran the exact strategy code on every bar size; the pass was not tied to evidence.
- **Fix:** `validate_across_bars` runs the same code on every bar size and stores the per-bar evidence; code decides PASS.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_same_code_is_run_unchanged_on_every_bar_size_with_its_own_window`, `vinu-research/tests/test_bar_validation.py::test_missing_holdout_or_stress_is_a_rejection_not_a_pass`
- **Must agree with:** bar sizes in `VINU_SWEEP_INTERVALS`; promotion bar; artifact `bar_interval` and `bar_evidence`.
- **Status:** GUARDED

### P02 Overfitting measure (PBO) cannot be computed for a fixed-rule strategy
- **Seen:** every fixed-rule strategy was blocked because it had no parameter trials.
- **Root cause:** PBO needs many trials; a single strategy has none.
- **Fix:** PBO is waived only when there are no parameter trials, the waiver is stored and stated; a real high PBO still blocks.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_no_parameter_trials_means_pbo_is_waived_and_says_so_but_a_real_high_pbo_still_blocks`, `vinu-research/tests/test_bar_validation.py::test_the_pbo_waiver_needs_a_verified_measurement_for_that_bar_size`
- **Must agree with:** `VINU_RESEARCH_PROMOTION_PBO_REQUIRED`, `..._PBO_THRESHOLD`.
- **Status:** GUARDED

### P03 Too few trades could pass
- **Seen:** a strategy with a handful of trades could meet the bar.
- **Root cause:** trade count was not part of the bar, nor re-checked at promotion.
- **Fix:** 30 trades required, re-checked from the stored count at promotion.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_too_few_trades_is_not_eligible_even_when_everything_else_passes`, `vinu-research/tests/test_bar_validation.py::test_the_stored_trade_count_is_rechecked_at_promotion_and_a_real_high_pbo_still_blocks`
- **Must agree with:** `VINU_RESEARCH_MIN_TRADES_FOR_PASS` (30).
- **Status:** GUARDED

### P04 Thin or stale data was scored as if it were fine
- **Seen:** a bar size with missing data produced numbers.
- **Root cause:** no data check before a test.
- **Fix:** a data problem is reported with a reason and that bar size is not tested; the others still run.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_a_bar_size_with_stale_or_thin_data_is_not_tested_and_says_why_while_the_others_run`, `vinu-research/tests/test_bar_validation.py::test_an_unreachable_price_service_means_nothing_is_tested`
- **Must agree with:** stock-api catalog fields (`backfill_status`, first and last bar time).
- **Status:** GUARDED

### P05 Strategy code read columns the backtest could not supply
- **Seen:** runs spent time and failed on an unknown column.
- **Fix:** such code is rejected before any run is spent; needed indicator columns are requested.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_columns_the_backtest_cannot_supply_are_rejected_before_any_run_is_spent`, `vinu-research/tests/test_bar_validation.py::test_indicator_columns_the_code_reads_are_requested_for_the_backtest`
- **Must agree with:** indicator names in features-api and the simulator.
- **Status:** GUARDED

### P06 One bar size's failure hid the others
- **Fix:** each bar size is isolated.
- **Guard:** `vinu-research/tests/test_bar_validation.py::test_one_bar_size_crashing_does_not_hide_the_others`, `vinu-research/tests/test_bar_validation.py::test_a_run_that_never_executed_is_not_tested_never_eligible`
- **Status:** GUARDED

### P07 Ready-made recipe templates held a single bar (win rate 1.8 percent)
- **Seen:** templates behaved wrongly across bar sizes. Root cause: templates did not hold state per bar; supertrend was fake.
- **Fix:** templates hold state; real supertrend.
- **Guard:** `vinu-research/tests/test_generator.py::test_event_recipes_hold_their_position_between_signals`
- **Status:** GUARDED

### P08 The manager gave up early
- **Root cause:** attempts were counted wrongly; now counted by backtest-runner delegations (`VINU_RESEARCH_MIN_ATTEMPTS`, 3).
- **Guard:** `vinu-agent/tests/test_team_verdict_extraction.py::test_an_early_stop_is_sent_back_until_enough_attempts_were_made`, `vinu-agent/tests/test_team_verdict_extraction.py::test_a_stop_after_enough_attempts_is_accepted`, `vinu-agent/tests/test_team_verdict_extraction.py::test_giving_up_is_still_bounded_when_the_manager_never_complies`, `vinu-agent/tests/test_team_verdict_extraction.py::test_the_delegation_tool_counts_idea_generator_requests`
- **Status:** GUARDED

### P09 A null strategy code became the text "None"
- **Fix:** guard in the research artifact writer.
- **Guard:** `vinu-agent/tests/test_research_artifact_writer.py::test_a_null_strategy_code_is_no_strategy_not_the_text_none`
- **Status:** GUARDED

## B. Orders and the order guard

### P10 The order guard failed open when the strategy store was unreadable
- **Seen:** an unreadable store let orders through.
- **Fix:** it now fails closed.
- **Guard:** `vinu-agent/tests/test_order_guard.py::test_fails_closed_when_store_raises`
- **Must agree with:** seeded mandate `require_active_artifact: true`.
- **Status:** GUARDED

### P11 Orders assumed regular hours only
- **Seen:** no handling of extended-hours or overnight orders; the guard used the regular clock.
- **Fix:** session read from the broker clock; outside regular only day limit orders with `extended_hours`; mandate `allowed_sessions`.
- **Guard:** `vinu-agent/tests/test_session_orders.py::test_regular_session_allows_market_orders`, `vinu-agent/tests/test_session_orders.py::test_the_mandate_can_exclude_a_session`, `vinu-agent/tests/test_session_orders.py::test_a_regular_session_order_is_unchanged`
- **Must agree with:** `vinu_infra/sessions.py`, mandate seed in `entrypoint.sh`, broker submit.
- **Status:** GUARDED

### P12 Overnight order for a stock the broker does not allow overnight
- **Fix:** needs the `overnight_tradable` attribute; fails closed if unknown.
- **Guard:** `vinu-agent/tests/test_session_orders.py::test_overnight_needs_the_overnight_tradable_attribute_and_fails_closed`
- **Status:** GUARDED

### P13 A strategy could trade in a session it was never approved for
- **Fix:** per-session approval stored on the artifact; guard refuses outside it; size multiplier applied; never-measured artifacts are not restricted.
- **Guard:** `vinu-agent/tests/test_session_orders.py::test_the_session_a_strategy_is_approved_for_passes_and_is_sized_by_its_hint`, `vinu-agent/tests/test_session_orders.py::test_an_artifact_that_was_never_measured_per_session_is_not_restricted`, `vinu-agent/tests/test_research_artifact_writer.py::test_a_regular_hours_pass_approves_the_regular_session_only`, `vinu-agent/tests/test_research_artifact_writer.py::test_an_all_session_pass_that_approves_no_session_is_rejected`
- **Status:** GUARDED

### P14 What the broker returns for an order was not written down
- **Fix:** field set from real paper responses (open, cancelled, filled); `order_config_alpaca.py`.
- **Guard:** `vinu-agent/tests/test_order_config_alpaca.py::test_a_real_overnight_fill_is_closed_with_its_price_and_time`, `vinu-agent/tests/test_order_config_alpaca.py::test_open_and_closed_status_sets_do_not_overlap`
- **Status:** GUARDED

### P15 The gatekeeper, allocator and order guard had never been run together
- **Fix:** planted-edge chain test (edge is found and traded safely, no edge is rejected, a bad strategy forced through still cannot be funded, a kill switch holds).
- **Guard:** `vinu-agent/tests/test_chain_planted_edge.py::test_planted_edge_walks_the_whole_chain_and_the_safety_stops_hold`, `vinu-agent/tests/test_chain_planted_edge.py::test_no_edge_is_rejected_by_code_and_the_guard_refuses_the_symbol`, `vinu-agent/tests/test_chain_planted_edge.py::test_a_bad_strategy_forced_through_the_gatekeeper_still_cannot_be_funded`, `vinu-agent/tests/test_chain_planted_edge.py::test_a_kill_switch_engaged_at_funding_time_holds_the_strategy_as_pendblock`
- **Status:** GUARDED (synthetic data only; not yet proven on a real strategy)

## C. Sessions and 24-hour data

### P16 Sessions were defined in several places
- **Fix:** one definition in `vinu_infra/sessions.py`.
- **Guard:** `vinu-infra/tests/test_sessions.py::test_sessions_in_new_york_time`, `vinu-infra/tests/test_sessions.py::test_daylight_saving_moves_the_utc_hours_but_not_the_sessions`
- **Must agree with:** every service that names a session (change-impact list in `02`).
- **Status:** GUARDED

### P17 Candles had no session filter, and daily bars mixed sessions
- **Fix:** filter on 1-minute bars before aggregating; indicator cache keyed by session.
- **Guard:** `vinu-stock-price/tests/test_session_filter.py::test_a_daily_bar_is_built_only_from_the_sessions_asked_for`, `vinu-stock-price/tests/test_session_filter.py::test_indicator_cache_does_not_mix_sessions`
- **Status:** GUARDED

### P18 Backtest metrics assumed 6.5 hours a day
- **Fix:** annualisation by the hours of the sessions traded.
- **Guard:** `vinu-simulator/tests/test_session_annualisation.py::test_all_sessions_are_twenty_four_hours_of_bars`, `vinu-simulator/tests/test_session_annualisation.py::test_extended_is_everything_but_regular_and_a_single_session_counts_its_hours`
- **Status:** GUARDED

### P19 The simulator answered an all-sessions request with the stored regular-hours run
- **Seen:** regular and all-24-hours validation gave identical numbers.
- **Root cause:** the result-reuse key (config hash) ignored the session.
- **Fix:** session added to the hash when not regular (`vinu-simulator/vinu_simulator/service.py`, around line 377).
- **Guard:** `vinu-simulator/tests/test_service.py::test_a_different_session_is_a_different_run_and_reaches_the_price_service`, `vinu-simulator/tests/test_service.py::test_the_default_session_keeps_its_old_hash`
- **Must agree with:** `vinu-research/tests/test_simulator_contract.py` pinned hash.
- **Status:** GUARDED (the guard runs against the image's code, so it passes in the container only after the next deploy)

### P20 Intraday equity curve had date-only timestamps
- **Seen:** per-session attribution impossible: a day's 26 or 96 bars read as one instant.
- **Fix:** full timestamp for intraday (`service.py`, around line 576).
- **Guard:** `vinu-simulator/tests/test_service.py::test_an_intraday_equity_curve_keeps_its_time_of_day`
- **Status:** GUARDED (the guard runs against the image's code, so it passes in the container only after the next deploy)

### P21 The simulator contract changed on purpose
- **Guard:** `vinu-research/tests/test_simulator_contract.py` (pinned request version `ecadb41ee551`, bumped when `session` was added).
- **Status:** GUARDED

### P22 The overnight feed refused a window that reached the last 15 minutes (HTTP 403)
- **Fix:** window clamped to 16 minutes before now (`OVERNIGHT_DELAY_MINUTES`).
- **Guard:** `vinu-stock-price/tests/test_session_filter.py::test_the_overnight_request_stops_short_of_the_last_fifteen_minutes`, `vinu-stock-price/tests/test_session_filter.py::test_a_window_entirely_inside_the_delay_makes_no_overnight_call`
- **Status:** GUARDED

### P23 Backfill skipped years already marked done, so overnight bars never came in
- **Fix:** `refresh` option, merge by timestamp.
- **Guard:** `vinu-stock-price/tests/test_backfill_orchestrator.py::test_a_year_already_marked_done_is_skipped_unless_a_refresh_is_asked_for`
- **Status:** GUARDED

## D. Deployment and stack

### P24 An old container ran old code after a fix
- **Fix:** stale-image check that watches files, moved or deleted files and folders, and removed images.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_a_stale_container_cannot_go_unnoticed`, `vinu-infra/tests/test_stack_guards.py::test_moving_or_deleting_a_file_makes_an_image_stale`, `vinu-infra/tests/test_stack_guards.py::test_a_container_whose_image_was_removed_is_reported_stale_not_a_crash`, `vinu-infra/tests/test_stack_guards.py::test_stale_check_sees_a_changed_file_that_git_considers_unchanged`
- **Status:** GUARDED

### P25 A shared module placed in the wrong folder crash-looped stock-api
- **Seen:** `ModuleNotFoundError` for `vinu_infra.sessions` at start-up.
- **Fix:** file moved to `vinu-infra/sessions.py` (the package maps `vinu_infra` to that folder).
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_every_shared_module_the_code_imports_exists_where_the_package_expects_it` (fails if code imports `vinu_infra.<module>` that is not in `vinu-infra/`; proven by planting a bad import)
- **Status:** GUARDED

### P26 Container or script rules
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_no_script_or_container_entrypoint_has_windows_line_endings`, `vinu-infra/tests/test_stack_guards.py::test_every_shell_script_parses`, `vinu-infra/tests/test_stack_guards.py::test_models_api_is_behind_a_profile_so_it_is_never_built_or_started_by_default`, `vinu-infra/tests/test_stack_guards.py::test_no_default_service_depends_on_models_api`
- **Status:** GUARDED

### P27 Settings that must not drift
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_env_example_pins_the_broker_to_paper`, `vinu-infra/tests/test_stack_guards.py::test_secret_values_are_never_written_in_env_files`, `vinu-infra/tests/test_stack_guards.py::test_the_seeded_mandate_requires_an_active_artifact`, `vinu-infra/tests/test_stack_guards.py::test_the_live_decision_validation_gate_is_never_switched_off_in_deployment_files`, `vinu-infra/tests/test_stack_guards.py::test_the_planner_is_pointed_at_a_screener_ranker_and_takes_the_top_ten`, `vinu-infra/tests/test_stack_guards.py::test_the_local_llm_runs_one_slot_so_concurrent_prompts_queue_instead_of_overflowing`, `vinu-infra/tests/test_stack_guards.py::test_the_reflection_container_serves_its_api_as_well_as_running_the_worker`
- **Status:** GUARDED

### P28 Every bar of the 24-hour backtest was attributed to "afterhours"
- **Seen:** the real AMD 1-hour all-sessions validation showed 6,168 bars in afterhours and none in regular or overnight.
- **Root cause:** `fetch_equity_returns` returned the returns with the table's row-number index (0, 1, 2 ...), not the dates. The attribution read those numbers as times just after 1970, which is 19:00 New York on 31 December 1969. My first tests used a date-indexed series, so they never saw it.
- **Fix:** `fetch_equity_returns(run_id, keep_dates=True)` indexes by bar time; the session profile asks for it. The default is unchanged because other callers align by position.
- **Guard:** `vinu-research/tests/test_session_stats.py::test_the_session_breakdown_of_a_real_shaped_equity_curve_lands_each_bar_in_its_own_session`, `vinu-research/tests/test_session_stats.py::test_the_default_still_returns_the_row_number_index_the_older_callers_align_on`
- **Must agree with:** the simulator's equity timestamps (P20: full timestamp for intraday, naive UTC).
- **Status:** GUARDED

### P29 "How many angles ran" was answered against the wrong number
- **Seen:** the answer was given as a fraction of 28, 30 or 31 angles (or "13 of 31"), although the 11 model angles are off on purpose.
- **Root cause:** the in-scope count was written nowhere; older documents quote counts that include model angles and removed angles.
- **Fix:** `00-project-understanding/analysis-angles-in-scope.md` states 27 registered, 11 model, 16 in scope, checked against the running service (AMD: 16 of 16).
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_the_angle_counts_written_in_the_requirements_pack_match_the_code` (fails when the written numbers differ from the angle specs; proven by changing the number)
- **Must agree with:** `VINU_MODELS_ENABLED`, `resolve_active_angles`, `GET /analysis/coverage/{ticker}`.
- **Status:** GUARDED

### P30 Four overlapping analysis angles were switched off (garch, exponential_smoothing, kalman_filters, search_trends)
- **Seen:** 16 in-scope angles, of which several repeat one another or have no reader; every angle costs run time and a chance of error.
- **Root cause:** angles were added over time without a check of overlap; `garch` was extracted from `shock_personality`, the two smoothing and state angles share a model family, `search_trends` has no consumer.
- **Fix:** the four names are in `PERMANENTLY_DISABLED_ANGLES` (`vinu-infra/system_manifest.py`); the agent's clusters no longer list them (A is `arima`, C is `drawdown_deep_dive`); the prompt paragraph is updated; the in-scope doc says 12. Live check: `/analysis/angles?active=true` returns 12 and the manifest `active_angle_count` is 12.
- **Guard:** `vinu-agent/tests/test_angle_clusters.py::test_no_cluster_lists_an_angle_that_is_switched_off`, `vinu-infra/tests/test_stack_guards.py::test_the_angle_counts_written_in_the_requirements_pack_match_the_code`
- **Must agree with:** `00-project-understanding/analysis-angles-in-scope.md`, the agent's `ANGLE_CLUSTERS`, the angle-synthesizer prompt.
- **Status:** GUARDED (to switch one back on: delete its name from the list, restore it in the clusters, change the doc numbers)

### P31 The reflection worker failed every cycle reading the significance flags ("attempt to write a readonly database")
- **Seen:** `significance_response_outcome` skipped every cycle; the worker mounts the agent's data folder read-only.
- **Root cause:** the flag store migrated its table (two new columns) only on the first write, so a file last written by an older version stayed on the old layout; the read-only reader then tried to migrate it.
- **Fix:** `SignificanceFlagStore.__init__` migrates when the owning service opens the file (a read-only opener just skips it).
- **Guard:** `vinu-agent/tests/test_significance_triage.py::test_opening_an_old_layout_file_adds_the_new_columns_at_once`, `vinu-agent/tests/test_significance_triage.py::test_the_old_rows_survive_and_reading_needs_no_further_change`
- **Must agree with:** the reflection worker's read-only mounts in `docker-compose.yml`; any other store that migrates lazily.
- **Status:** GUARDED (live: the analyst now runs and returns 0 findings, because there are no flags yet)

### P32 A stalled model server held the gateway's one slot for 15 minutes per call while the queue behind it expired
- **Seen:** on 2026-10-07 from about 10:21 to 11:37 UTC the local model (port 8092) accepted calls and never answered. 23 research calls expired after about 1,750 s in the queue; 48 calls failed with "upstream did not answer within 300s". Normal calls end well inside 200 s.
- **Root cause:** each call tried 3 times at 300 s, so a stalled server cost 15 minutes of the single slot per call. Ordering was not the problem (priorities and aging already exist in `priorities.py` and the store).
- **Fix:** after 2 upstream timeouts in a row (`STALL_STREAK`), further timeouts are not retried and the call fails at once with "the model server is stalled; not retried"; any answer resets the count. A stall now costs 300 s per call, not 900 s.
- **Guard:** `vinu-llm-gateway/tests/test_gateway.py::test_a_stalled_model_server_is_not_retried_so_it_cannot_hold_the_slot`, `vinu-llm-gateway/tests/test_gateway.py::test_an_answer_clears_the_timeout_streak`
- **Must agree with:** `VINU_LLM_GATEWAY_ATTEMPT_TIMEOUT_SEC` and `VINU_LLM_GATEWAY_MAX_ATTEMPTS`; the research retry rule (3 attempts per strategy run).
- **Status:** GUARDED (the cause of the stall itself is on the host model server, outside this repo; not found)

### P33 The live scheduler's own trades never reached the book the breaker, cooldown and symbol lockout read
- **Seen:** the edge `book.writes->live.scheduler` was a declared gap since 2026-10-02: a filled scheduler order was recorded only in `scheduler_executions`, so a loss on the scheduler path could not trip the daily-loss breaker, the cooldown or the 72-hour symbol lockout (O5).
- **Root cause:** the fill-enrichment pass wrote fill price and quantity to the ledger and stopped; nothing turned a fill into a book position.
- **Fix:** `apply_fill` in `book/positions.py` (long-only: a buy opens or adds, a sell reduces and closes at zero, a sell with nothing open is reported and invents nothing). The enrichment pass calls it through `_write_fill_to_book`; the ledger column `book_applied_qty` makes a growing partial fill count once. The edge is now `wired` and instrumented, so `/research/pipeline-edges` shows whether it flows.
- **Guard:** `vinu-live/tests/test_execution_fill_enrichment.py::test_a_filled_buy_and_sell_land_in_the_book_so_the_breaker_sees_the_loss`, `vinu-live/tests/test_execution_fill_enrichment.py::test_a_partial_fill_that_grows_is_written_once_not_twice`, `vinu-live/tests/test_execution_fill_enrichment.py::test_a_sell_with_nothing_open_invents_no_position_and_is_reported`, `vinu-live/tests/test_execution_fill_enrichment.py::test_an_unfilled_order_writes_nothing_to_the_book`
- **Must agree with:** `vinu-infra/pipeline_edges.yaml` (the edge entry names `apply_fill`); the orchestrator's own book writes (one book, one position per symbol).
- **Status:** GUARDED (not yet seen on a real fill: that needs the first real ACTIVE strategy, O8; shorts are not handled)

### P34 At night the live code chose market orders, which the order guard refuses: exits would have been blocked
- **Seen:** `_choose_entry_order_type` returns "market" unless the spread is wide or unknown, and every scheduler exit is a market order. Pre-market, after-hours and overnight the broker takes only limit orders with no stop leg, so those orders were refused (O9).
- **Root cause:** routing knew about spreads, not sessions.
- **Fix:** `extended_hours_route` in `guards.py`, called by the scheduler and by the orchestrator's `_submit_order`: outside the regular session the order becomes a limit set `EXTENDED_MARKETABLE_BPS` (30, `VINU_LIVE_EXTENDED_MARKETABLE_BPS`) through the price (the caller's price, else the live quote mid), and any stop leg is dropped. With no price at all it is left unchanged, so the guard refuses it visibly. The weekend gap is left as before (the order queues).
- **Guard:** `vinu-live/tests/test_extended_hours_routing.py::test_an_exit_at_night_becomes_a_limit_a_little_below_the_price`, `vinu-live/tests/test_extended_hours_routing.py::test_the_scheduler_sends_a_limit_exit_at_night`, `vinu-live/tests/test_extended_hours_routing.py::test_the_orchestrator_sends_a_limit_and_no_stop_leg_at_night`, `vinu-live/tests/test_extended_hours_routing.py::test_with_no_price_the_order_is_left_for_the_guard_to_refuse_not_invented`. `vinu-live/tests/conftest.py` fixes the clock to a regular session so older tests do not depend on when they run.
- **Must agree with:** `vinu-agent/vinu_agent/broker/order_guard.py` and `alpaca.py` (what they refuse and accept outside regular hours); `vinu_infra/sessions.py`.
- **Status:** GUARDED (the 30 bps is a guessed starting value; not yet seen on a real night exit)

### P35 The benchmark comparison (alpha, beta, tracking error) was never computed in the research loop
- **Seen:** (O12) the strategy's equity returns have a row-number index and the benchmark's has dates; the comparison aligned on index and dropped what it could not match, so it returned nothing and the loop skipped it silently.
- **Fix:** `compute_benchmark_comparison_by_date` in `benchmark.py` compounds both series to one return per calendar date first (timezone dropped), and the loop calls it with a dated copy of the strategy returns. Other steps (correlation gate, PBO, portfolio) keep the row-number series they align on.
- **Guard:** `vinu-research/tests/test_benchmark.py::TestComparisonByDate::test_the_plain_function_finds_nothing_in_common_across_a_row_index_and_dates`, `vinu-research/tests/test_benchmark.py::TestComparisonByDate::test_hourly_strategy_bars_are_compounded_to_dates_and_compared`, `vinu-research/tests/test_benchmark.py::TestComparisonByDate::test_the_research_loop_uses_the_dated_comparison`
- **Must agree with:** `fetch_equity_returns(keep_dates=True)`; `loop.py` where alpha is read for suggestions and the report.
- **Status:** GUARDED (the numbers are informational: nothing in promotion reads alpha or beta; not yet seen in a real run)

### P36 A session could be approved on thin data, or on the gap between sessions
- **Seen:** (O13) real AMD 1h: pre-market had 549 bars in 1.3 years (about 2 a day) yet showed Sharpe 3.4 and was approved at 0.30 size, while the regular session lost money. The first bar after a gap also carried the whole gap.
- **Fix:** `session_stats.py`: a bar whose gap from the previous bar is over `GAP_FACTOR` (2x) the usual spacing is counted as `gap_bars` and left out of every session's statistics; a non-regular session's bars per day must reach `MIN_DENSITY` (0.5) of what the regular session's density implies for its length, else `insufficient_data` ("too thin"). `bars` still counts every bar; `valid_bars` is what the statistics and the 200-bar floor use.
- **Guard:** `vinu-research/tests/test_session_stats.py::test_a_session_that_looks_great_on_thin_data_is_not_approved`, `vinu-research/tests/test_session_stats.py::test_the_first_bar_after_a_gap_is_not_credited_to_the_session_it_lands_in`, `vinu-research/tests/test_session_stats.py::test_full_density_data_is_still_judged_on_its_returns`
- **Must agree with:** `vinu_infra/sessions.py` (session lengths in `SESSION_MINUTES`); `promotion.py` (reads the chosen session's row).
- **Status:** GUARDED (2x and 0.5 are guessed values, not fitted; the AMD run was not re-run, so that breakdown is not yet re-checked)

### P37 The env template listed 17 settings that nothing reads, among them the two "market hours only" switches
- **Seen:** (O2) `VINU_CORRELATION_MARKET_HOURS_ONLY` and `..._SESSION_BREAK_ON_CLOSE` looked like they limited analysis to regular hours. No code reads them or any other `VINU_CORRELATION_*` setting except the API address: they belonged to a service that no longer exists. Five other unread names (`VINU_DECAY_*`, `VINU_LLM_ANALYSIS_*`, `VINU_LLM_TTL_SEC`) were also dead.
- **Fix:** removed from `.env-example` (the live `.env` still carries them; they do nothing). A general guard now fails when the template lists a setting no code, compose file or script reads.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_every_setting_in_the_env_example_is_read_by_something`
- **Status:** GUARDED (no setting limits the 2022 analysis windows to regular hours; whether they should be is a design question for the angles, not a switch)

### P38 A two-week test override of the analysis start date was still deployed
- **Seen:** (O1) `VINU_STAGE1_START_DATE=2026-06-17` in `.env` and the template: every analysis window was a few months long, so angles were judged on tiny samples.
- **Fix:** both set to `2022-01-01` (history from 2022 exists: 248 backfill years done, 2 failed in 2022); the agent and analysis containers were recreated and show the new value. Analyses will be recomputed on the longer windows over the next scheduler cycles.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_the_env_example_keeps_the_full_history_start_date_not_the_short_test_override`
- **Must agree with:** `quarters.py` (the start must stay before the current period's start)
- **Status:** GUARDED (the guard covers the template; the live `.env` was set by hand and has no test)

### P39 Running the infra tests on the host left stray databases next to the real stores
- **Seen:** (O18) `strategy_store.db` and `market_regime_history.db` appeared in `vinu-components/data` after a host run, because some code defaults its data root to `./data` under the working folder.
- **Fix:** `vinu-infra/tests/conftest.py` runs every infra test from its own empty temporary folder.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_the_infra_tests_run_in_an_empty_folder_so_they_cannot_leave_databases_among_the_real_ones`
- **Status:** GUARDED (verified: a full host run now leaves no `.db` in `data/`)

### P40 The reflection worker had no health check, so the scoreboard always showed it as unchecked
- **Seen:** (O15, last part) the container ran the worker and the API but declared no health check, so `docker compose ps` and `pipeline_health.py` could not tell a working worker from a dead API.
- **Fix:** the reflection API now exposes `/reflection/health` and the compose file gives the container a health check on it. If the worker loop dies the container exits and restarts (it is the main process); the check covers the API process.
- **Guard:** `vinu-reflection/tests/test_routes_synthesis.py::test_the_service_answers_a_health_check`, `vinu-infra/tests/test_stack_guards.py::test_every_long_running_service_in_the_compose_file_has_a_health_check`
- **Status:** GUARDED (the check does not prove the worker's last cycle succeeded; the five waiting analysts and the likely-inert `screener_agreement` stay under O15)

### P41 A deploy killed research runs that were in flight
- **Seen:** (O7, O17) 24 of the 30 failed research runs in one day were "interrupted: the agent container restarted"; a run takes 5 to 100 minutes, so any restart of a service it uses killed it. Most of those restarts were deploys.
- **Fix:** `scripts/stack.sh deploy` now refuses to restart `agent-api`, `research-api`, `llm-gateway` or `quant-core-api` while a run is in flight, and prints how to wait or override (`FORCE=1`). This stops the self-inflicted kills; it does not make runs survive a crash or a power cut.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_deploy_refuses_to_restart_the_research_services_while_a_run_is_in_flight`
- **Status:** GUARDED (a text check of the script; the refusal itself was not exercised against a live run). Resumable runs remain open as O7.

### P42 The initial-analysis test suite never finished in the container
- **Seen:** (O14) the full suite hung for over 12 minutes with no output: tests reached the real news client, which calls a service that is not there and retries with backoff.
- **Fix:** `vinu-initial-analysis/tests/conftest.py` makes the real news client return no articles in every test (tests that need articles pass their own fake client). (This was only part of the cause: see P49.)
- **Guard:** `vinu-initial-analysis/tests/test_api_v1.py::test_trigger_and_poll_flow` (it used to wait on the news retries inside a 30 s deadline and now passes in the suite run).
- **Status:** GUARDED (superseded by P49: the first fix was incomplete; the package now runs whole in 116 s)

### P43 A restart threw away all the work of a research run that was nearly done
- **Seen:** (O7, O17) interrupted research runs held up to 17 finished specialist tasks (1.4 hours of idea, backtest and critic results); the next run for the ticker started from nothing.
- **Fix:** a research run's finished specialist tasks are already stored in `team_tasks`. When a research run starts, `TeamManager` looks for the latest run of the same ticker (same session id, `planner-<ticker>`) that a restart cut short in the last 6 hours and nobody has picked up, adds a briefing of its finished work (up to 6,000 characters, newest kept; 700 per task) to the prompt, and counts its tested backtests toward the minimum-attempts budget. The old run is marked `resumed_by` the new one, so it is carried over once. Failures for any other reason, other teams and other tickers are never carried over. This is resume-by-briefing: the model is told what was done; it does not continue the old conversation.
- **Guard:** `vinu-agent/tests/test_research_run_resume.py::test_the_next_research_run_gets_the_earlier_work_in_its_prompt_and_is_linked`, `vinu-agent/tests/test_research_run_resume.py::test_the_store_finds_only_a_recent_unclaimed_interrupted_run_of_the_same_session`, `vinu-agent/tests/test_research_run_resume.py::test_a_run_that_failed_for_another_reason_is_not_resumed`, `vinu-agent/tests/test_research_run_resume.py::test_a_team_other_than_research_never_carries_work_over`, `vinu-agent/tests/test_research_run_resume.py::test_the_briefing_lists_finished_work_and_counts_tested_attempts`
- **Must agree with:** `reconcile-runs` in `cli.py` (it writes the `interrupted:` message this lookup matches); the planner worker's session id `planner-<ticker>`; the minimum-attempts rule (`VINU_RESEARCH_MIN_ATTEMPTS`).
- **Status:** GUARDED (not yet seen on a real restart; the 6-hour window and the briefing size are guessed values; a run killed before any backtest only carries ideas)

### P44 A wedged model server stayed wedged until a person restarted it
- **Seen:** (O19) on 2026-10-07 the model (`hindsight-llm`, llama.cpp, one slot) froze twice with one request stuck (`n_decoded` fixed at 410 of 8000, container at 97% CPU, GPU idle); every call behind it timed out for over an hour the first time; its health check said healthy throughout.
- **Fix:** `scripts/model_guard.py` reads `/slots` and restarts the container when the busy slot shows the same task at the same token count for 300 s, then waits 10 minutes before judging again. A host scheduled task (`vinu-model-guard`, installed with `scripts/install_model_guard.ps1`) runs it every minute; it writes `logs/model_guard.log` and `logs/model_guard.json`. An unreadable `/slots` (container stopped or starting) does nothing.
- **Guard:** `vinu-infra/tests/test_model_guard.py::test_a_frozen_slot_is_restarted_once_it_has_been_frozen_long_enough_then_left_alone`, `vinu-infra/tests/test_model_guard.py::test_a_slot_that_keeps_advancing_is_never_restarted`, `vinu-infra/tests/test_model_guard.py::test_an_idle_slot_clears_the_memory_so_the_next_request_starts_a_fresh_count`
- **Must agree with:** the gateway's 300 s attempt timeout (the guard waits as long as one attempt, so a slow call is not cut); the model container name and port in `docker-compose-hindsight.yml`.
- **Status:** GUARDED (installed and ran by itself, result 0; the restart path has not yet fired on a real wedge; the cause of the freeze is still unknown; the task lives on this PC only, so it must be installed again on a new machine)

### P45 A backtest charged the same trading cost at 3 a.m. as at noon
- **Seen:** (O3, O10) every trade paid the same slippage and spread in every session, so overnight and pre-market results were flattered and session approval rested on them.
- **Fix:** the cost models take a per-bar `session_multiplier` that scales slippage and spread (not the commission). For bars with a time of day the engine sets it from the bar's session: `VINU_SIM_SESSION_COST_MULT`, default `premarket=5,regular=1,afterhours=7,overnight=3` (first set as guesses 2, 1, 2, 3; replaced on 2026-10-08 by a base from published spread figures, see `03-guards-configs-and-settings/session-cost-evidence.md`). Daily bars are stamped at midnight and are never scaled. Both cost models (flat and Almgren-Chriss) use it.
- **Guard:** `vinu-simulator/tests/test_costs.py::TestSessionScaledCosts::test_an_overnight_round_trip_costs_more_than_the_same_one_in_the_regular_session`, `vinu-simulator/tests/test_costs.py::TestSessionScaledCosts::test_the_multiplier_follows_the_session_of_the_bar`, `vinu-simulator/tests/test_costs.py::TestSessionScaledCosts::test_the_commission_is_not_scaled`, `vinu-simulator/tests/test_costs.py::TestSessionCostBase::test_the_default_table_is_the_documented_one`
- **Must agree with:** `vinu_infra/sessions.py` (the session names); the live order guard (it does not use these numbers).
- **Status:** GUARDED (the base is rough: after-hours 7 is measured in one earnings-based study, overnight 3 holds for stocks that trade consistently, pre-market 5 has no direct figure. Strategies tested after the changes see higher night costs, so earlier overnight verdicts are not comparable)

### P46 Nobody was measuring quote spreads, so the cost multipliers had nothing to be fitted to
- **Seen:** (O10) the stock service only answered live quotes at order time and kept no history; there was no way to see what a spread costs in each session.
- **Fix:** the stock ingest loop now takes 5 quote snapshots per cycle (walking the watchlist round and round) and files each spread under the session it was taken in (`vinu_spreads.db`, `SpreadStore`). `GET /stock/spread-stats?days=N` returns the median and 90th-percentile spread per session and the multipliers they imply (session median over regular median, never below 1; `null` for a session with fewer than 30 snapshots, so it never guesses).
- **Guard:** `vinu-stock-price/tests/test_api.py::test_a_snapshot_pass_files_the_spread_under_the_current_session_and_the_route_reports_it`, `vinu-stock-price/tests/test_api.py::test_suggested_multipliers_are_session_median_over_regular_median_only_with_enough_samples`, `vinu-stock-price/tests/test_api.py::test_an_unusable_quote_is_not_filed`
- **Must agree with:** `VINU_SIM_SESSION_COST_MULT` in the simulator (P45): replace its guessed 2, 1, 2, 3 with the suggested multipliers once every session has 30 or more snapshots.
- **Status:** GUARDED (live: 70 regular-session snapshots in the first minutes. The first reading is NOT trustworthy as a cost: median 31 bps, 90th percentile 598 bps for liquid names, because the data feed is IEX-only (the SIP feed is not permitted) and one exchange's quote is much wider than the national best bid and offer. The ratio between sessions may still be useful; the absolute level is not)

### P47 `stack.sh deploy` rebuilt the images but left the containers on the old ones
- **Seen:** on 2026-10-07 `deploy` built five services, then `docker compose up -d` printed "Running" for them and recreated nothing; `stale_images.py` kept reporting "the container's image no longer exists". The new code was not running until I forced the recreate by hand.
- **Fix:** `deploy` now runs `docker compose up -d --force-recreate --no-deps` on exactly the stale services it just rebuilt.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_deploy_recreates_the_rebuilt_containers_instead_of_leaving_them_on_the_old_image`
- **Status:** GUARDED (verified live: after the change, deploy ended with "every running service is built from its current source"; the cause of compose skipping the recreate is not known)

### P48 The screener-agreement analyst skipped every cycle because an audit file did not exist yet
- **Seen:** (O15) `screener_agreement` skipped each cycle with "unable to open database file". I had assumed it was inert because this system uses rankers, not rules. Reading it showed two halves: the ranker half (I) had its data (`screener_rankers.db`, `screener_ranker_churn.db`), and only the rule-fire half (X) reads `screener_audit.db`, which exists only after a rule has fired. Opening the missing file on the read-only mount raised and took the working half down with it.
- **Fix:** the rule-fire half runs only when `screener_audit.db` exists; the ranker half always runs.
- **Guard:** `vinu-reflection/tests/test_screener_agreement.py::TestRuleAuditFileMissing::test_the_ranker_half_still_reports_when_no_rule_has_ever_fired`, `vinu-reflection/tests/test_screener_agreement.py::TestRuleAuditFileMissing::test_nothing_at_all_still_returns_no_findings_without_error`
- **Status:** GUARDED (live: it now returns a finding for the `core_starter` ranker, agreement rate up 0.13, PSI 0.08, below the 0.25 alarm level. The earlier claim that this analyst is probably inert for good was wrong)

### P49 The initial-analysis tests quietly used the live stack, which made the suite slow and sometimes stuck
- **Seen:** (O14) when a call to `localhost` is refused, `net.request` retries it against `host.docker.internal`. Inside the test container that reaches the LIVE stack's published ports, so tests pulled real market data (and `test_trigger_and_poll_flow` only passed because the live stack held real AAPL history). One test (`test_pnl_attribution.py::TestRoutes::test_run_with_angle_names_does_not_error`) then sat for minutes. I first blamed the two parallel arima tests: wrong. They are slow (35 s and 498 s) but they finish.
- **Fix:** `vinu-initial-analysis/tests/conftest.py` blocks the price and news clients' network calls in every test (a test that needs HTTP patches the client itself), and `test_trigger_and_poll_flow` gets its own synthetic bars. The slow arima test uses a refit cadence of 4. I also tried starting the parallel backtest workers with `forkserver` instead of `fork` as a precaution and reverted it: it was not the cause, and it broke a test because forkserver workers do not see environment variables set after the helper starts.
- **Guard:** `vinu-initial-analysis/tests/test_api_v1.py::test_trigger_and_poll_flow`, `vinu-initial-analysis/tests/test_arima_backtest.py::test_parallel_at_cadence_greater_than_1_runs_but_is_not_identical_to_sequential`
- **Status:** GUARDED (full package in the image, nothing deselected: 389 passed, 7 skipped in 116 s)

### P50 A small order cut into time slices produced slices of zero shares
- **Seen:** (live drill, 2026-10-08) a 2-share order planned as TWAP or VWAP came out as several slices, some of 0 shares. The scheduler would send each as an order, and the guard refused the empty ones.
- **Fix:** `_without_empty_slices` in `vinu-live/vinu_live/execution.py` drops empty slices and gives their share to the neighbours, so the slice quantities still add up to the order.
- **Guard:** `vinu-live/tests/test_execution.py::TestSmallOrdersAreNotCutIntoEmptySlices::test_twap_of_a_two_share_order_has_no_zero_quantity_slice`, `vinu-live/tests/test_execution.py::TestSmallOrdersAreNotCutIntoEmptySlices::test_vwap_of_a_small_order_has_no_zero_quantity_slice`
- **Status:** GUARDED (live suite 964 passed before the agent change)

### P51 The session size hint (for example half size after hours) was ignored when the optional soft limits were off
- **Seen:** (live drill) the artifact was approved for after-hours with size multiplier 0.5, yet the first after-hours entry was sent at full size, because the multiplier only ran together with the opt-in soft limits.
- **Fix:** `session_size_multiplier` in `vinu-agent/vinu_agent/broker/order_guard.py` returns just the session part; `vinu-agent/vinu_agent/tools/trade_tool.py` always applies it to entries (never to `reduce_only` exits), while the other soft limits stay opt-in. Checked live: a 4-share entry became 2 and a 1-share entry was refused as "below one share".
- **Guard:** `vinu-agent/tests/test_session_orders.py::test_the_session_size_hint_applies_without_the_opt_in_soft_limits`, `vinu-agent/tests/test_trade_tool.py::TestTradeToolPreApproveResultChecked::test_the_session_size_hint_scales_an_entry_even_with_soft_limits_off`, `vinu-agent/tests/test_trade_tool.py::TestTradeToolPreApproveResultChecked::test_an_exit_is_never_scaled_by_the_session_hint`
- **Status:** GUARDED (the claim "agent suite 0 failures" first written here was wrong: 21 tests failed and the summary hid them, see P56 and P57; after both fixes the agent suite in the image shows 1681 passed)

### P52 Live drill of the gatekeepers on Alpaca paper (2026-10-08): results
- **Seen:** a synthetic edge (planted trend, measured by the real simulator) was written as a real artifact for AAPL and pushed down the whole chain. Worked: no ACTIVE artifact and BENCHING are refused; the gatekeeper hook moved it to PEND and the allocator to ACTIVE; research-api and portfolio-api saw it; the scheduler reached the order step; after-hours routing sent a limit order; a session not approved was refused; the kill switch refused a new entry (`kill_switch_halt`) while a `reduce_only` exit still passed and filled; `max_position_pct` refused an oversized order; a 2-share entry filled at 336.80 and the next cycle's fill enrichment recorded the fill, 6.5 bps slippage and `book_applied_qty` 2; the exit filled at 336.54. Afterwards the artifact was set DISABLED, nothing rests at Alpaca, the kill switch is off. Two of my own drill calls used a wrong field (`type` instead of `order_type`), so they went as market orders and the guard correctly refused them; not a system fault.
- **Fix:** not applicable; this entry records evidence. The two defects the drill found are P50 and P51.
- **Guard:** the P50 and P51 guard tests; the drill itself is a manual script, not repeatable in the suite because it spends paper money.
- **Status:** GUARDED (by P50 and P51; open findings O20 to O22)

### P53 Capital could go to 11 unvalidated YAML strategies
- **Seen:** (O20) portfolio-api put equal weights on the 11 YAML registry strategies, which no research run ever validated, next to the ACTIVE research artifacts.
- **Fix:** `include_yaml_strategies` in `vinu-portfolio/vinu_portfolio/config.py` (env `VINU_PORTFOLIO_INCLUDE_YAML_STRATEGIES`, default off) and `list_active_strategies` in `vinu-portfolio/vinu_portfolio/service.py`: only ACTIVE artifacts get capital unless it is switched on.
- **Guard:** `vinu-portfolio/tests/test_service.py::TestYamlStrategiesAreNotAllocatedByDefault::test_the_unvalidated_yaml_strategies_get_no_capital_unless_switched_on`
- **Status:** GUARDED (portfolio suite in the image: 0 failures). The allocator's `amount` is still ignored by portfolio-api (O20).

### P54 The starting mandate allowed shorts although the book is long-only
- **Seen:** (O22, decided with the user 2026-10-08: long only for now, shorts later as their own feature) `vinu-agent/entrypoint.sh` wrote `allow_short: true` into the mandate.
- **Fix:** the entrypoint now writes `allow_short: false`; the running container's mandate file was changed to match. Exits are reduce-only sells and are not affected.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_the_starting_mandate_is_long_only_because_the_book_is_long_only`
- **Status:** GUARDED (stack guards 38 passed)

### P55 After its first fill the scheduler stopped managing its own position
- **Seen:** (live drill) P33 writes scheduler fills into the book, but the ownership check treated every book position as the trade-plan orchestrator's. The cycle after the AAPL fill reported AAPL as "orchestrator-owned" and skipped it, so a retired strategy's position would never have been closed by the scheduler.
- **Fix:** the ownership split in `vinu-live/vinu_live/scheduler.py`: a book position in a symbol the scheduler bought stays the scheduler's unless an active trade plan claims it.
- **Guard:** `vinu-live/tests/test_scheduler_allocation_and_ownership.py::test_a_position_the_scheduler_bought_stays_the_schedulers_after_its_fill_reaches_the_book`, `vinu-live/tests/test_scheduler_allocation_and_ownership.py::test_a_book_position_with_an_active_plan_is_still_the_orchestrators`
- **Status:** GUARDED (live suite in the image: 0 failures)

### P56 The test harness said "0 failures" while 21 tests had failed
- **Seen:** (2026-10-08) the agent-api run's log listed 21 failed tests, yet the summary line printed `failing tests recorded: 0`. `grep` treated the log as binary ("Binary file matches") and counted nothing. I had passed that "0" on to the user as a clean suite; it was not.
- **Fix:** `scripts/test_in_containers.sh` reads the logs with `grep -a` (text mode) for both the pass lines and the failure count.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_the_test_harness_counts_failures_even_when_a_log_looks_binary_to_grep`
- **Status:** GUARDED (rerun with the fixed counter: agent 1681 passed, live 978, portfolio 320 plus infra 469, 0 failures; the numbers were read from the logs, not from the summary alone)

### P57 The session size hint (P51) broke 21 agent tests that use a mocked guard
- **Seen:** the P51 change made the trade tool compare the guard's session multiplier, which a mocked guard returned as a `MagicMock`, so 21 tests in `test_trade_tool.py` and `test_trade_tool_audit_trail.py` raised `TypeError` (hidden by P56).
- **Fix:** every mocked guard in those two files now returns a neutral `MultiplierResult(1.0, {}, None)`. The production code was right; the tests were incomplete.
- **Guard:** `vinu-agent/tests/test_trade_tool.py::TestTradeToolPreApproveResultChecked::test_successful_order_submission`, `vinu-agent/tests/test_trade_tool_audit_trail.py::TestStrategyEvaluationWrite::test_passed_order_writes_pass`
- **Status:** GUARDED (42 tests in the two files pass; full agent suite 1681 passed)

### P58 Sizes came from the 96,000 paper balance; nothing knew the real 20 dollars or what was already committed
- **Seen:** (the user's point, 2026-10-08) allocation, order sizes and the capital allocator team's budget (a fixed 100,000) all ignored the real-money base, and no record said how much money open trades already held.
- **Fix:** one capital base `VINU_REAL_CAPITAL` and one free-cash rule (`CapitalState` in `vinu-infra/capital.py`: free cash = capital - committed - reserve). The pure allocator `vinu-portfolio/vinu_portfolio/capital_allocator.py` (shrunk win rate, fractional Kelly, position cap, fail/win cash scenarios, whole-share check) is fed by `vinu-portfolio/vinu_portfolio/capital_plan.py` and replaces the daily allocation's dollars when a base is set (the drawdown ladder scales what is held, the maturity ladder only new money). The capital ledger in vinu-live (`capital_ledger.py`, `GET /live/capital`) counts open positions at cost plus buys still filling. The order guard (`order_guard.py`) refuses entries above the free cash and fails closed when the ledger is unreadable or of the other money mode; exits are exempt. The capital allocator team's budget is the ledger's free cash (`scheduler_workers.py`). The agent reads the answer through `get_capital_summary` (agents: allocation_analyst, exposure_reviewer, live_decision_agent) and `GET /portfolio/capital-plan`; nothing is pushed to it. Settings are in `.env-example`; the live stack runs as a 20-dollar paper account (`VINU_REAL_CAPITAL=20`, mode paper).
- **Guard:** `vinu-portfolio/tests/test_capital_allocator.py::TestAllocation::test_nothing_is_allocated_above_the_free_cash`, `vinu-portfolio/tests/test_capital_plan.py::test_the_plan_is_sized_from_the_twenty_dollars_not_the_account`, `vinu-live/tests/test_capital_ledger.py::test_committed_money_is_open_positions_at_cost_and_locks_the_cash`, `vinu-agent/tests/test_free_cash_guard.py::test_an_entry_above_the_free_cash_is_refused_with_the_figures`, `vinu-agent/tests/test_capital_allocator_worker.py::TestBudgetFromTheRealMoneyLedger::test_with_a_capital_base_the_budget_is_the_ledgers_free_cash_not_the_configured_figure`, `vinu-agent/tests/test_capital_summary_tool.py::test_it_reads_the_allocators_answer_and_is_read_only`
- **Status:** GUARDED (checked live: the ledger reports 20 / reserve 8 / free 12, and the guard refused a 336-dollar entry with the figures. A funded plan has not been seen live because no strategy has return history yet, see O23)

### P59 Paper and real money were not tagged, so they could mix
- **Seen:** no table said which money a row was made under.
- **Fix:** `account_mode` (paper or real; set by `VINU_ACCOUNT_MODE`) is stored on book positions (open and closed), the scheduler's order ledger, the allocation history (plus `capital_base` and `committed`; a real stack also writes its own file `allocation_history_real.db`) and every safety-ledger event. Reads filter by the stack's own mode; summaries say which mode they are for. Rows from before were all Alpaca paper and default to `paper`.
- **Guard:** `vinu-live/tests/test_capital_ledger.py::test_positions_are_tagged_and_the_other_mode_is_never_counted`, `vinu-live/tests/test_execution_log_mode.py::test_orders_are_tagged_and_each_mode_sees_only_its_own`, `vinu-agent/tests/test_capital_summary_tool.py::test_safety_ledger_events_are_tagged_with_the_account_mode`, `vinu-infra/tests/test_stack_guards.py::test_the_money_tables_carry_the_account_mode_tag`
- **Status:** GUARDED (the reflection and research results are not yet split by mode, see O23)

### P60 A position closed outside the scheduler stayed in the book and locked the capital
- **Seen:** (live check right after P58) the manual AAPL exit never reached the book, so the ledger showed 2 AAPL at 673.60 committed against a 20-dollar base, free cash 0, and every entry was refused. Worse, the scheduler's cycle returned early when there was nothing to trade and so never reached any reconciliation.
- **Fix:** `sync_book_to_broker` in `vinu-live/vinu_live/book/sync.py` cuts the book down to what the broker holds (never grows it; the exit price is unknown so the cut is at entry price and counts as neither win nor loss). The scheduler runs it first in every cycle, even when there are no target weights. Checked live: after one cycle committed went from 673.60 to 0 and free cash to 12.00.
- **Guard:** `vinu-live/tests/test_book_sync.py::test_a_position_the_broker_no_longer_holds_is_closed_in_the_book_and_frees_the_money`, `vinu-live/tests/test_book_sync.py::test_the_scheduler_syncs_the_book_even_in_a_cycle_with_nothing_to_trade`
- **Status:** GUARDED (live suite 978 passed; the capital stays locked until the next cycle after a manual exit, which is the safe direction)

### P61 The breaker measured losses against the 96,000 paper balance, so it could never trip on a 20-dollar account
- **Seen:** (drill of the breaker, 2026-10-08) `breaker/engine.py` takes its percentage limits (daily loss 5 percent, leverage 2) of `portfolio_value`, which the scheduler filled with the Alpaca equity. On 96,000 a 5 percent daily loss is 4,800 dollars; the 20-dollar base can lose at most 20. It also counted every position in the paper account, not only the system's own.
- **Fix:** `_check_breaker` in `vinu-live/vinu_live/scheduler.py`: with `VINU_REAL_CAPITAL` set, `portfolio_value` is the capital base, the positions checked are the book's own long positions, and the day's loss is realized today plus what the open positions are down since entry (a conservative stand-in for the day's move). Without a base nothing changes.
- **Guard:** `vinu-live/tests/test_breaker_on_real_capital.py::test_a_loss_that_is_small_on_the_paper_balance_halts_a_twenty_dollar_account`, `vinu-live/tests/test_breaker_on_real_capital.py::test_only_the_systems_own_positions_count_not_the_rest_of_the_paper_account`
- **Status:** GUARDED (not seen to trip live: the breaker only runs when there is something to trade and no strategy is ACTIVE yet, so the proof is at test level)

### P62 The cooldown read losses of both money modes, and its docs said the scheduler's losses were invisible to it
- **Seen:** `cooldown_active` in `vinu-live/vinu_live/trade_plan/orchestrator.py` read `closed_positions` with raw SQL and no `account_mode` filter, so paper losses could lock a real account. The scheduler's entry-guard docstring also said the scheduler writes no fills to the book, which stopped being true with P33.
- **Fix:** the query filters by the stack's money mode; the docstring now says the cooldown and the symbol lockout see the scheduler's own losses (checked by test: three losing scheduler trades lock the symbol, a win ends the streak, two losses start the cooldown, the other mode's losses do not count).
- **Guard:** `vinu-live/tests/test_loss_guards_on_scheduler_trades.py::test_losses_made_with_the_other_money_do_not_lock_this_stack`, `vinu-live/tests/test_loss_guards_on_scheduler_trades.py::test_three_losing_scheduler_trades_lock_the_symbol`
- **Status:** GUARDED

### P63 The agent never saw any news: its readers looked for keys the news service does not send
- **Seen:** (first data-audit card, vinu-news, 2026-10-08) a real call to `/news/search` returns `{"count": n, "data": [...]}` with times in unix seconds. The memory sync (`sync_news`) and the trade plan's news section (`_fetch_news`) read `results` / `articles`, so both saw an empty list for every ticker: agent memory held no news and every trade plan said there was none. The plan's date cell sliced the time as text (`[:10]`), which would have crashed on the first real article.
- **Root cause:** the readers were written against a guessed shape, and their tests mocked a bare list, a shape the service never sends.
- **Fix:** `vinu-agent/vinu_agent/news_payload.py` is the one place that knows the shape (`news_articles`, `article_date`); `memory/sync_service.py` and `tools/trade_plan_tool.py` use it. The test now uses a real row's shape. Same readers, second fault found by the live check: they called `/news/search`, which ranks by text relevance, so the plan's News Context for AAPL showed 2023-2024 headlines. Both now call `/news/ticker/{symbol}` (newest first, 30 days).
- **Guard:** `vinu-agent/tests/test_news_payload_shape.py::test_trade_plan_news_section_sees_the_services_articles`, `vinu-agent/tests/test_news_payload_shape.py::test_memory_sync_stores_the_services_articles`, `vinu-agent/tests/test_news_payload_shape.py::test_trade_plan_asks_for_the_tickers_newest_news_not_a_relevance_search`
- **Must agree with:** the news routes' response model `DataResponse` in `vinu-news/vinu_news/server/schemas.py`; other readers of news (`vinu-initial-analysis/clients/news_client.py` already reads `data`).
- **Status:** GUARDED (the guard fails on the old code and passes on the new; checked on the host, then in the image after the rebuild)

### P64 Research reports said "Fix the error above" and did not contain the error
- **Seen:** (data audit, research, 2026-10-08) 24 of the 44 stored research reports ended with the suggestion "Fix the error above; the code must run on plain OHLCV data without exceptions" and no error. The cause (for example `name 'ta' is not defined`) sat in the critique's reasoning, and the report printed only the suggestions, collected in an unordered set.
- **Root cause:** `generate_report` in `vinu-research/vinu_research/report.py` used only `suggestions`.
- **Fix:** the report adds the critique reasoning when it carries the cause (strategy crash, static check failure) and keeps the findings in a stable order.
- **Guard:** `vinu-research/tests/test_report.py::TestCrashCauseReachesTheReport::test_the_crash_message_is_in_the_report`
- **Must agree with:** the critique texts in `vinu-research/vinu_research/loop.py` (`The strategy code crashed`, `Static AST Verification failed`).
- **Status:** GUARDED (fails on the old code, passes on the new)

### P65 Every audit entry claimed real trading and none carried the money mode
- **Seen:** (data audit, agent, 2026-10-08) all 1,289 entries of `trade_audit.log` had `paper_trading: false` while the stack trades on Alpaca paper; the file had no `account_mode` although every other money record does (P59).
- **Root cause:** `AuditLogger.log` defaulted `paper_trading` to False and no caller passed True.
- **Fix:** `vinu-agent/vinu_agent/broker/kill_switch.py`: each entry carries `account_mode` (from `VINU_ACCOUNT_MODE`; `unknown` if the setting is unreadable, the write still happens) and `paper_trading` follows it unless the caller states it.
- **Guard:** `vinu-agent/tests/test_audit_log_money_mode.py::test_a_paper_stack_writes_paper_entries`, `vinu-agent/tests/test_audit_log_money_mode.py::test_a_real_stack_writes_real_entries`
- **Must agree with:** `vinu-infra/account_mode.py`; the safety ledger tag (P59); readers of the audit log in reflection (none used the flag).
- **Status:** GUARDED

### P66 A news source failed on every poll and nobody was told or acted
- **Seen:** (data audit, news, 2026-10-08) the feed `ap_top_news` answered `http_403` on 252 of 252 polls. The failure was written to `feed_health` but nothing read it, nothing switched the feed off, and the provider side (Alpaca, FMP, Yahoo) recorded no health at all. The operator switches wrote into the packaged yaml, which is read-only in the container.
- **Root cause:** health was recorded for RSS feeds only, had no policy and no read-out, and the on/off flag lived in a file that cannot be written at run time.
- **Fix:** layer 1 of the news plan (`07-news-layers/plan.md`): `vinu-news/vinu_news/sources/health.py` records every poll of every source (feeds and providers) with an error kind, switches a source off after `VINU_NEWS_SOURCE_AUTO_OFF_AFTER` (10) errors in a row and retries after 1 h, 6 h, then 24 h, keeps the operator switch in the database, and reads all of it out at `GET /news/sources` (state in words, `attention` list); `PATCH /news/sources/{id}` is the switch. A quiet feed with no error is never switched off. The migration of the old table is safe when two threads start at once (it failed with `duplicate column name` on first start).
- **Guard:** `vinu-news/tests/test_source_health.py::test_a_source_that_keeps_failing_is_switched_off_and_the_reason_is_kept`, `vinu-news/tests/test_source_health.py::test_the_retry_window_grows_and_a_success_switches_the_source_back_on`, `vinu-news/tests/test_source_health.py::test_a_quiet_feed_with_no_error_is_never_switched_off`, `vinu-news/tests/test_source_health.py::test_providers_are_recorded_and_a_failing_one_is_skipped_once_switched_off`, `vinu-news/tests/test_source_health.py::test_two_connections_migrating_at_once_do_not_fail`
- **Must agree with:** `feeds.yaml` and `ticker_news.yaml` (the configured sources); the old toggles `PATCH /news/feeds/{id}` and `/providers/{id}` still write the yaml and cannot persist in the container (use `/news/sources/{id}`).
- **Status:** GUARDED (live: `GET /news/sources` shows `ap_top_news` switched off automatically after 264 errors in a row, blocked: http_403, next try in 1 h; news suite in the image 159 passed, 0 failures)

### P67 A re-served news item inflated the daily counts, and changed text on the same link was dropped
- **Seen:** (layer 2 of the news plan, 2026-10-08) when a source served an item again, the persist step skipped the row but still added one to its thread's daily snapshot and `ticker_daily_stats`, so those counts grew with every re-poll of an RSS feed. A headline or summary that changed on the same link was dropped without a trace.
- **Root cause:** `persist_leads` treated "link already stored" as a skip that still bumped the counters, and had no notion of the same item seen again or of a revision.
- **Fix:** `vinu-news/vinu_news/analysis/storage/dedup.py` (a fingerprint of the normalised headline and summary) and `persist.py`: an item with the same fingerprint only moves `last_seen_at` and `seen_count` (no counter bump); changed text is stored as a new row linked by `revision_of`, the old row gets `is_current = 0`, and every read serves current rows only. Columns `content_hash`, `first_seen_at`, `last_seen_at`, `seen_count`, `revision_of`, `is_current`; rows from before are back-filled in small steps. The search-index trigger now fires only when the text changes.
- **Guard:** `vinu-news/tests/analysis/test_layer2_dedup.py::test_the_same_item_again_only_moves_last_seen_and_the_count`, `vinu-news/tests/analysis/test_layer2_dedup.py::test_changed_text_becomes_a_linked_revision_with_its_own_first_seen`, `vinu-news/tests/analysis/test_layer2_dedup.py::test_a_summary_only_change_is_not_swallowed_by_an_id_collision`
- **Must agree with:** every query on `articles` (`is_current = 1`); `07-news-layers/plan.md`.
- **Status:** GUARDED (live: 357 items already seen again, highest seen count 5, 4 revisions stored; the daily counts that were inflated before are rebuilt by the layer-5 rebuild only for the new table, the old `ticker_daily_stats` stays as it was, see O33)

### P68 Later reports of a story were thrown away, so which sources told it and when was lost
- **Seen:** (layer 3, 2026-10-08) inside one poll the extra reports of a cluster were dropped before storing, and across polls a report matching an existing story was skipped. The audit read the one-article-per-cluster result as "clustering groups nothing"; that was wrong: the groups were formed and then discarded, so only the lead survived.
- **Fix:** `post_process.py` keeps the other cluster members (`duplicates`), `persist.py` stores them as raw rows under the lead's story (`is_lead = 0`), and a report joining an existing story is kept the same way. `story_threads` gains `sources_json`, `n_sources`, `first_source` (existing stories back-filled); a later report only adds its source and moves the end time. Reads serve one article per story with the tags `story_n_sources`, `story_sources`, `story_first_source`, `story_n_reports`. Layer 4 `story_facts` (primary ticker, other tickers, entities, key words, event tag, sentiment as a number with its method) is computed once per story; layer 5 `ticker_news` holds one row per (ticker, story); `GET /news/ticker-news/{symbol}` serves it (from, to, `as_of`, `known_by`, event tag, minimum sources). FinBERT, when models are on, replaces the story's number and says so. Existing stories are indexed once in the background (a marker elects one runner).
- **Guard:** `vinu-news/tests/analysis/test_layer3_stories.py::test_a_later_report_from_another_source_joins_the_story_and_is_kept_as_a_raw_row`, `vinu-news/tests/analysis/test_layer3_stories.py::test_two_sources_in_the_same_poll_become_one_story_and_both_are_kept`, `vinu-news/tests/analysis/test_layer45_facts_and_ticker_news.py::test_a_new_story_gets_facts_and_a_row_per_ticker`, `vinu-news/tests/analysis/test_layer45_facts_and_ticker_news.py::test_rebuild_recomputes_everything_from_the_raw_rows_and_runs_once`, `vinu-news/tests/analysis/test_layer45_facts_and_ticker_news.py::test_the_ticker_news_route_serves_the_table`
- **Must agree with:** the thread matcher thresholds in `analysis/config` (0.25 inside a poll, 0.30 across polls); the `is_lead` filter on every article read.
- **Status:** GUARDED (live: 7 multi-source stories already, for example CNBC then NIKKEI on the same story; indexing of the existing stories was at 23,003 of 55,175 when checked and still running)

### P69 A background worker that died at start-up stayed dead while its container reported healthy
- **Seen:** (2026-10-08, after the layer-2 deploy) the news ingest loop and the finbert worker both exited at start-up on `database is locked`; the container stayed healthy and nothing ingested for minutes. All 21 background workers in the 11 entrypoints were started as a bare `cmd &`.
- **Root cause:** nothing supervised them, and the hash back-fill held the write lock in one long statement. Separately the finbert worker crashed on every start because the models container is dormant.
- **Fix:** every entrypoint now starts workers through `supervise` (restart on a non-zero exit after 10 s, 20 s ... 5 min, count reset after 10 healthy minutes, a clean exit ends it); the back-fill runs in small committed steps; the finbert worker exits cleanly when `VINU_MODELS_ENABLED=false`.
- **Guard:** `vinu-infra/tests/test_stack_guards.py::test_no_entrypoint_starts_a_bare_background_worker`, `vinu-infra/tests/test_stack_guards.py::test_supervise_restarts_a_crashing_worker_and_stops_after_a_clean_exit`, `vinu-news/tests/test_finbert_worker_dormant.py::test_the_worker_exits_cleanly_when_models_are_disabled`
- **Status:** GUARDED (live: after the final deploy the only supervisor line is the finbert worker finishing cleanly; no other worker has exited)

### P70 Chain C1: the analysis saw "no news effect" for symbols that have thousands of articles
- **Seen:** (data audit) the news-price result of 12% of symbols had been replaced by an empty placeholder; the strategy and research read zeros. Causes: the news read attached a price reaction by reading candles per page (137.7 s for AAPL's 7,941 articles, and a failure part-way); initial-analysis saved a failed news fetch as a completed empty run; and the newest run always wins, even when it is only a placeholder.
- **Fix:** the price reaction is opt-in (`?reaction=true`; nothing read it, the news-price angle computes its own); the runner raises (an error run, retried later) when the news fetch failed for an angle that declares `uses_news` (shock_personality, drawdown_deep_dive, news_price_causality, signal_evidence); a placeholder row never replaces a stored result that has real rows.
- **Guard:** `vinu-news/tests/test_news_read_has_no_price_dependency.py::test_the_default_read_never_touches_the_price_service`, `vinu-initial-analysis/tests/test_runner_fetch_failures.py::test_a_failed_news_fetch_is_an_error_run_for_an_angle_that_reads_news_and_a_good_one_is_completed`, `vinu-initial-analysis/tests/test_runner_fetch_failures.py::test_a_placeholder_never_replaces_a_stored_result_that_has_real_rows`
- **Status:** GUARDED (live: AAPL's multi-year read 137.7 s before, 44.0 s now while the background indexing was running; the 36 shadowed results are fixed by re-running those angles, which has not been done yet, see O33)

### P71 One shared news database: bulk prefill and live writes fought for one lock, and every migration took the whole store down
- **Seen:** (2026-10-08) `database is locked` at start-up killed the ingest loop; a one-time migration of 55,174 stories took about ten minutes on this disk and kept the news server unanswering and the container unhealthy; removing or refilling one ticker meant deleting rows out of a shared pile.
- **Root cause:** every ticker, every layer and all configuration lived in one SQLite file.
- **Fix:** the per-ticker layout (user decision, 2026-10-08): `vinu-news/vinu_news/storage/ticker_stores.py` gives each ticker its own database `data/news/tickers/<SYMBOL>.db` holding every layer (items, stories, facts, the ticker table); a story about two tickers is stored in both with the same article id (accepted duplication). Alpaca is the only source (22 RSS feeds switched off through the operator switch, FMP and Yahoo off in the configuration). A new central database `news_central.db` holds settings, the watchlist, backfill state and source health, seeded once from the old shared file (every ticker's backfill reset to pending; the old `vinu_news.db` is left untouched as the archive). Reads for one ticker use its file; reads across tickers merge the files without repeats; `GET /news/tickers` lists each ticker's dataset with its backfill state and `DELETE /news/tickers/{symbol}` drops one and marks its backfill pending. The 63,000-row ticker reference list is seeded once, in the central database only. `VINU_NEWS_LAYOUT=single` keeps the old one-file behaviour.
- **Guard:** `vinu-news/tests/test_per_ticker_layout.py::test_ingest_writes_each_ticker_into_its_own_file_with_the_same_article_id`, `vinu-news/tests/test_per_ticker_layout.py::test_a_long_write_on_one_ticker_does_not_block_another`, `vinu-news/tests/test_per_ticker_layout.py::test_the_listing_shows_each_ticker_and_dropping_one_leaves_the_others`, `vinu-news/tests/test_per_ticker_layout.py::test_a_fresh_start_carries_the_configuration_and_leaves_the_news_behind`, `vinu-news/tests/test_per_ticker_layout.py::test_a_ticker_symbol_cannot_escape_the_folder`
- **Must agree with:** every read that crosses tickers (latest, search, high-impact, active threads, watchlist news) merges all files; a thread id is only unique inside one ticker's file.
- **Status:** GUARDED (live: fresh start seeded 50 tickers and 13 settings, the 22 source switches carried over, 24 ticker files existed within a minute of start, AAPL backfill running)

### P72 The analysis read the live news store directly, so its input could change under it
- **Seen:** (design, 2026-10-08) news angles fetched their range from the live store on every run (16 pages for AAPL, minutes long); a revision, a re-index, a migration or an outage part-way changed or broke the input, and the result then replaced the previous one.
- **Fix:** `vinu-initial-analysis/vinu_initial_analysis/clients/news_snapshot.py`: `SnapshotNewsClient` wraps the news client with the same `get_ticker_news`, so the runner and every angle are unchanged. A range is read once and kept as `news_inputs/<SYMBOL>/<from>_<to>.parquet` with a manifest (built at, rows, data_through, schema version); a range that ended more than a day before it was built is final and reused, a range that reaches the present is rebuilt after an hour, an empty answer is never kept, and a failed read of a range without a copy still raises. `GET /analysis/news-inputs` lists the copies and `DELETE /analysis/news-inputs/{symbol}` removes one ticker's copies (always safe).
- **Guard:** `vinu-initial-analysis/tests/test_news_snapshot.py::test_a_closed_range_is_read_once_and_then_served_from_the_copy`, `vinu-initial-analysis/tests/test_news_snapshot.py::test_the_copy_has_the_same_rows_and_columns_with_plain_python_values`, `vinu-initial-analysis/tests/test_news_snapshot.py::test_a_live_outage_cannot_change_an_analysis_that_has_its_copy`, `vinu-initial-analysis/tests/test_news_snapshot.py::test_an_empty_answer_is_never_kept`
- **Status:** GUARDED (the copies fill as the analysis runs; none exist yet on the fresh stack)

---

## E. Open problems (found, not fixed)

| # | Problem | Why it matters | Next step |
|---|---|---|---|
| O1 | CLOSED. Fixed: P38. | | |
| O2 | CLOSED. Fixed: P37 (the switches did nothing). | | |
| O3 | Fixed as far as the evidence goes (P45): costs scale by session from a base taken from published spread figures. Thin stocks overnight are still flattered (they can cost 10 to 20 times regular, the base is 3) | overnight results for thin names | per-name liquidity scaling, or restrict overnight trading to liquid names |
| O4 | No alert channel configured (Telegram or Discord) | at night a halt reaches nobody | set one, with quiet hours |
| O5 | CLOSED. Fixed: P33 (not yet seen on a real fill). | | |
| O6 | DECIDED, not built: the allocator does not carry approved sessions or size multipliers; the order guard stays the single place that enforces them (two places would drift apart) | a strategy approved only for the regular session still gets capital allocated overnight, which sits idle | revisit only if idle overnight capital turns out to matter |
| O7 | Fixed: P41 stops deploys from killing runs, P43 carries a killed run's finished work into the next run. A run killed mid-conversation still loses that conversation (the model is re-briefed, not resumed) | | |
| O8 | Gatekeeper, allocator and live feedback never run on a real strategy | still synthetic only | needs the first real ACTIVE strategy |
| O9 | CLOSED. Fixed: P34 (not yet seen on a real night exit). | | |
| O10 | Base set from published figures (2026-10-08, `session-cost-evidence.md`): pre-market 5, after-hours 7, overnight 3. Our own recorder keeps collecting (P46) but its feed is IEX-only and reads too wide, so it can only refine the ratios | the base is rough: one study per session, none direct for pre-market | after a few days, compare `/stock/spread-stats` ratios with the base; do not use its absolute level |
| O11 | CLOSED. Already fixed earlier: `vinu-reflection/entrypoint.sh` runs the API and the worker; checked live on 2026-10-07 (the agent reads `/reflection/synthesis/latest` and `/reflection/beliefs/notable`). Guard: `vinu-infra/tests/test_stack_guards.py::test_the_reflection_container_serves_its_api_as_well_as_running_the_worker`. | | |
| O12 | CLOSED. Fixed: P35. | | |
| O13 | CLOSED. Fixed: P36 (thresholds are guessed). | | |
| O14 | CLOSED. Fixed: P42 (news client) and P49 (the tests were using the live stack through a fallback address). | | |
| O15 | Reflection worker, what remains: four analysts wait for files their producers write only on an event: `injected_context_log.db` (agent, when context is injected), `rebalance_requests.db` (live, on a rebalance request), `paper_performance.db` (shadow evaluator, on paper trades), `market_regime_history.db` (research, when a trade plan is analysed). The flag-store failure (P31), the missing health check (P40) and `screener_agreement` (P48, it works and reports) are fixed. Reading another service's WAL database on a read-only mount still fails when the owner has the file closed | four of six analysts are silent until the system trades | nothing to build: they start by themselves when the first paper trades happen; check `docker compose logs reflection-worker` after the first one |
| O16 | Partly fixed (P32). The backlog came from a 76-minute stall of the host model server, not from ordering. Still open: the cause of the stall (host side, unknown); a stall still costs 300 s per call, so a quick probe-and-pause would be better; the planner still queues summaries (5 waiting, 4 with 1,300 s or more) while the model is stalled | a stall wastes research runs; nothing tells the user it happened (see O4) | find why the model server stopped answering (its log on the host); add a cheap probe before each call, and an alert (O4) |
| O17 | Fixed as far as it can be: P41 and P43 (see O7) | | |
| O18 | CLOSED. Fixed: P39. | | |
| O19 | Recovery is automatic now (P44). Still open: why the model freezes (a 2,810-token prompt with thinking on; try capping thinking or `max_tokens`), and the task only exists on this PC | a freeze still costs up to 5 minutes plus the restart | find the cause in the model server's own log; reinstall the task on a new machine |
| O20 | CLOSED. Fixed: P53 (no capital to unvalidated YAML strategies) and P58 (the allocator's dollars now size the daily allocation). | | |
| O21 | CLOSED. The diagram was wrong, not the code: refusals go to the trade audit log (every order and refusal); the safety ledger is the hash-chained record of kill-switch halts and resumes, now tagged with the money mode. Diagram D5 and the audit row A15 corrected. | | |
| O22 | CLOSED. Fixed: P54 (long-only mandate), P55 (scheduler keeps its own positions) and P60 (the book follows the broker). Shorts remain a later feature. | | |
| O23 | Capital allocator, what is rough or missing: (1) the win/loss inputs are each strategy's daily simulator returns, not real trades; (2) Kelly fraction 0.25, reserve 0.4, position cap 0.25 are proposed defaults, not decisions; (3) no strategy has return history yet, so a funded plan has never been seen live; (4) whole shares only, so most stocks cost more than the free cash of 12 dollars; (5) reflection and research statistics are not split by money mode; (6) the old `VINU_PORTFOLIO_RESERVE_FRACTION` is not used while a capital base is set; (7) `manager_prompt.md` of the allocator team still shows 100000 in its example | a 20-dollar account may be unable to buy anything | decide the settings with the user; try fractional shares in regular hours only; split reflection results by mode |
| O24 | Data audit, news, what is left (the rest is fixed: P63, P66, P67, P68, P70): `finbert` stays empty while the models container is dormant (by design); `avg_impact` in the news-price angle reads a field the service does not send and nothing uses it; no consumer reads `ticker_daily_stats`, the thread routes or the new `ticker-news` table yet; news still does not reach allocation, the live scheduler or the guards (question for the user). Correction to the audit: live ingest is mixed-source (Benzinga 194, Investing.com 65, Seeking Alpha 54, CNBC 34, Bloomberg 20 in three days); 99.6% Benzinga came from the 2023 backfill | news is stored well but still little used for decisions | switch initial-analysis to the ticker-news table; decide where news may act |
| O25 | Data audit, stock-price (`06-data-audit/findings.md` DA-S1..S7): 542,317 gaps counted and nobody decides from them; `has_adj_data` stale; `ingest_log` grows 72,000 rows a day with no pruning; spread snapshots have no reader; outside regular hours the quote has no valid ask, the live spread guard fails open and the after-hours/overnight statistics are one stale quote; macro events are pulled but 0 are stored (no Finnhub key); one data provider only | no spread protection in the extended sessions that 24-hour trading depends on | choose a source of extended-hours quotes or a rule without one; decide on a macro calendar key; prune logs |
| O26 | Data audit, screener (DA-R1..R5): the ranking was saved from 20 of 50 symbols after two candle chunks timed out, with no mark; only the latest snapshot is kept; no rules exist; the ranking does not reach sizing or entry (research tilt off, planner reads symbols only, 18 of the 20 'top' names scored negative); stock-api exited once during my timing test (cause unknown) | planner can plan from a partial or negative ranking | mark/refuse partial runs, keep history, decide whether the score should matter |
| O27 | Data audit, initial-analysis (DA-I1..I7): `peer_relative_strength` is 72% of the store, 83 s a run, named only in the agent; seven angles are not used by research, live or portfolio; the batch tracker table is absent and two empty stray databases exist; old runs are never deleted; the newest windows end 2026-10-01 | cost without a reader; stale analysis | decide which angles feed decisions, retention, refresh schedule |
| O28 | Data audit, research (DA-X2..X8): 55% of candidate strategies crash on run, the rest fail the significance tests (block-bootstrap 19, BCa 17, bootstrap interval 17, placebo 17, price-path 11, trade-permutation 11, walk-forward 9 of 44 runs), none passed; 59% of sweep points fail on recipe names the registry does not know; three tables that should have rows are empty; the signal evidence has one condition; five hypotheses are 'validated' with no passing strategy | nothing reaches ACTIVE | feeds the strategy-pass step; one shared recipe list |
| O29 | Data audit, simulator and strategy, plus chains C1-C4: 99.7% of simulator runs allowed shorting against a long-only mandate; the news-price result of 12% of symbols was replaced by an empty placeholder after a failed news fetch (bulk news read takes minutes because every page pulls candle data); YAML strategies never evaluated | validation judges a payoff live cannot take; the news-aware strategy reads zeros | C1 fixed (P70); C2 (long-only validation), C3 (partial ranking) and C4 (sweep recipe names) remain |
| O30 | Data audit, portfolio (DA-P1..P4): allocation history unread and mixed bases; no account equity or cash time series is stored anywhere | no record to review drawdown or live-versus-simulated performance | build an equity snapshot table in live (tagged paper/real) |
| O31 | Data audit, live (DA-L1..L5): a trade leaves four records that do not join (book, order log, journal, audit log); a position closed outside the scheduler is booked at its entry price with zero pnl although the audit log has the real exit fill; read routes with no outside caller; legacy day-start equity file | the allocator's win/loss statistics miss real exits | one trade ledger with a trade id; sync reads the exit fill |
| O32 | Data audit, agent (DA-A1..A5): the memory sync is never called so the memory is empty; 56% of team runs fail and lose their cause; the model-call log grows 90 MB a day; 98% of the audit log is the fact-checker; an empty duplicate telemetry database | agent memory tool searches nothing | decide on memory sync; store failure causes; retention |
| O33 | News follow-ups after the fresh start: (1) the per-ticker backfill of all 50 tickers from 2023-01-01 is running (one ticker at a time) and must finish before the news angles are re-run; (2) the news-based angle results in initial-analysis (news-price causality, shock personality, drawdown, signal evidence) were computed from the old shared store and stay until re-run: decide whether to clear them; (3) `ticker_daily_stats` and `thread_daily_snapshots` of the new files start clean (the inflated old counts stay in the archive only); (4) per-ticker onboarding state (pending, backfilling, complete, analysed) is shown by `GET /news/tickers` but nothing gates the planner or live on it yet; (5) the universe must be point-in-time (record when each ticker joined) to avoid selection bias; (6) the old `ticker_news`-table based read for initial-analysis is not used yet (it still reads `/news/ticker/{symbol}` through the snapshot) | analysis on stale or half-filled news | wait for the backfill, then re-run the news angles; add the onboarding gate |
