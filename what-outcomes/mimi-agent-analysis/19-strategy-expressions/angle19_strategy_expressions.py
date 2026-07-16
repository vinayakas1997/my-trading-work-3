"""Angle 19: Strategy Expressions — expression engine, rules DSL, YAML strategies."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

from datetime import datetime, timezone

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 1: Expression Engine ──
print("=== STEP 1: EXPRESSION ENGINE ===")
t0 = time.time()
try:
    from vinu_strategy.engine.expression import evaluate_expression
    has_engine = True
    log('import_engine', time.time()-t0, 'PASS', 'evaluate_expression imported')
except Exception as e:
    has_engine = False
    log('import_engine', time.time()-t0, 'FAIL', str(e))

if has_engine:
    t0 = time.time()
    ctx = {
        'SMA_9': 100.5, 'SMA_21': 99.2, 'RSI_14': 45.0,
        'ADX_14': 28.0, 'MOM_20': 0.05, 'ATR_14': 2.5,
        'BB_UPPER_20': 105.0, 'BB_MID_20': 100.0, 'BB_LOWER_20': 95.0,
        'close': 100.5,
    }
    expressions = [
        ('signal', 'SMA_9 / SMA_21 - 1', 0.0131),
        ('rsi_mr', 'max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)', 0.0),
        ('mom_adx', 'MOM_20 * (ADX_14 / 50)', 0.028),
        ('bb_position', '(close - BB_LOWER_20) / (BB_UPPER_20 - BB_LOWER_20)', None),
    ]
    for name, expr, expected in expressions:
        t1 = time.time()
        try:
            result = evaluate_expression(expr, ctx)
            status = 'PASS'
            detail = f'{expr} = {result:.4f}'
            if expected is not None and abs(result - expected) > 0.01:
                status = 'WARN'
                detail += f' (expected ~{expected})'
            log(f'expr_{name}', time.time()-t1, status, detail)
        except Exception as e:
            log(f'expr_{name}', time.time()-t1, 'FAIL', str(e))

# ── Step 2: Rules DSL ──
print("\n=== STEP 2: RULES DSL ===")
t0 = time.time()
try:
    from vinu_strategy.engine.rules import RuleEngine
    has_rules = True
    log('import_rules', time.time()-t0, 'PASS', 'RuleEngine imported')
except Exception as e:
    has_rules = False
    log('import_rules', time.time()-t0, 'FAIL', str(e))

if has_rules:
    t0 = time.time()
    rules_config = [
        {'name': 'adx_strength', 'when': [{'source': 'features', 'key': 'ADX_14', 'gt': 25}], 'then': {'action': 'weight_multiply', 'value': 1.0}},
        {'name': 'weak_trend', 'when': [{'source': 'features', 'key': 'ADX_14', 'lte': 25}], 'then': {'action': 'weight_set', 'value': 0.0}},
    ]
    try:
        engine = RuleEngine(rules_config)
        test_ctx = {'features': {'ADX_14': 28.0}, 'weights': {'AAPL': 0.5}, 'cash': 0.5}
        result = engine.evaluate(test_ctx)
        log('rules_eval', time.time()-t0, 'PASS', str(result)[:300])
    except Exception as e:
        log('rules_eval', time.time()-t0, 'FAIL', str(e))

# ── Step 3: YAML Strategy Templates ──
print("\n=== STEP 3: YAML STRATEGY TEMPLATES ===")
t0 = time.time()
try:
    from vinu_strategy.models.strategy import StrategyConfig as StrategyDefinition
    from vinu_strategy.loader import load_strategy
    has_yaml = True
    log('import_yaml', time.time()-t0, 'PASS', 'StrategyConfig loaded')
except Exception as e:
    has_yaml = False
    log('import_yaml', time.time()-t0, 'FAIL', str(e))

if has_yaml:
    t0 = time.time()
    try:
        strat = load_strategy('adx_filtered_crossover')
        if strat:
            log('yaml_adx', time.time()-t0, 'PASS',
                f'name={strat.name}, features={strat.features_required}, pipeline={strat.pipeline}')
        else:
            log('yaml_adx', time.time()-t0, 'WARN', 'Strategy not found')
    except Exception as e:
        log('yaml_adx', time.time()-t0, 'FAIL', str(e))

# ── Step 4: Strategy List ──
print("\n=== STEP 4: AVAILABLE STRATEGIES ===")
t0 = time.time()
try:
    strategies_dir = '/home/somic_cps/Vina/my-trading-work-3/vinu-components/vinu-strategy/strategies'
    import os, yaml
    if os.path.isdir(strategies_dir):
        files = [f for f in os.listdir(strategies_dir) if f.endswith(('.yaml', '.yml'))]
        for fname in sorted(files):
            with open(os.path.join(strategies_dir, fname)) as fh:
                data = yaml.safe_load(fh)
            sname = data.get('name', fname)
            desc = data.get('description', '')[:80]
            log(f'strategy_{sname}', time.time()-t0, 'PASS', f'{desc}')
    else:
        log('strategies_dir', 0, 'FAIL', f'Not found: {strategies_dir}')
except Exception as e:
    log('strategies_dir', 0, 'FAIL', str(e))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 19 strategy expressions finished')
