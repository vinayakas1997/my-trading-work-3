"""Test _discover_first_year directly."""
import sys, os
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
os.chdir(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price')
os.environ['VINU_STOCK_CONFIG'] = r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\vinu_stock\providers\config\providers.yaml'

from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.backfill.orchestrator import _discover_first_year, MIN_BACKFILL_YEAR
from vinu_stock.config import load_config

config = load_config()
print(f'Data root: {config.vinu_stock_data_root}')
print(f'Alpaca key configured: {bool(config.alpaca_api_key)}')
print(f'MIN_BACKFILL_YEAR: {MIN_BACKFILL_YEAR}')

registry = ProviderRegistry(config)
print(f'\nProviders for backfill role:')
for p in registry.for_role('backfill'):
    print(f'  {p.provider_id}: configured={p.is_configured()}')

for sym in ['AAPL', 'MSFT', 'NVDA', 'TSLA']:
    start = _discover_first_year(sym, registry)
    print(f'\n{sym}: start_year={start}')
    # Also check catalog
    from vinu_stock.catalog.store import CatalogStore
    cat = CatalogStore(config.vinu_stock_data_root)
    entry = cat.get_symbol(sym)
    print(f'  catalog: first_bar_ts={entry.first_bar_ts if entry else None}')
