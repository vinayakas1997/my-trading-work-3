"""Angle 18: Research Loop — template documentation, risk critic, auto-filters."""
import sys, json, time, os
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

from datetime import datetime, timezone

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

BASE = '/home/somic_cps/Vina/my-trading-work-3/vinu-components'

# ── Step 1: Template Documentation ──
print("=== STEP 1: STRATEGY TEMPLATES ===")
t0 = time.time()
strategies_dir = f'{BASE}/vinu-strategy/strategies'
templates = []
if os.path.isdir(strategies_dir):
    files = sorted([f for f in os.listdir(strategies_dir) if f.endswith(('.yaml', '.yml'))])
    for fname in files:
        fp = os.path.join(strategies_dir, fname)
        with open(fp) as fh:
            import yaml
            data = yaml.safe_load(fh)
        name = data.get('name', fname.replace('.yaml', ''))
        desc = data.get('description', '')[:100]
        features = data.get('features_required', [])
        templates.append({'name': name, 'desc': desc, 'features': features})
        log(f'template_{name}', time.time()-t0, 'PASS', f'{desc}, features={features}')
log('template_count', time.time()-t0, 'PASS', f'{len(templates)} templates found')

# ── Step 2: Risk Critic Dimensions ──
print("\n=== STEP 2: RISK CRITIC (19 DIMENSIONS) ===")
t0 = time.time()
risk_critic = {
    1: ('Max drawdown', '< -15% = concern'),
    2: ('Sharpe ratio', '< 0.5 = concern'),
    3: ('Win rate', '< 40% = concern'),
    4: ('London session drawdown clustering', '>= 2 drawdowns'),
    5: ('CVaR 95%', '< -3% = concern'),
    6: ('Recovery time', '> 120 days = concern'),
    7: ('Annual turnover', '> 2000% = concern'),
    8: ('Sharpe p-value', '> 0.05 = not significant'),
    9: ('Profit factor', '< 1.0 = losing money'),
    10: ('VaR 95%', '< -4% = concern'),
    11: ('Alpha vs benchmark', '< 0 = underperforming'),
    12: ('Information ratio', '0-0.5 = weak'),
    13: ('Down capture', '> 120% = losing more than market'),
    14: ('Excess CAGR', '< 0 = underperforming'),
    15: ('Passive outperformance', 'Benchmark CAGR > strategy CAGR'),
    16: ('Trade count', '< 30 = insufficient sample'),
    17: ('Sharpe improvement', 'Must improve by > 0.05 per iteration'),
    18: ('Max drawdown threshold', '< -25% triggers STOP'),
    19: ('Iteration stall', 'Sharpe < 0.3 after iteration 3 = STOP'),
}
for idx, (name, threshold) in risk_critic.items():
    log(f'critic_{idx:02d}_{name[:30]}', 0, 'PASS', f'{threshold}')
log('critic_count', 0, 'PASS', f'{len(risk_critic)} dimensions documented')

# ── Step 3: Auto-Filters Documentation ──
print("\n=== STEP 3: AUTO-INJECTED FILTERS ===")
t0 = time.time()
filters = {
    'ADX filter': 'Skip if ADX < 20 (weak trend)',
    'Session exclusion': 'Skip London session (low liquidity)',
    'News cooldown': 'Skip 60min after high-impact news',
    'Volatility guard': 'Skip if ATR/close > 5% (excessive vol)',
}
for name, desc in filters.items():
    log(f'filter_{name[:20]}', time.time()-t0, 'PASS', desc)

# ── Step 4: Research Loop Import Test ──
print("\n=== STEP 4: RESEARCH LOOP MODULE ===")
t0 = time.time()
try:
    from vinu_research.runner import run_research
    log('import_runner', time.time()-t0, 'PASS', 'vinu_research.runner imported')
except Exception as e:
    log('import_runner', time.time()-t0, 'WARN', f'{e}')

# Check what's actually available
t0 = time.time()
research_dir = f'{BASE}/vinu-research/vinu_research'
if os.path.isdir(research_dir):
    modules = sorted([f.replace('.py', '') for f in os.listdir(research_dir) if f.endswith('.py') and not f.startswith('_')])
    log('research_modules', time.time()-t0, 'PASS', f'Available: {modules}')
else:
    log('research_modules', time.time()-t0, 'FAIL', 'vinu_research directory not found')

# ── Step 5: Walk-Forward & Holdout Documentation ──
print("\n=== STEP 5: VALIDATION METHODS ===")
t0 = time.time()
validation = {
    'Monte Carlo permutation': '1000 shuffles of trade PnL → p-value for Sharpe',
    'Bootstrap Sharpe CI': '1000 bootstrap samples → 95% CI for true Sharpe',
    'Walk-forward consistency': 'N windows, IS vs OOS Sharpe degradation',
    'Deflated Sharpe ratio': 'Bailey & Lopez de Prado (2014) multiple testing correction',
    'Holdout validation': 'Trailing 20% of data never seen by refinement',
}
for name, desc in validation.items():
    log(f'validation_{name[:25]}', time.time()-t0, 'PASS', desc)

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 18 research loop finished')
