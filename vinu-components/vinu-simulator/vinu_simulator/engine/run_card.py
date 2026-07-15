from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RUN_CARD_SCHEMA_VERSION = "0.1"


def _sha256_of(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": _sha256_of(path),
    }


def write_run_card(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
    metrics: dict[str, float],
    benchmark_metrics: dict[str, dict[str, float]] | None = None,
    trade_count: int = 0,
    equity_points: int = 0,
    strategy_code_hash: str = "",
    validation: dict[str, Any] | None = None,
    attribution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, Any]] = []
    for fname in ("equity.parquet", "weights.parquet", "trades.parquet", "meta.json", "config.json"):
        fpath = run_dir / fname
        if fpath.exists():
            artifacts.append(_artifact_entry(fpath))

    run_card: dict[str, Any] = {
        "schema_version": _RUN_CARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "backtest": {
            "codes": list(config.get("symbols", config.get("tickers", []))),
            "start_date": config.get("start_date", ""),
            "end_date": config.get("end_date", ""),
            "interval": config.get("interval", "1d"),
            "initial_cash": config.get("initial_capital", 1_000_000.0),
        },
        "reproducibility": {
            "config_hash": _sha256_of(run_dir / "config.json") if (run_dir / "config.json").exists() else "",
            "strategy_hash": strategy_code_hash,
        },
        "metrics": {k: v for k, v in metrics.items() if isinstance(v, (int, float))},
        "trade_count": trade_count,
        "equity_points": equity_points,
        "artifacts": artifacts,
    }

    if benchmark_metrics:
        run_card["benchmark_metrics"] = benchmark_metrics

    if validation:
        run_card["validation"] = validation

    if attribution:
        run_card["attribution"] = attribution

    card_path = run_dir / "run_card.json"
    card_path.write_text(json.dumps(run_card, indent=2, default=str) + "\n", encoding="utf-8")

    md_path = run_dir / "run_card.md"
    md_path.write_text(_render_markdown(run_card), encoding="utf-8")

    return run_card


