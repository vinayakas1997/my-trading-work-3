# 02 — backtesting_44_metrics

- **Angle id:** `backtesting_44_metrics`
- **Cluster:** G — Validation & attribution
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/`
  (`compute.py`, `backtest.py`, `spec.yaml`); annualization in `angles/_helpers.py`
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A scorecard of how the ticker's own price has behaved in the past, as if
you had simply bought and held it: return, volatility, drawdown, and how
bad the worst days were. It measures the **stock itself, not any
strategy**, and it is backward-looking only -- it says nothing about
what happens next.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Annualizing by √(periods per year) assumes returns have **zero serial correlation**. | [S1], [S2] |
| A2 | A Sharpe-style ratio measures reward per unit of risk **relative to a risk-free benchmark**. | [S1] |
| A3 | Past-window statistics are **estimates with real error**; few observations means unreliable numbers. | [S2] |
| A4 | Standard deviation treats upside and downside moves as equally "risky"; downside measures (Sortino) exist because that's often not what investors mean by risk. | [S3] |
| A5 | Tail metrics (VaR, CVaR) are read from the **actual historical returns** (percentiles), not from a normal-distribution assumption. | code, see F-notes |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Annualizing monthly Sharpe by √12 | Valid "except under very special circumstances" only; serial correlation overstated one hedge fund's annual Sharpe by **up to 65%**. | [S2] |
| R2 | Downside deviation computed as the standard deviation of only the negative returns | **Wrong method** -- it drops the periods that met the target instead of counting them as zero shortfall. Correct: root-mean-square of shortfalls below target, over all observations. | [S3] |
| R3 | Intraday returns, Dow 30 stocks, Oct 2018-Mar 2019 | Heavy tails held: **kurtosis from 10 to over 1,000**, shrinking as the timescale lengthens; volatility clustering held; absence of return autocorrelation held. | [S5] |
| R4 | Same data, gain/loss asymmetry | **Not found** -- large drops were not more frequent than large rises in that sample. | [S5] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `sharpe_ratio` = CAGR ÷ annualized volatility, **no risk-free rate**. | Sharpe: average **excess return over a riskless benchmark** ÷ its standard deviation [S1]. | **Not the standard Sharpe ratio.** Two differences: geometric CAGR instead of the average return, and no risk-free subtraction. With a nonzero risk-free rate, this overstates the ratio. Label it "return/volatility ratio" or fix the formula. |
| F2 | `sortino_ratio` uses `rets[rets < 0].std()`. | That is exactly the documented incorrect method [S3]. | **Miscalculated.** A ticker falling the same amount every bar would get a downside deviation of zero -- "risk-free." |
| F3 | Annualizes with √(periods per year) on every timeframe. | Needs zero serial correlation [S1]; can overstate badly when it's present [S2]. For liquid large caps at intraday scale, absence of autocorrelation did hold [S5]. | Reasonable for liquid names, not guaranteed for every ticker. |
| F4 | Intraday periods-per-year assume a 390-minute regular session (`_helpers.PERIODS_PER_YEAR`). | -- (code-internal) | **Unverified risk:** elsewhere the codebase tags bars in `ny_premarket` / `ny_afterhours` sessions (`storage/factsheet.py`). If those bars are included here, intraday annualized figures are mis-scaled. Needs a check against real stored bars. |
| F5 | `compute.py` accepts as few as **5** returns; `backtest.py` requires **100**. | Sharpe ratios carry real estimation error [S2]. | Five returns can't produce a meaningful Sharpe, Sortino or VaR. The two files disagree; `compute.py`'s threshold is the one out of line. |
| F6 | Name and glossary say "44+ metrics." | -- | It computes **18**. |
| F7 | A successful row has **no `status` field** at all. | -- | Unlike other angles, consumers can't check `status == "ok"` here; success means "no status key." |
| F8 | Glossary says it shows how "a strategy/symbol" performed. | -- | It only ever measures the ticker's own buy-and-hold returns. `win_rate` is the share of **up bars**, not winning trades. |
| F9 | `kurtosis` from pandas. | pandas returns **excess** kurtosis (normal = 0), unbiased [S4]. | Correct, but must be read as excess: >0 means fatter tails than normal. Very large values at 1min are expected [S5]. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

All returns are simple per-bar returns (`pct_change` of close) for the
requested timeframe. Fractions, not percent (0.05 = 5%).

**Core metrics** (also recomputed on a rolling 100-bar window by `backtest.py`):

| Field | Meaning |
|---|---|
| `total_return` | Compound return over the whole window. |
| `cagr` | `total_return` converted to an annual rate. |
| `ann_vol` | Standard deviation of bar returns × √(periods per year). |
| `sharpe_ratio` | `cagr ÷ ann_vol`. **Not the textbook Sharpe** -- see F1. |
| `sortino_ratio` | `cagr ÷ annualized std of negative returns`. **Miscalculated** -- see F2. |
| `max_drawdown` | Worst peak-to-trough fall of the compounded price path (negative, e.g. -0.35). |
| `calmar_ratio` | `cagr ÷ |max_drawdown|`. |
| `win_rate` | Share of bars with a positive return. **Not trades.** |
| `avg_win` / `avg_loss` | Mean return of up bars / of down bars (`avg_loss` is negative). |
| `win_loss_ratio` | `|avg_win ÷ avg_loss|`; `null` if there were no down bars. |
| `profit_factor` | Sum of up-bar returns ÷ |sum of down-bar returns|; `null` if no down bars. |

**Whole-history tail metrics** (always computed over the entire history, never windowed):

| Field | Meaning |
|---|---|
| `var_95` / `var_99` | Historical 5th / 1st percentile of bar returns -- "on the worst 5% / 1% of bars, the loss was at least this." Negative. |
| `cvar_95` | Average return on the bars at or below `var_95` -- how bad the worst 5% were on average. |
| `tail_ratio` | |95th percentile ÷ 5th percentile|. >1 means the best bars were bigger than the worst bars were deep. `null` if the 5th percentile is exactly 0. |
| `skewness` | Asymmetry of bar returns; negative = longer left (loss) tail. |
| `kurtosis` | **Excess** kurtosis (normal = 0); >0 = fatter tails than normal [S4]. |

**Always present:** `n_observations` (number of returns), `symbol`,
`analysis_at` (UTC run time), `angle`.

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| *(absent)* | **Success.** This angle never writes `status: "ok"` (F7). | All fields above. |
| `no_data` | No price bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than 5 returns. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What it really is.** Despite the name, this is not a strategy backtest
and not 44 metrics. It takes the ticker's closing prices for one
timeframe, turns them into bar-to-bar returns, and computes 18 summary
statistics of that return stream -- the numbers you'd see on a fund
factsheet if the "fund" were simply holding this one stock. It runs on
9 timeframes (1min through 6M) because its own design doc widened it
there.

**Two layers, on purpose.** The 11 "core" metrics (plus `ann_vol`) are
also recomputed by `backtest.py` on a rolling 100-bar trailing window,
one row per bar, so later analysis can slice them by session / day /
week. The 6 tail metrics are computed only once over the full history,
never sliced -- tail estimates from a short window would be mostly noise
(this is the angle's own design decision; see `_whole_history_metrics`'
docstring).

**The Sharpe issue, in plain terms (F1).** Sharpe's ratio asks "how much
did this earn *above cash*, per unit of wobble?" [S1]. Ours asks "how
much did it earn, per unit of wobble?" -- no cash subtraction -- and
uses compound growth (CAGR) where Sharpe uses the simple average. The
further the risk-free rate is above zero, the more the two diverge.

**The Sortino issue, in plain terms (F2).** Sortino's point is to count
only harmful volatility. The right way: for every bar, record how far it
fell short of the target (0 if it didn't), then take the root-mean-square
across *all* bars [S3]. Our code instead takes only the losing bars and
measures how spread out they are *around their own average loss* -- so a
stock that loses the same amount every day scores as having no downside
risk at all.

**Annualization.** Every annualized number multiplies by √(periods per
year), which is only right if returns don't carry over from one bar to
the next [S1][S2]. For liquid large caps at intraday frequency, that
held in a 2018-19 test [S5]; for thinner stocks it may not, and Lo shows
how large the overstatement can get [S2]. Separately, the intraday
periods-per-year constants assume a 390-minute regular session (F4).

**Reading the tail numbers.** VaR/CVaR here are historical percentiles
of real returns, so they already reflect fat tails rather than assuming
a bell curve -- good, since real returns are heavy-tailed, with excess
kurtosis anywhere from 10 to over 1,000 at intraday scale, falling as
the timescale lengthens [S5]. That means: a big `kurtosis` on 1min data
is normal; the same value on 1D data is more notable.

**Why it's in Cluster G.** It's evidence about the ticker's past, not a
forecast -- context for sizing and risk, never a directional signal.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| S1 | William F. Sharpe, "The Sharpe Ratio," *The Journal of Portfolio Management*, Fall 1994 (author's own online copy) | Ex-post definition: average differential (excess) return ÷ its standard deviation; riskless-security benchmark; √T annualization assumes zero serial correlation. | https://web.stanford.edu/~wfsharpe/art/sr/sr.htm |
| S2 | Andrew W. Lo, "The Statistics of Sharpe Ratios," *Financial Analysts Journal* 58(4), 2002 (abstract page) | Estimation error; √12 annualization valid only in special cases; up to 65% overstatement from serial correlation. | https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios |
| S3 | Rollinger & Hoffman (Red Rock Capital), "Sortino: A 'Sharper' Ratio," as republished by IASG, 2014-05-20 | Target downside deviation = RMS of below-target shortfalls, above-target returns counted as 0, all observations; std-of-negative-returns-only is the common incorrect method. | https://www.iasg.com/blog/2014/05/20/red-rock-capital-sortino-sharper-ratio |
| S4 | pandas documentation, `pandas.Series.kurt` | Fisher's (excess) kurtosis, normal = 0.0, unbiased. | https://pandas.pydata.org/docs/reference/api/pandas.Series.kurt.html |
| S5 | Ratliff-Crain, Van Oort, Bagrow, Koehler & Tivnan, "Revisiting Cont's Stylized Facts for Modern Stock Markets," arXiv:2311.07738, 2023 (rev. 2024) | Dow 30 intraday, Oct 2018-Mar 2019: 8 of Cont's 11 facts held (heavy tails with kurtosis 10 to >10³, volatility clustering, absence of autocorrelation); gain/loss asymmetry not found. | https://arxiv.org/html/2311.07738 |

**Tried and not used:**
- Rollinger & Hoffman original PDF on cmegroup.com -- timed out twice;
  the IASG republication [S3] was read instead.
- Cont (2001), "Empirical properties of asset returns: stylized facts
  and statistical issues," *Quantitative Finance* 1:223-236 -- the
  author's own PDF failed on a broken HTTPS certificate, so it was not
  read and is not cited directly; [S5] re-tests its facts and was read.
