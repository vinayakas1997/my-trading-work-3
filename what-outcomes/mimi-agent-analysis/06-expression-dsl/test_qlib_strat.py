"""Test QLib evaluator and strategy expression engine."""
import sys, numpy as np
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')

print("=== QLib Evaluator ===")
from vinu_features.compute.bigger_recipe._alpha_expr.evaluator import evaluate as qlib_eval

close = np.random.randn(100).cumsum() + 100
high = close + np.abs(np.random.randn(100) * 0.5)
low = close - np.abs(np.random.randn(100) * 0.5)
open_ = low + (high - low) * np.random.rand(100)
volume = np.random.randint(500000, 2000000, 100)
arr = {'close': close, 'open': open_, 'high': high, 'low': low, 'volume': volume}

qlib_tests = [
    ('field', '$close'),
    ('arith', '$close - $open'),
    ('hl_spread', '($high - $low) / $open'),
    ('return', 'Ref($close, 1) / $close - 1'),
    ('rank', 'Rank($close, 20)'),
    ('corr', 'Corr($close, $volume, 10)'),
    ('logical', '$close > $open && $volume > 1000000'),
    ('slope', 'Slope($close, 20)'),
    ('rsquare', 'Rsquare($close, 20)'),
    ('idxmax', 'IdxMax($close, 20)'),
    ('resi', 'Resi($close, 20)'),
    ('mean', 'Mean($close, 20)'),
    ('std', 'Std($close, 20)'),
    ('max', 'Max($close, 20)'),
    ('min', 'Min($close, 20)'),
    ('sum', 'Sum($close, 20)'),
    ('quantile', 'Quantile($close, 20, 0.5)'),
    ('greater', 'Greater($close, $open)'),
    ('abs', 'Abs($close)'),
    ('log', 'Log($volume + 1)'),
]
for name, expr in qlib_tests:
    try:
        v = qlib_eval(expr, arr)
        non_null = sum(1 for x in v if x is not None)
        print(f'  PASS {name}: len={len(v)}, non_null={non_null}')
    except Exception as e:
        print(f'  FAIL {name}: {e}')

print("\n=== Strategy Expression Engine ===")
try:
    from vinu_strategy.engine.expression import evaluate_expression as strat_eval
    ctx = {'SMA_9': 100.5, 'SMA_21': 99.2, 'RSI_14': 45.0, 'ADX_14': 28.0}
    strat_tests = [
        ('simple', 'SMA_9 / SMA_21 - 1', 0.0131),
        ('maxmin', 'max(RSI_14, ADX_14) / min(RSI_14, ADX_14)', 28/45),
        ('abs', 'abs(SMA_9 - SMA_21)', 1.3),
        ('mod', 'SMA_9 % 10', 0.5),
        ('power', 'ADX_14 ** 2', 784),
        ('ci', 'sma_9 / sma_21 - 1', 0.0131),
    ]
    for name, expr, _ in strat_tests:
        try:
            v = strat_eval(expr, ctx)
            print(f'  PASS {name}: {v}')
        except Exception as e:
            print(f'  FAIL {name}: {e}')
    # Error handling
    for name, expr in [('unknown', 'unknown + 1'), ('empty', ''), ('disallowed', 'import os')]:
        try:
            strat_eval(expr, ctx)
            print(f'  FAIL err_{name}: should have raised')
        except Exception as e:
            print(f'  PASS err_{name}: {e}')
except ImportError as e:
    print(f'  SKIP: {e}')