def _render_markdown(card: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Run Card: {card['run_id']}")
    lines.append(f"")
    lines.append(f"- **Generated**: {card['generated_at']}")
    lines.append(f"- **Schema**: {card['schema_version']}")
    lines.append(f"")

    bt = card.get("backtest", {})
    lines.append(f"## Backtest Configuration")
    lines.append(f"")
    lines.append(f"| Param | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Codes | {', '.join(bt.get('codes', []))} |")
    lines.append(f"| Period | {bt.get('start_date', '')} → {bt.get('end_date', '')} |")
    lines.append(f"| Interval | {bt.get('interval', '')} |")
    lines.append(f"| Initial Cash | {bt.get('initial_cash', ''):,} |")
    lines.append(f"")

    rep = card.get("reproducibility", {})
    lines.append(f"## Reproducibility")
    lines.append(f"")
    lines.append(f"- **Config Hash**: `{rep.get('config_hash', 'N/A')[:16]}...`")
    lines.append(f"- **Strategy Hash**: `{rep.get('strategy_hash', 'N/A')[:16]}...`")
    lines.append(f"")

    metrics = card.get("metrics", {})
    if metrics:
        lines.append(f"## Performance Metrics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        for k, v in sorted(metrics.items()):
            if isinstance(v, float):
                if "return" in k or "drawdown" in k or "volatility" in k:
                    lines.append(f"| {k} | {v:.4%} |")
                else:
                    lines.append(f"| {k} | {v:.4f} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append(f"")

    bm = card.get("benchmark_metrics", {})
    if bm:
        for ticker, bm_metrics in bm.items():
            lines.append(f"## Benchmark: {ticker}")
            lines.append(f"")
            lines.append(f"| Metric | Value |")
            lines.append(f"|---|---|")
            for k, v in sorted(bm_metrics.items()):
                if isinstance(v, float):
                    if "return" in k or "drawdown" in k or "volatility" in k:
                        lines.append(f"| {k} | {v:.4%} |")
                    else:
                        lines.append(f"| {k} | {v:.4f} |")
                else:
                    lines.append(f"| {k} | {v} |")
            lines.append(f"")

    val = card.get("validation")
    if val:
        lines.append(f"## Validation Results")
        lines.append(f"")
        mc = val.get("monte_carlo", {})
        if mc.get("minimum_met"):
            p_val = mc.get('p_value')
            sim_mean = mc.get('sim_mean')
            sim_std = mc.get('sim_std')
            sim_p5 = mc.get('sim_p5')
            sim_p95 = mc.get('sim_p95')
            
            p_val_str = f"{p_val:.4f}" if p_val is not None else "N/A"
            mean_str = f"{sim_mean:.4f}" if sim_mean is not None else "N/A"
            std_str = f"{sim_std:.4f}" if sim_std is not None else "N/A"
            p5_str = f"{sim_p5:.4f}" if sim_p5 is not None else "N/A"
            p95_str = f"{sim_p95:.4f}" if sim_p95 is not None else "N/A"
            
            lines.append(f"### Monte Carlo Path Significance")
            lines.append(f"- **p-value (Sharpe)**: {p_val_str} (Null: random trade ordering is no better)")
            lines.append(f"- **Simulated Sharpe**: mean={mean_str}, std={std_str}, 5th%={p5_str}, 95th%={p95_str}")
            lines.append(f"- **Number of trades / iterations**: {mc.get('n_trades', 'N/A')} / {mc.get('n_iterations', 'N/A')}")
            lines.append(f"")
            
        bs = val.get("bootstrap", {})
        if bs.get("minimum_met"):
            ci_low = bs.get('ci_low')
            ci_high = bs.get('ci_high')
            mean = bs.get('mean')
            std = bs.get('std')
            
            ci_low_str = f"{ci_low:.4f}" if ci_low is not None else "N/A"
            ci_high_str = f"{ci_high:.4f}" if ci_high is not None else "N/A"
            mean_str = f"{mean:.4f}" if mean is not None else "N/A"
            std_str = f"{std:.4f}" if std is not None else "N/A"
            
            lines.append(f"### Bootstrap Sharpe Stability")
            lines.append(f"- **95% Confidence Interval**: [{ci_low_str}, {ci_high_str}]")
            lines.append(f"- **Bootstrap Sharpe**: mean={mean_str}, std={std_str}")
            lines.append(f"- **Observations / iterations**: {bs.get('n_observations', 'N/A')} / {bs.get('n_iterations', 'N/A')}")
            lines.append(f"")
            
        wf = val.get("walk_forward", {})
        if wf.get("minimum_met"):
            consistency_rate = wf.get('consistency_rate')
            ret_mean = wf.get('return_mean')
            ret_std = wf.get('return_std')
            sh_mean = wf.get('sharpe_mean')
            sh_std = wf.get('sharpe_std')
            
            cr_str = f"{consistency_rate:.1%}" if consistency_rate is not None else "N/A"
            ret_mean_str = f"{ret_mean:.4%}" if ret_mean is not None else "N/A"
            ret_std_str = f"{ret_std:.4%}" if ret_std is not None else "N/A"
            sh_mean_str = f"{sh_mean:.4f}" if sh_mean is not None else "N/A"
            sh_std_str = f"{sh_std:.4f}" if sh_std is not None else "N/A"
            
            lines.append(f"### Walk-Forward Consistency")
            lines.append(f"- **Consistency Rate**: {cr_str} ({wf.get('profitable_windows', 'N/A')}/{wf.get('total_windows', 'N/A')} profitable windows)")
            lines.append(f"- **Return**: mean={ret_mean_str}, std={ret_std_str}")
            lines.append(f"- **Sharpe**: mean={sh_mean_str}, std={sh_std_str}")
            lines.append(f"")

    attr = card.get("attribution")
    if attr:
        lines.append(f"## Performance Attribution")
        lines.append(f"")
        by_sym = attr.get("by_symbol", {})
        if by_sym:
            lines.append(f"### Symbol Performance")
            lines.append(f"")
            lines.append(f"| Symbol | Trades | Win Rate | Total PnL | Avg PnL | Avg Win | Avg Loss |")
            lines.append(f"|---|---|---|---|---|---|---|")
            for sym, stats in sorted(by_sym.items()):
                count = stats.get('count')
                win_rate = stats.get('win_rate')
                total_pnl = stats.get('total_pnl')
                avg_pnl = stats.get('avg_pnl')
                avg_win = stats.get('avg_win')
                avg_loss = stats.get('avg_loss')
                
                count_str = str(count) if count is not None else "N/A"
                win_rate_str = f"{win_rate:.1%}" if win_rate is not None else "N/A"
                total_pnl_str = f"{total_pnl:,.2f}" if total_pnl is not None else "N/A"
                avg_pnl_str = f"{avg_pnl:,.2f}" if avg_pnl is not None else "N/A"
                avg_win_str = f"{avg_win:,.2f}" if avg_win is not None else "N/A"
                avg_loss_str = f"{avg_loss:,.2f}" if avg_loss is not None else "N/A"
                
                lines.append(f"| {sym} | {count_str} | {win_rate_str} | {total_pnl_str} | {avg_pnl_str} | {avg_win_str} | {avg_loss_str} |")
            lines.append(f"")
            
        by_bench = attr.get("by_benchmark", {})
        if by_bench:
            lines.append(f"### Beta Regression vs Benchmarks")
            lines.append(f"")
            lines.append(f"| Benchmark | Alpha (Ann.) | Beta | R² | Tracking Error | Info Ratio | Obs |")
            lines.append(f"|---|---|---|---|---|---|---|")
            for ticker, stats in sorted(by_bench.items()):
                alpha = stats.get('alpha')
                beta = stats.get('beta')
                r2 = stats.get('r_squared')
                te = stats.get('tracking_error')
                ir = stats.get('information_ratio')
                n_obs = stats.get('n_observations')
                
                alpha_str = f"{alpha:.4%}" if alpha is not None else "N/A"
                beta_str = f"{beta:.4f}" if beta is not None else "N/A"
                r2_str = f"{r2:.4f}" if r2 is not None else "N/A"
                te_str = f"{te:.4%}" if te is not None else "N/A"
                ir_str = f"{ir:.4f}" if ir is not None else "N/A"
                n_obs_str = str(n_obs) if n_obs is not None else "N/A"
                
                lines.append(f"| {ticker} | {alpha_str} | {beta_str} | {r2_str} | {te_str} | {ir_str} | {n_obs_str} |")
            lines.append(f"")
            
        by_reg = attr.get("by_regime", {})
        if by_reg:
            lines.append(f"### Market Regime Performance")
            lines.append(f"")
            for ticker, regimes in sorted(by_reg.items()):
                lines.append(f"#### Benchmark: {ticker}")
                lines.append(f"")
                lines.append(f"| Regime | Days | Total Return | Avg Return | Sharpe | Win Rate |")
                lines.append(f"|---|---|---|---|---|---|")
                for regime, stats in sorted(regimes.items()):
                    count = stats.get('count')
                    total_return = stats.get('total_return')
                    avg_return = stats.get('avg_return')
                    sharpe = stats.get('sharpe')
                    win_rate = stats.get('win_rate')
                    
                    count_str = str(count) if count is not None else "N/A"
                    tr_str = f"{total_return:.4%}" if total_return is not None else "N/A"
                    ar_str = f"{avg_return:.4%}" if avg_return is not None else "N/A"
                    sharpe_str = f"{sharpe:.4f}" if sharpe is not None else "N/A"
                    wr_str = f"{win_rate:.1%}" if win_rate is not None else "N/A"
                    
                    lines.append(f"| {regime} | {count_str} | {tr_str} | {ar_str} | {sharpe_str} | {wr_str} |")
                lines.append(f"")

    lines.append(f"## Artifacts")
    lines.append(f"")
    lines.append(f"| File | Size | SHA256 |")
    lines.append(f"|---|---|---|")
    for a in card.get("artifacts", []):
        lines.append(f"| {a['path']} | {a['size_bytes']:,} B | `{a['sha256'][:12]}...` |")
    lines.append(f"")

    lines.append(f"---")
    lines.append(f"*Run card auto-generated by vinu-simulator*")
    return "\n".join(lines)
