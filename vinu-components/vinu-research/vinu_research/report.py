from __future__ import annotations

from typing import Any

from vinu_research.models import BacktestResult, IterationRecord


def generate_report(
    symbol: str,
    from_date: str,
    to_date: str,
    user_idea: str,
    history: list[IterationRecord],
    best_result: BacktestResult | None,
    best_iteration: int,
) -> str:
    lines: list[str] = []
    lines.append("=== FINAL RESEARCH REPORT ===")
    lines.append("")
    lines.append(f"Strategy: {user_idea}")
    lines.append(f"Ticker: {symbol.upper()}")
    lines.append(f"Time Period: {from_date} \u2192 {to_date}")
    lines.append(f"Iterations: {len(history)}")
    lines.append("")

    if len(history) > 1:
        lines.append("Refinements Applied:")
        for i, rec in enumerate(history):
            if i == 0:
                continue
            prev = history[i - 1]
            suggestions = rec.critique.suggestions
            if suggestions:
                for s in suggestions:
                    lines.append(f"  {i}. {s}")
        lines.append("")

    first = history[0].result if history else None
    best = best_result

    if first and best and len(history) > 1:
        lines.append("Before \u2192 After:")
        lines.append(
            f"  Sharpe:         {first.metrics.sharpe_ratio:.2f} \u2192 {best.metrics.sharpe_ratio:.2f}"
        )
        lines.append(
            f"  Max Drawdown:   {first.metrics.max_drawdown:.1%} \u2192 {best.metrics.max_drawdown:.1%}"
        )
        lines.append(
            f"  Win Rate:       {first.metrics.win_rate:.0%} \u2192 {best.metrics.win_rate:.0%}"
        )
        lines.append(
            f"  Total Return:   {first.metrics.total_return:.1%} \u2192 {best.metrics.total_return:.1%}"
        )
        lines.append("")
    elif best:
        lines.append("Final Metrics:")
        lines.append(f"  Sharpe:         {best.metrics.sharpe_ratio:.2f}")
        lines.append(f"  Max Drawdown:   {best.metrics.max_drawdown:.1%}")
        lines.append(f"  Win Rate:       {best.metrics.win_rate:.0%}")
        lines.append(f"  Total Return:   {best.metrics.total_return:.1%}")
        lines.append("")

    if history:
        lines.append("Iteration History:")
        lines.append(
            f"  {'Iter':<6} {'Sharpe':<10} {'MaxDD':<10} {'WinRate':<10} {'Verdict':<10}"
        )
        lines.append("  " + "-" * 50)
        for rec in history:
            m = rec.result.metrics
            lines.append(
                f"  {rec.iteration:<6} {m.sharpe_ratio:<10.2f} {m.max_drawdown:<10.1%} "
                f"{m.win_rate:<10.0%} {rec.critique.verdict:<10}"
            )
        lines.append("")

    if best and best.benchmark_metrics:
        lines.append("Benchmark Comparison:")
        for bm_name, bm_data in best.benchmark_metrics.items():
            lines.append(f"  vs {bm_name}: Sharpe={bm_data.get('sharpe_ratio', 0):.2f}, "
                         f"Total Return={bm_data.get('total_return', 0):.1%}")
        lines.append("")

    lines.append("Key Findings:")
    if history:
        all_critiques = [rec.critique for rec in history]
        all_findings = set()
        for c in all_critiques:
            for s in c.suggestions:
                all_findings.add(s)
        if all_findings:
            for i, finding in enumerate(all_findings, 1):
                lines.append(f"  {i}. {finding}")
        else:
            lines.append("  No specific issues identified — strategy performed well.")
    lines.append("")

    lines.append("Optimized Strategy Code:")
    if history:
        best_rec = next(
            (r for r in history if r.iteration == best_iteration),
            history[-1],
        )
        lines.append("```python")
        lines.append(best_rec.strategy_code)
        lines.append("```")

    lines.append("")
    return "\n".join(lines)


def format_metrics_table(metrics: dict[str, float]) -> str:
    rows = [
        ("Total Return", f"{metrics.get('total_return', 0):.2%}"),
        ("CAGR", f"{metrics.get('cagr', 0):.2%}"),
        ("Annual Vol", f"{metrics.get('annual_volatility', 0):.2%}"),
        ("Sharpe", f"{metrics.get('sharpe_ratio', 0):.2f}"),
        ("Sortino", f"{metrics.get('sortino_ratio', 0):.2f}"),
        ("Max DD", f"{metrics.get('max_drawdown', 0):.1%}"),
        ("Win Rate", f"{metrics.get('win_rate', 0):.0%}"),
    ]
    return "\n".join(f"  {k:<15} {v}" for k, v in rows)
