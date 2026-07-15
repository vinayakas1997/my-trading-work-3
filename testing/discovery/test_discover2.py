"""Debug config and discover."""
import sys, os
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
os.chdir(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price')

from vinu_stock.config import load_config
config = load_config()
print('Config attrs:', [a for a in dir(config) if not a.startswith('_')])
print(f'data_root: {getattr(config, "data_root", "N/A")}')
print(f'vinu_stock_data_root: {getattr(config, "vinu_stock_data_root", "N/A")}')

from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.backfill.orchestrator import _discover_first_year, MIN_BACKFILL_YEAR
print(f'MIN_BACKFILL_YEAR: {MIN_BACKFILL_YEAR}')

registry = ProviderRegistry(config)
print(f'\nProviders for backfill role:')
for p in registry.for_role('backfill'):
    print(f'  {p.provider_id}: configured={p.is_configured()}')

for sym in ['AAPL', 'MSFT', 'NVDA', 'TSLA']:
    start = _discover_first_year(sym, registry)
    print(f'{sym}: start_year={start}')
