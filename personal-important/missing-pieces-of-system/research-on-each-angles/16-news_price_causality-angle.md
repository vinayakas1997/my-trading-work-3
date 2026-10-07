# 16 — news_price_causality

- **Angle id:** `news_price_causality`
- **Cluster:** D — News & event-driven
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/`
  (`compute.py`, `granger.py`, `correlation.py`, `impact.py`, `novelty.py`,
  `significance_model.py`, `regime_features.py`, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Tests whether news actually causes this ticker's price moves rather than
just correlating with them (Granger causality), plus a per-article event
study (price change and abnormal return in the minutes/hours after each
article), a novelty score, and a pre-event significance classifier. **The
reported Granger `p_value` and lag-analysis `best_lag_minutes` are each
the best of several tested lags with no multiple-comparison correction**
(see F1/F2) -- treat both as more optimistic than a single, pre-specified
test would be.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Granger causality tests whether past values of one series improve prediction of another beyond that series' own past, via an F-test on a VAR model's lagged coefficients. | [N1] |
| A2 | Testing several candidate lag lengths and reporting the one with the smallest p-value is a recognized, real methodology ("Granger Minimum p-value") -- but doing so without correcting the significance threshold inflates the false-positive rate. | [N2] |
| A3 | For daily-return event studies, a market-model abnormal return (regressed against a market index) is well-specified and reasonably powerful; simpler methods (e.g. mean-adjusted) also perform adequately in many cases. | [N3] |
| A4 | Shuffled/random train-test splits leak future information into a time-series model; only a **chronological** split gives an honest held-out evaluation. | code's own docstring (`significance_model.py`) |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Granger causality tests, VAR lag length chosen by information criteria or by scanning several lags | Test statistics are "very sensitive to the lag length chosen"; "overfitted VAR models also tend to lead to over-rejection of the null hypothesis of Granger non-causality" -- i.e. false "yes, it's causal" findings become more likely, not less, when more lags are tried. | [N2] |
| R2 | Reporting the minimum p-value across several tested lags ("p-hacking based on selection over various VAR models with different lag lengths") | Identified in the literature as a real, documented source of false-positive Granger causality findings in published research. | [N2] |
| R3 | Market-model vs. mean-adjusted abnormal returns, daily stock data, simulated event studies | "A simple methodology based on the market model is both well-specified and relatively powerful under a wide variety of conditions, and in special cases even simpler methods also perform well." | [N3] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `run_granger_causality_test` runs the test at **every lag from 1 to 12**, takes the **minimum** p-value across all 12, and reports `granger_causes_prices = best_p < 0.05` -- an unadjusted 0.05 threshold applied to a value selected as the smallest of 12 tests. | This is close to a textbook description of the exact practice the literature calls out: testing multiple lag lengths and selecting the most significant one inflates the false-positive rate above the nominal 5% [N2]. | **Real, confirmed methodological bug.** The reported `p_value` is not a valid p-value for the stated 0.05 decision rule -- it needs a correction (e.g. Bonferroni: compare to 0.05/12 ≈ 0.0042) or a pre-specified single lag chosen on other grounds (e.g. AIC/BIC on the VAR, not on the causality test's own p-value). As written, `granger_causes_prices: True` is easier to trigger by chance than the glossary's framing ("a low granger_causality_p_value means real statistical evidence") implies. |
| F2 | `compute_lag_analysis` runs Pearson correlation at 5 candidate lags (0/15/30/60/120 min) and reports whichever has the **largest absolute correlation** as `best_lag_minutes`/`best_lag_correlation`, with no correction and no significance test on the winning lag at all. | Same underlying statistical issue as F1, applied to correlation instead of Granger F-tests -- selecting the best of several tried comparisons and reporting it without accounting for the search. | **Same class of bug, second instance in the same angle.** Unlike the Granger row, this one doesn't even carry a p-value to (mis)compare against a threshold -- `best_lag_correlation` is reported as a plain number, so a reader has no way to tell "found by chance among 5 tries" from "genuinely the best lag." |
| F3 | `resample_news_to_hourly`/`impact.py` use the **real** news schema (`tickers`, `sort_ts`, `sentiment`) throughout. | -- | **Correct**, and a useful contrast: [05-drawdown_deep_dive-angle.md](05-drawdown_deep_dive-angle.md) found a different angle's news-attribution code using the wrong field names (`symbol`/`ts`/`price_change_30m`) that never matched anything live. This angle gets the same integration right, confirming the schema mismatch there was isolated to that one module, not a codebase-wide problem. |
| F4 | Abnormal returns are computed against SPY via a market-model-style regression, falling back to a mean-adjusted model if SPY is unavailable, with the choice recorded in `ar_model` so a reader can tell which was used. | Market-model abnormal returns are well-specified and reasonably powerful for daily event studies; simpler (mean-adjusted) methods also perform adequately in many cases [N3]. | **Sound design**, grounded in the actual event-study literature, and the code is explicit (not silent) about which model produced a given row -- avoids the same "success" ambiguity flagged in other angles' fallback-labeling. |
| F5 | `correlation.py`'s comment documents that its bootstrap confidence interval was previously broken (`scipy.stats.bootstrap` decorrelating x from y per resample, collapsing the CI to a degenerate `[-1, 1]`) and has since been fixed by reusing an already-tested shared helper (`pearson_with_ci`). | -- (internal history, code-only) | **A previously-caught bug, already fixed** -- shows this codebase does catch and correct real statistical bugs in this exact area, which makes the still-unfixed Granger/lag multiple-comparisons issue (F1/F2) more a gap than a pattern of neglect. |
| F6 | `significance_model.py`'s docstring documents catching and removing a genuine label leak (an earlier version trained on `impact_label`/`price_change_*`, which are derived from the same post-event window as the target, and reported a "7-8x lift" before the leak was removed) and reports, as a **negative result**, that neither rule-based sentiment nor FinBERT scores predict the *direction* of a significant price reaction above chance (~50% sign-agreement, all correlations p > 0.1). | -- (internal methodology, code-only) | **Exemplary self-correction and honest reporting** -- a leakage bug caught before shipping, and a negative result reported as a negative result rather than omitted. This is the most methodologically self-aware angle researched so far. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

This angle writes several row **types**, distinguished by `type`:

**`type: "impact"`** -- one row per (article, affected ticker) pair, only computed under the `1min` pass:

| Field | Meaning |
|---|---|
| `article_id`, `headline`, `sentiment`, `sentiment_score` | Article identification/content. |
| `is_primary` | Whether this ticker was the article's primary subject vs. a secondary mention. |
| `session` | Market session the article landed in. |
| `price_change_5m/15m/30m/1h/1d` | Simple price change over each post-article window. |
| `abnormal_return_30m`, `car_1h` | Return over and above the modeled expectation (see `ar_model`). |
| `ar_p_value`, `ar_significant` | Statistical significance of the abnormal return. |
| `ar_model` | `"market"` (SPY-regressed), `"mean_adjusted"` (fallback), or `"none"` (not enough data) -- see F4. |
| `impact_label` | Coarse label combining sentiment and 30m price change. |
| `novelty_score` | 1.0 = nothing similar published recently for this ticker; near 0 = rehash. |
| `significance_score`, `significance_score_sample` | Pre-event predicted probability the move will be significant, plus `"train"`/`"test"` -- see F6, only trust `"test"` rows. |

**`type: "significance_model_eval"`** -- one row, model quality summary (chronological holdout metrics).

**`type: "granger"`** -- one row: `granger_causes_prices`, `best_lag_minutes`, `p_value`, `sample_size` -- **see F1**.

**`type: "correlation"`** -- one row: `news_return_corr`, `corr_p_value`, `sentiment_return_corr`, `news_volume_corr`, `sample_size`.

**`type: "lag"`** -- one row: `best_lag_minutes`, `best_lag_correlation` -- **see F2**.

**`type: "status"`** -- fallback row when no articles or no candles are available.

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

This angle has **no `status` field on success rows** -- success is indicated
by which `type` rows are present. Only the no-data fallback row carries
`type: "status"` with `granger_causes_prices: False`, `news_return_corr: 0.0`,
`best_lag_minutes: 0`, `event_count: 0`.

## 7. Comprehensive explanation  *(for humans only)*

**What Granger causality actually tests.** Not "does A cause B" in a
deep sense -- it tests whether adding B's own past values to a model
that already uses A's past values improves prediction of A, via an
F-test on the added lagged coefficients [N1]. The choice of how many
lags to include is not a free technical detail; it changes the test's
outcome, and both over- and under-fitting the lag length distort results
[N2].

**Why testing 12 lags and keeping the best is the specific trap the
literature warns about (F1).** Bruns & Stern's simulation study of
exactly this practice found that scanning multiple lag lengths and
reporting the most significant one -- what they term part of "p-hacking"
in Granger causality testing -- causes real, quantifiable over-rejection
of the null hypothesis: false "causality found" results become more
common than the nominal significance level implies [N2]. Our code's
`run_granger_causality_test` does precisely this: 12 separate F-tests,
minimum p-value kept, compared against the unadjusted 0.05 threshold
used for a single test. `compute_lag_analysis` (F2) repeats the same
shape with correlations instead of F-tests, and without even a p-value
to check.

**Why this matters downstream.** The glossary tells the LLM "a low
`granger_causality_p_value` means real statistical evidence, not just
'news and price both moved.'" Given F1, that's currently not quite
accurate -- the reported value is systematically more likely to look
significant than a single honest test would be, exactly the opposite of
the confidence the glossary attributes to it. This doesn't mean the
angle finds *no* real signal, only that its stated 0.05 cutoff doesn't
mean what a single-lag 0.05 cutoff would mean.

**What this angle gets right.** The event-study machinery (`impact.py`)
is grounded correctly in the literature -- market-model abnormal returns
with an honest fallback label, the right news-article schema throughout
(unlike a different angle's real bug found earlier in this research),
and a bootstrap-CI bug already caught and fixed in `correlation.py`. The
significance classifier (`significance_model.py`) is the most
methodologically careful piece of code researched in this whole folder
so far: it documents catching its own label leak before shipping, uses
a chronological (not random) train/test split specifically because
shuffling time series leaks the future, and reports a negative result
(neither sentiment scoring method predicts reaction *direction*) rather
than hiding it. The multiple-comparisons issue in Granger/lag selection
is a real gap, but it sits inside an otherwise unusually self-critical
module.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| N1 | statsmodels documentation, `statsmodels.tsa.stattools.grangercausalitytests` | Null hypothesis definition (does the second series' past improve prediction of the first, beyond the first's own past); the four test statistics returned (`ssr_ftest` matches R's `lmtest::grangertest`); confirmed no built-in warning about testing multiple lags. | https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html |
| N2 | Bruns & Stern, "Lag length selection and p-hacking in Granger causality testing: prevalence and performance of meta-regression models," *Empirical Economics*, 2019 (open-access ANU repository copy, pp. 1-4) | Granger test sensitivity to lag length; "p-hacking can... be based on selection over various VAR models with different lag lengths"; overfitted lag lengths cause over-rejection of the null (more false "causal" findings); this is prevalent in real published research using this exact selection practice. | https://openresearch-repository.anu.edu.au/bitstream/1885/204050/6/Lag%20length%20selection.pdf |
| N3 | Brown & Warner, "Using Daily Stock Returns: The Case of Event Studies," *Journal of Financial Economics* 14(1), 1985, pp. 3-5 | Market-model abnormal returns are well-specified and relatively powerful for daily event studies; simpler methods (e.g. mean-adjusted) also perform adequately in special cases -- grounding for this angle's market-model-with-fallback design (F4). | https://leeds-faculty.colorado.edu/bhagat/brownwarner1985.pdf |
