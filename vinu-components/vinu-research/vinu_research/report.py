from __future__ import annotations

from typing import Any

from vinu_research.models import (
    BacktestResult,
    HoldoutResult,
    IterationRecord,
    StressTestResult,
    WalkForwardResult,
)
from vinu_research.portfolio import PortfolioAnalysisResult


def generate_report(
    symbol: str,
    from_date: str,
    to_date: str,
    user_idea: str,
    history: list[IterationRecord],
    best_result: BacktestResult | None,
    best_iteration: int,
    walk_forward: WalkForwardResult | None = None,
    holdout: HoldoutResult | None = None,
    portfolio: PortfolioAnalysisResult | None = None,
    stress_test: StressTestResult | None = None,
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

    if best and best.metrics.tail_ratio != 0.0:
        m = best.metrics
        lines.append("Extended Risk Metrics:")
        lines.append(f"  VaR (95%):      {m.var_95:.1%}")
        lines.append(f"  CVaR (95%):     {m.cvar_95:.1%}")
        lines.append(f"  Tail Ratio:     {m.tail_ratio:.2f}")
        lines.append(f"  Profit Factor:  {m.profit_factor:.2f}")
        lines.append(f"  Avg Win / Loss: {m.win_loss_ratio:.2f}x")
        lines.append(f"  Max DD Duration: {m.max_dd_duration_days} days")
        lines.append(f"  Recovery Time:  {m.recovery_time_days} days")
        if m.annual_turnover > 0:
            lines.append(f"  Annual Turnover: {m.annual_turnover:.0f}%")
        if m.sharpe_p_value < 1.0:
            lines.append(f"  Sharpe 95% CI:  [{m.sharpe_ci_95_low:.2f}, {m.sharpe_ci_95_high:.2f}]")
            lines.append(f"  Sharpe p-value: {m.sharpe_p_value:.3f}")
        if m.beta != 0.0:
            lines.append(f"  Beta:           {m.beta:.2f}")
            lines.append(f"  Alpha (ann.):   {m.alpha:.2%}")
            lines.append(f"  Info Ratio:     {m.information_ratio:.2f}")
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
        for bm_name, bm_data in best.benchmark_metrics.items():
            lines.append(f"Benchmark Comparison (vs {bm_name}):")
            bm_sharpe = bm_data.get("sharpe_ratio", 0)
            bm_cagr = bm_data.get("cagr", 0)
            bm_vol = bm_data.get("annual_volatility", 0)
            bm_maxdd = bm_data.get("max_drawdown", 0)
            bm_wr = bm_data.get("win_rate", 0)
            st_cagr = best.metrics.cagr
            st_vol = best.metrics.annual_volatility
            st_maxdd = best.metrics.max_drawdown
            st_wr = best.metrics.win_rate

            lines.append(f"  {'Metric':<20} {'Strategy':<12} {'Benchmark':<12} {'Diff':<10}")
            lines.append("  " + "-" * 54)
            lines.append(f"  {'CAGR':<20} {st_cagr:<11.1%} {bm_cagr:<11.1%} {st_cagr - bm_cagr:<+9.1%}")
            lines.append(f"  {'Sharpe':<20} {best.metrics.sharpe_ratio:<11.2f} {bm_sharpe:<11.2f} {best.metrics.sharpe_ratio - bm_sharpe:<+9.2f}")
            lines.append(f"  {'Max Drawdown':<20} {st_maxdd:<11.1%} {bm_maxdd:<11.1%} {st_maxdd - bm_maxdd:<+9.1%}")
            lines.append(f"  {'Volatility':<20} {st_vol:<11.1%} {bm_vol:<11.1%} {st_vol - bm_vol:<+9.1%}")
            lines.append(f"  {'Win Rate':<20} {st_wr:<11.0%} {bm_wr:<11.0%} {st_wr - bm_wr:<+9.0%}")

            alpha = bm_data.get("alpha", None)
            beta = bm_data.get("beta", None)
            ir = bm_data.get("information_ratio", None)
            te = bm_data.get("tracking_error", None)
            up_cap = bm_data.get("up_capture", None)
            down_cap = bm_data.get("down_capture", None)
            corr = bm_data.get("market_correlation", None)
            rel_dd = bm_data.get("relative_max_drawdown", None)

            if alpha is not None:
                lines.append("")
                lines.append("  Alpha & Beta vs Benchmark:")
                lines.append(f"    Alpha (ann.):        {alpha:.2%}")
                lines.append(f"    Beta:                {beta:.2f}")
                if corr is not None:
                    lines.append(f"    Market Correlation:  {corr:.2f}")
                if ir is not None:
                    lines.append(f"    Information Ratio:   {ir:.2f}")
                if te is not None:
                    lines.append(f"    Tracking Error:      {te:.1%}")
                if rel_dd is not None:
                    lines.append(f"    Relative Max DD:     {rel_dd:.1%}")
            if up_cap is not None and down_cap is not None:
                lines.append("")
                lines.append("  Market Capture:")
                lines.append(f"    Up Capture:    {up_cap:.0%} of market upside")
                lines.append(f"    Down Capture:  {down_cap:.0%} of market downside")
            lines.append("")

    if holdout is not None:
        lines.append("=== HOLDOUT VALIDATION ===")
        lines.append(
            f"Holdout period: {holdout.holdout_from} → {holdout.holdout_to} "
            "(never used during refinement)"
        )
        lines.append("")
        lines.append(f"  {'Metric':<20} {'In-Sample':<14} {'Holdout':<14}")
        lines.append("  " + "-" * 48)
        lines.append(
            f"  {'Sharpe':<20} {holdout.in_sample_sharpe:<14.2f} {holdout.holdout_sharpe:<14.2f}"
        )
        lines.append(f"  {'Max Drawdown':<20} {'':<14} {holdout.holdout_max_drawdown:<14.1%}")
        lines.append(f"  {'Total Return':<20} {'':<14} {holdout.holdout_total_return:<14.1%}")
        lines.append(f"  {'Trade Count':<20} {'':<14} {holdout.holdout_trade_count:<14}")
        lines.append("")
        if holdout.passed:
            lines.append("Verdict: PASSED holdout validation — performance held up on unseen data.")
        else:
            lines.append(f"Verdict: FAILED holdout validation — {holdout.note}")
            lines.append(
                "This strategy was NOT approved as PASS on the strength of in-sample "
                "metrics alone; treat any in-sample-only numbers above with caution."
            )
        lines.append("")

    if stress_test is not None and stress_test.windows:
        lines.append("=== STRESS TEST (historical crisis windows) ===")
        lines.append(
            f"  {'Window':<28} {'Period':<24} {'Max DD':<10} {'Return':<10} {'Trades':<8} {'Result'}"
        )
        lines.append("  " + "-" * 90)
        for w in stress_test.windows:
            period = f"{w.from_date} → {w.to_date}"
            if w.passed is None:
                dd = ret = trades = "n/a"
                verdict = f"SKIPPED ({w.note})" if w.note else "SKIPPED"
            else:
                dd = f"{w.max_drawdown:.1%}"
                ret = f"{w.total_return:.1%}"
                trades = str(w.trade_count)
                verdict = "PASS" if w.passed else f"FAIL ({w.note})"
            lines.append(f"  {w.name:<28} {period:<24} {dd:<10} {ret:<10} {trades:<8} {verdict}")
        lines.append("")
        if stress_test.passed is None:
            lines.append("Verdict: stress test inconclusive — no window had usable price data.")
        elif stress_test.passed:
            lines.append("Verdict: PASSED all evaluated stress windows.")
        else:
            lines.append(
                "Verdict: FAILED at least one stress window — this strategy would have "
                "drawn down beyond the configured threshold during a known historical shock."
            )
        lines.append("")

    if walk_forward and walk_forward.has_walk_forward:
        lines.append("=== OUT-OF-SAMPLE VALIDATION ===")
        lines.append(f"Walk-forward windows: {walk_forward.n_windows} ({walk_forward.method})")
        lines.append("Aggregation method: Median across windows")
        lines.append("")

        is_s = walk_forward.aggregated_is_metrics.get("sharpe_ratio", 0)
        oos_s = walk_forward.aggregated_oos_metrics.get("sharpe_ratio", 0)
        is_dd = walk_forward.aggregated_is_metrics.get("max_drawdown", 0)
        oos_dd = walk_forward.aggregated_oos_metrics.get("max_drawdown", 0)
        is_wr = walk_forward.aggregated_is_metrics.get("win_rate", 0)
        oos_wr = walk_forward.aggregated_oos_metrics.get("win_rate", 0)
        is_cagr = walk_forward.aggregated_is_metrics.get("cagr", 0)
        oos_cagr = walk_forward.aggregated_oos_metrics.get("cagr", 0)

        lines.append(f"  {'Metric':<20} {'In-Sample':<14} {'Out-of-Sample':<16} {'Gap':<10}")
        lines.append("  " + "-" * 60)
        lines.append(f"  {'Sharpe':<20} {is_s:<14.2f} {oos_s:<16.2f} {walk_forward.sharpe_gap:<+10.2f}")
        lines.append(f"  {'Max Drawdown':<20} {is_dd:<14.1%} {oos_dd:<16.1%} {walk_forward.max_dd_gap:<+10.1%}")
        lines.append(f"  {'Win Rate':<20} {is_wr:<14.0%} {oos_wr:<16.0%} {walk_forward.win_rate_gap:<+10.0%}")
        lines.append(f"  {'CAGR':<20} {is_cagr:<14.2%} {oos_cagr:<16.2%} {is_cagr - oos_cagr:<+10.1%}")

        gap = walk_forward.sharpe_gap
        if gap > 0.5:
            lines.append("")
            lines.append(f"Verdict: HIGH OVERFITTING RISK — Sharpe gap {gap:.2f} > 0.5")
            lines.append("Consider simplifying the strategy or adding regularization filters")
        elif gap > 0.3:
            lines.append("")
            lines.append(f"Verdict: MODERATE OVERFITTING RISK — Sharpe gap {gap:.2f}")
            lines.append("Monitor out-of-sample performance closely")
        else:
            lines.append("")
            lines.append(f"Verdict: LOW OVERFITTING RISK — Sharpe gap {gap:.2f} within acceptable range")

        lines.append("")

        lines.append("Per-Window Breakdown:")
        lines.append(f"  {'Win':<6} {'IS Sharpe':<12} {'OOS Sharpe':<12} {'IS DD':<12} {'OOS DD':<12}")
        lines.append("  " + "-" * 54)
        for w in walk_forward.windows:
            ism = w["in_sample_metrics"]
            osm = w["out_of_sample_metrics"]
            lines.append(
                f"  {w['window_id']:<6} {ism['sharpe_ratio']:<12.2f} {osm['sharpe_ratio']:<12.2f} "
                f"{ism['max_drawdown']:<11.1%} {osm['max_drawdown']:<11.1%}"
            )
        lines.append("")

    if portfolio is not None:
        lines.append("=== PORTFOLIO ANALYSIS ===")
        lines.append(f"Universe: {', '.join(portfolio.symbols)}")
        lines.append(f"Average pairwise correlation: {portfolio.avg_pairwise_correlation:.2f}")
        lines.append("")

        lines.append("Correlation Matrix:")
        syms = portfolio.symbols
        header = "  " + " " * 8 + "".join(f"{s:>10}" for s in syms)
        lines.append(header)
        for row_sym in syms:
            row = portfolio.correlation_matrix.get(row_sym, {})
            row_line = f"  {row_sym:<8}" + "".join(f"{row.get(col, 0.0):>10.2f}" for col in syms)
            lines.append(row_line)
        lines.append("")

        lines.append(
            f"Beta-Neutral Hedge Overlay (rolling {portfolio.beta_hedge_lookback_days}-day beta, "
            "analytically applied to realized returns — not a live traded hedge leg):"
        )
        lines.append(f"  {'Metric':<20} {'Raw Portfolio':<16} {'Beta-Hedged':<16}")
        lines.append("  " + "-" * 52)
        lines.append(f"  {'Sharpe':<20} {portfolio.raw_sharpe:<16.2f} {portfolio.hedged_sharpe:<16.2f}")
        lines.append(f"  {'Max Drawdown':<20} {portfolio.raw_max_drawdown:<16.1%} {portfolio.hedged_max_drawdown:<16.1%}")
        lines.append(f"  {'Annual Volatility':<20} {portfolio.raw_annual_vol:<16.1%} {portfolio.hedged_annual_vol:<16.1%}")
        lines.append("")
        lines.append(f"Most recent estimated beta to benchmark: {portfolio.final_beta_estimate:.2f}")
        lines.append(
            "A beta-neutral overlay shorts this fraction of portfolio value in the "
            "benchmark, re-estimated on a rolling basis using only prior data."
        )
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
