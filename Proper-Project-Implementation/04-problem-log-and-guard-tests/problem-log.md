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

---

## E. Open problems (found, not fixed)

| # | Problem | Why it matters | Next step |
|---|---|---|---|
| O1 | CLOSED. Fixed: P38. | | |
| O2 | CLOSED. Fixed: P37 (the switches did nothing). | | |
| O3 | Reworded after reading the code: backtest costs are not zero. Every trade pays `VINU_SIMULATOR_TRANSACTION_COST_PCT` plus `VINU_SIMULATOR_SLIPPAGE_PCT` (0.0005) per side, and `VINU_SIM_SPREAD_BPS=0` is only the extra quote spread on top. What is missing is that the cost is the same in every session | overnight and pre-market trades are probably cheaper in the backtest than in life, so session approval is flattered | measure quote spreads per session (O10), then give the cost model the bar time |
| O4 | No alert channel configured (Telegram or Discord) | at night a halt reaches nobody | set one, with quiet hours |
| O5 | CLOSED. Fixed: P33 (not yet seen on a real fill). | | |
| O6 | DECIDED, not built: the allocator does not carry approved sessions or size multipliers; the order guard stays the single place that enforces them (two places would drift apart) | a strategy approved only for the regular session still gets capital allocated overnight, which sits idle | revisit only if idle overnight capital turns out to matter |
| O7 | Partly fixed (P41): deploys no longer kill a run in flight. A crash or restart outside a deploy still does | work lost | make runs resumable: save progress after each strategy attempt and continue from it after a restart (a design decision; bring options) |
| O8 | Gatekeeper, allocator and live feedback never run on a real strategy | still synthetic only | needs the first real ACTIVE strategy |
| O9 | CLOSED. Fixed: P34 (not yet seen on a real night exit). | | |
| O10 | Per-session spread and liquidity not measured | risk hint uses return volatility only | quote-based spread per session |
| O11 | CLOSED. Already fixed earlier: `vinu-reflection/entrypoint.sh` runs the API and the worker; checked live on 2026-10-07 (the agent reads `/reflection/synthesis/latest` and `/reflection/beliefs/notable`). Guard: `vinu-infra/tests/test_stack_guards.py::test_the_reflection_container_serves_its_api_as_well_as_running_the_worker`. | | |
| O12 | CLOSED. Fixed: P35. | | |
| O13 | CLOSED. Fixed: P36 (thresholds are guessed). | | |
| O14 | The initial-analysis tests are not hermetic. In the container harness the full suite never finishes: `test_pnl_attribution.py::test_run_with_angle_names_does_not_error` waits on a news fetch to a service that is not there, and `test_arima_backtest.py` parallel-fit tests take many minutes. With every service URL set to a refusing port, everything except the arima backtest file ran in 103 s (378 passed, 1 failed: `test_api_v1.py::test_trigger_and_poll_flow`, which needs the default URLs and passes under them) | the suite cannot be run as one command, so regressions in this package can hide | make the tests fake the news and bar clients (or set refusing URLs only where the test does not need them), and time-box the arima parallel tests |
| O15 | Reflection worker: 5 of its 6 analysts still skip each cycle. One was a real bug (P31, fixed). The other five wait on files that their producers write only when an event happens, and nothing has happened yet: `injected_context_log.db` (agent, when context is injected), `rebalance_requests.db` (live, on a rebalance request), `paper_performance.db` (shadow evaluator, on paper trades), `market_regime_history.db` (research, when a trade plan is analysed). `screener_agreement` reads the screener's rule-fire audit, which fills only when a screener RULE fires; this system uses rankers, so it may stay inert for good. The missing health check is fixed (P40). A reflection reader on a read-only mount also cannot open a WAL database whose owner has it closed (seen on research telemetry, llm_cache, signal_evidence, sweep_grid) | the learning loop has little to learn from until trades exist; cross-container SQLite reads are fragile | after the first paper trades, confirm the four files appear and the analysts run; decide whether screener_agreement is worth keeping; add a health check to the reflection worker; longer term, give reflection a read path that does not depend on the owner having the file open |
| O16 | Partly fixed (P32). The backlog came from a 76-minute stall of the host model server, not from ordering. Still open: the cause of the stall (host side, unknown); a stall still costs 300 s per call, so a quick probe-and-pause would be better; the planner still queues summaries (5 waiting, 4 with 1,300 s or more) while the model is stalled | a stall wastes research runs; nothing tells the user it happened (see O4) | find why the model server stopped answering (its log on the host); add a cheap probe before each call, and an alert (O4) |
| O17 | Cause proven and the self-inflicted part stopped (P41). See O7 for the rest | | |
| O18 | CLOSED. Fixed: P39. | | |
