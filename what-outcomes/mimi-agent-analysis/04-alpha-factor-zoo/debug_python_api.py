"""Debug: test Python API for gtja191 factors."""
import sys, pandas as pd
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
from vinu_tools.compute.alpha_registry import Registry
from vinu_tools.compute.bigger_recipe import catalog as rc

reg = Registry()
print(f'Total factors: {reg.count()}')

print('\nRecipe names:', rc.list_recipe_names())

# Check if gtja191 is a recipe
for n in rc.list_recipe_names():
    meta = rc.get_recipe_meta(n)
    print(f'  {n}: warmup={meta.get("warmup_bars")}, desc={meta.get("description","")[:80]}')

print('\n--- Trying individual gtja191 factor via Python API ---')
mod = reg.get('gtja191_001')
if mod:
    print(f'gtja191_001 exists: theme={mod.meta.theme}, cols={mod.meta.columns_required}')
    # Try computing
    bars = pd.DataFrame({
        'open': [100.0], 'high': [105.0], 'low': [98.0], 'close': [102.0], 'volume': [1000000.0],
        'dividends': [0.0], 'splits': [0.0]
    })
    bars.index = pd.date_range('2022-01-03', periods=1, freq='D')
    try:
        result = reg.compute('gtja191_001', bars)
        print(f'gtja191_001 compute result: {result}')
    except Exception as e:
        print(f'gtja191_001 compute error: {e}')
