"""Test gtja191/qlib158 factor compute via Python API."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')

from vinu_tools.compute.alpha_registry import Registry
from vinu_tools.compute.bigger_recipe import catalog as rc
from vinu_tools.compute.bigger_recipe.executor import Executor

reg = Registry()

# Get the a gtja191 factor module and compute directly
mod = reg.get('gtja191_001')
print(f'gtja191_001: {mod}')

# Try executor approach
executor = Executor()
# Check if gtja191_001 can be computed via executor
try:
    recipe = rc.get_recipe('gtja191_001')
    print(f'gtja191_001 is in recipe catalog: {recipe}')
except Exception as e:
    print(f'gtja191_001 not in recipe catalog: {e}')

# Generate some test bars
dates = pd.date_range('2022-01-03', periods=100, freq='D')
np.random.seed(42)
bars = pd.DataFrame({
    'open': np.random.uniform(95, 105, 100).cumsum() + 100,
    'high': np.random.uniform(97, 108, 100).cumsum() + 102,
    'low': np.random.uniform(93, 103, 100).cumsum() + 98,
    'close': np.random.uniform(94, 106, 100).cumsum() + 101,
    'volume': np.random.randint(800000, 1200000, 100),
    'dividends': np.zeros(100),
    'splits': np.zeros(100)
}, index=dates)

# Try computing via the Registry's formula system
try:
    formula = mod.meta.formula_expression
    print(f'\ngtja191_001 formula expression: {formula}')
except Exception as e:
    print(f'Cannot get formula: {e}')
