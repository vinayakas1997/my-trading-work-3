"""Debug: why backtest_factor returns all zeros."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

# Fetch data
ohlcv = {}
for sym in TICKERS:
    r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
        'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS
    }, timeout=30)
    data = r.json().get('data', [])
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['t'], unit='s')
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                       'c': 'close', 'v': 'volume'}, inplace=True)
    ohlcv[sym] = df

# Build panel
panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {}
    for sym in TICKERS:
        if col in ohlcv[sym].columns:
            frames[sym] = ohlcv[sym][col]
    panel[col] = pd.DataFrame(frames)
panel['returns'] = panel['close'].pct_change()

print('Panel close shape:', panel['close'].shape)
print('Panel close head:\n', panel['close'].head())
print('Panel close tail:\n', panel['close'].tail())
print('\nReturns head:\n', panel['returns'].head())

# Compute factor
from vinu_tools.compute.factor_expressions import compute_expression
fv = compute_expression('alpha101_001', panel)
print('\nFactor values head:\n', fv.head())
print('Factor values tail:\n', fv.tail())
print('Factor values describe:\n', fv.describe())

# Compute forward returns
fwd_ret = panel['returns'].shift(-1)
print('\nFwd returns head:\n', fwd_ret.head())
print('Fwd returns tail:\n', fwd_ret.tail())

# Align
common_idx = fwd_ret.index.intersection(fv.index)
print(f'\nCommon index: {len(common_idx)} periods')
fwd_ret2 = fwd_ret.loc[common_idx[:-1]]
fv2 = fv.loc[common_idx[:-1]]
print(f'Forward returns shape: {fwd_ret2.shape}')
print(f'Factor values shape: {fv2.shape}')

print('\nLast 5 rows of fwd_ret:\n', fwd_ret2.tail())
print('\nLast 5 rows of fv:\n', fv2.tail())

# Run backtest
from vinu_tools.compute.factor_backtest import backtest_factor
res = backtest_factor(fv2, fwd_ret2, weight_scheme='rank',
                      long_quantile=0.25, short_quantile=0.25,
                      freq='1d', compute_turnover=True)
print('\nBacktest metrics:', res.metrics)
print('\nPortfolio returns head:', res.portfolio_returns.head(20))
print('\nPortfolio returns nonzero:', (res.portfolio_returns != 0).sum(), 'of', len(res.portfolio_returns))
print('\nLong returns head:', res.long_returns.head(20))
print('\nShort returns head:', res.short_returns.head(20))
print('\nPositions head:\n', res.positions.head(10))
print('\nEquity curve head:\n', res.equity_curve.head(20))
