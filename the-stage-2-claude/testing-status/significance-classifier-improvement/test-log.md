# significance-classifier-improvement — Test Log

**Status:** Not started.

## What will be tested / Expected output

Baseline (already verified, 2026-08-02, before any change):

| Ticker | AUC | Top-decile lift | n_train_positive | n_test_positive |
|---|---|---|---|---|
| AAPL | 0.852 | 5.0x | 161 | 62 |
| TSLA | 0.915 | 6.2x | 143 | 66 |
| JNJ | 0.661 | 6.0x | 15 | 5 |

- After any feature/data change, re-run `news_price_causality` for
  AAPL/TSLA/JNJ sequentially and compare the new `significance_model_eval`
  row's `auc`/`top_decile_lift` against this baseline, per ticker.
- Pass condition: JNJ's AUC moves meaningfully above 0.661 **without**
  AAPL/TSLA's AUC dropping. A regression on AAPL/TSLA while JNJ improves
  is not a clean win — report honestly either way.
- A negative result (nothing moves the needle) is a legitimate, reportable
  outcome, not a failure to hide.
- Any new feature must pass the same leakage test as `impact_label`
  failed: is it knowable at publication time, or does it depend on
  post-event price data?
- Full detail: [../../scope-responsibilities/02-significance-classifier-improvement.md](../../scope-responsibilities/02-significance-classifier-improvement.md)

## Bug / Fix Log

_Nothing logged yet — testing has not started._
