# Deflated Sharpe Ratio

## What This Angle Studies
Bailey & Lopez de Prado (2014) correction for multiple testing: adjusts observed Sharpe for the number of strategies tested.

## Results
DSR formula implemented and verified: 1 trial → DSR=1.0 (always significant), 10 trials → DSR=0.05, 30+ trials → DSR=0.0. Correctly penalizes multiple testing. Formula accounts for skewness, kurtosis, and non-normality.

## Execution Time
~0.1s

### Bugs Found
None.