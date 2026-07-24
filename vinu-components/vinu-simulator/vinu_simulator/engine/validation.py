from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def block_bootstrap_permutation(
    trade_pnls: list[float],
    actual_sharpe: float,
    block_size: int = 5,
    n_iterations: int = 1000,
    periods_per_year: float = 252.0,
    initial_capital: float = 1_000_000.0,
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Circular block bootstrap of trade P&Ls.

    Resamples blocks of consecutive trades (preserving local dependence),
    recomputes Sharpe on each resampled sequence, and returns the fraction
    of resampled Sharpes >= actual_sharpe as a p-value. This is a more
    rigorous null than full i.i.d. shuffling when trade P&Ls are autocorrelated.

    Uses circular blocks so the start and end of the trade sequence can
    wrap into the same block, avoiding edge bias.
    """
    if len(trade_pnls) < 3:
        return {
            "p_value": 1.0,
            "sim_mean": 0.0,
            "sim_std": 0.0,
            "sim_p5": 0.0,
            "sim_p95": 0.0,
            "n_iterations": 0,
            "n_trades": len(trade_pnls),
            "minimum_met": False,
        }
    if block_size < 1:
        block_size = 1

    rng = rng or np.random.default_rng()
    pnl_array = np.array(trade_pnls, dtype=float)
    n = len(pnl_array)
    sim_sharpes = np.zeros(n_iterations)

    for i in range(n_iterations):
        n_blocks = int(np.ceil(n / block_size))
        indices: list[int] = []
        for _ in range(n_blocks):
            start = rng.integers(0, n)
            for j in range(block_size):
                indices.append((start + j) % n)
        sampled = pnl_array[indices[:n]]

        equity = initial_capital + np.cumsum(sampled)
        equity = np.maximum(equity, 1e-12)
        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])

        if len(returns) < 2 or np.std(returns) == 0:
            sim_sharpes[i] = 0.0
        else:
            sim_sharpes[i] = float(np.mean(returns) / np.std(returns) * np.sqrt(periods_per_year))

    p_value = float(np.mean(sim_sharpes >= actual_sharpe))

    return {
        "p_value": p_value,
        "sim_mean": float(np.mean(sim_sharpes)),
        "sim_std": float(np.std(sim_sharpes)),
        "sim_p5": float(np.percentile(sim_sharpes, 5)),
        "sim_p95": float(np.percentile(sim_sharpes, 95)),
        "n_iterations": n_iterations,
        "n_trades": n,
        "block_size": block_size,
        "minimum_met": True,
    }


def price_path_resample(
    daily_returns: pd.Series,
    actual_sharpe: float,
    block_size: int = 20,
    n_iterations: int = 1000,
    periods_per_year: float = 252.0,
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Block-bootstrap the daily return series and recompute Sharpe on each path.

    Tests whether the observed Sharpe ratio is distinguishable from what
    arises from the autocorrelation and volatility structure of price
    changes alone — a different null than trade-order permutation.
    """
    if len(daily_returns) < block_size * 2:
        return {
            "p_value": 1.0,
            "sim_mean": 0.0,
            "sim_std": 0.0,
            "sim_p5": 0.0,
            "sim_p95": 0.0,
            "n_iterations": 0,
            "n_observations": len(daily_returns),
            "minimum_met": False,
        }

    rng = rng or np.random.default_rng()
    returns = daily_returns.values
    n = len(returns)
    sim_sharpes = np.zeros(n_iterations)

    for i in range(n_iterations):
        n_blocks = int(np.ceil(n / block_size))
        indices: list[int] = []
        for _ in range(n_blocks):
            start = rng.integers(0, n)
            for j in range(block_size):
                indices.append((start + j) % n)
        sampled = returns[indices[:n]]

        if np.std(sampled) == 0 or periods_per_year <= 0:
            sim_sharpes[i] = 0.0
        else:
            sim_sharpes[i] = float(np.mean(sampled) / np.std(sampled) * np.sqrt(periods_per_year))

    p_value = float(np.mean(sim_sharpes >= actual_sharpe))

    return {
        "p_value": p_value,
        "sim_mean": float(np.mean(sim_sharpes)),
        "sim_std": float(np.std(sim_sharpes)),
        "sim_p5": float(np.percentile(sim_sharpes, 5)),
        "sim_p95": float(np.percentile(sim_sharpes, 95)),
        "n_iterations": n_iterations,
        "n_observations": n,
        "block_size": block_size,
        "minimum_met": True,
    }


def compute_validation_verdict(
    validation: dict[str, dict[str, float]],
) -> dict[str, bool | list[str]]:
    """Combine all sub-results into one documented pass/fail verdict.

    Rules:
    - monte_carlo.p_value < 0.05
    - block_bootstrap.p_value < 0.05
    - price_path.p_value < 0.10  (slightly looser — tougher null)
    - walk_forward.consistency_rate >= 0.6
    - bootstrap.ci_low > 0       (Sharpe 95% CI lower bound above zero)
    """
    reasons: list[str] = []
    all_passed = True
    any_method_ran = False

    for method, key, threshold, label in [
        ("monte_carlo", "p_value", 0.05, "Trade-permutation p-value"),
        ("block_bootstrap", "p_value", 0.05, "Block-bootstrap p-value"),
        ("price_path", "p_value", 0.10, "Price-path resample p-value"),
    ]:
        sub = validation.get(method, {})
        if not sub.get("minimum_met", False):
            reasons.append(f"{label}: insufficient data (skipped)")
            continue
        any_method_ran = True
        val = sub.get(key, 1.0)
        if val < threshold:
            reasons.append(f"{label} {val:.4f} < {threshold} (PASS)")
        else:
            reasons.append(f"{label} {val:.4f} >= {threshold} (FAIL)")
            all_passed = False

    wf = validation.get("walk_forward", {})
    if wf.get("minimum_met", False):
        any_method_ran = True
        cr = wf.get("consistency_rate", 0.0)
        if cr >= 0.6:
            reasons.append(f"Walk-forward consistency {cr:.2f} >= 0.60 (PASS)")
        else:
            reasons.append(f"Walk-forward consistency {cr:.2f} < 0.60 (FAIL)")
            all_passed = False
    else:
        reasons.append("Walk-forward consistency: insufficient data (skipped)")

    bs = validation.get("bootstrap", {})
    if bs.get("minimum_met", False):
        any_method_ran = True
        ci_low = bs.get("ci_low", 0.0)
        if ci_low > 0:
            reasons.append(f"Bootstrap Sharpe CI lower bound {ci_low:.4f} > 0 (PASS)")
        else:
            reasons.append(f"Bootstrap Sharpe CI lower bound {ci_low:.4f} <= 0 (FAIL)")
            all_passed = False
    else:
        reasons.append("Bootstrap Sharpe CI: insufficient data (skipped)")

    if not any_method_ran:
        all_passed = False
        reasons.append(
            "No validation method had sufficient data to run — cannot confirm "
            "statistical significance; treating as not-yet-validated (fail-closed)."
        )

    return {
        "passed": all_passed,
        "reasons": reasons,
    }


def monte_carlo_permutation(
    trade_pnls: list[float],
    actual_sharpe: float,
    initial_capital: float = 1_000_000.0,
    n_iterations: int = 1000,
    periods_per_year: float = 252.0,
) -> dict[str, float]:
    if len(trade_pnls) < 3:
        return {
            "p_value": 1.0,
            "sim_mean": 0.0,
            "sim_std": 0.0,
            "sim_p5": 0.0,
            "sim_p95": 0.0,
            "n_iterations": 0,
            "n_trades": len(trade_pnls),
            "minimum_met": False,
        }

    pnl_array = np.array(trade_pnls, dtype=float)
    sim_sharpes = np.zeros(n_iterations)

    for i in range(n_iterations):
        shuffled = np.random.permutation(pnl_array)
        equity = initial_capital + np.cumsum(shuffled)
        
        # Capping equity at a very small positive number to prevent negative or zero division
        equity = np.maximum(equity, 1e-12)
        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])
        
        if len(returns) < 2 or np.std(returns) == 0:
            sim_sharpes[i] = 0.0
        else:
            sim_sharpes[i] = float(np.mean(returns) / np.std(returns) * np.sqrt(periods_per_year))

    p_value = float(np.mean(sim_sharpes >= actual_sharpe))

    return {
        "p_value": p_value,
        "sim_mean": float(np.mean(sim_sharpes)),
        "sim_std": float(np.std(sim_sharpes)),
        "sim_p5": float(np.percentile(sim_sharpes, 5)),
        "sim_p95": float(np.percentile(sim_sharpes, 95)),
        "n_iterations": n_iterations,
        "n_trades": len(trade_pnls),
        "minimum_met": True,
    }


def bootstrap_sharpe_ci(
    daily_returns: pd.Series,
    n_iterations: int = 1000,
    periods_per_year: float = 252.0,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    if len(daily_returns) < 5:
        return {
            "ci_low": 0.0,
            "ci_high": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "n_iterations": 0,
            "n_observations": len(daily_returns),
            "minimum_met": False,
        }

    returns = daily_returns.values
    if periods_per_year <= 0:
        rf_daily = 0.0
    else:
        rf_daily = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = returns - rf_daily

    n = len(returns)
    boot_sharpes = np.zeros(n_iterations)

    for i in range(n_iterations):
        sample = np.random.choice(excess, size=n, replace=True)
        if np.std(sample) == 0:
            boot_sharpes[i] = 0.0
        else:
            # Prevent standard error calculation standard deviation zero
            std_val = np.std(sample)
            if std_val == 0 or periods_per_year <= 0:
                boot_sharpes[i] = 0.0
            else:
                boot_sharpes[i] = float(np.mean(sample) / std_val * np.sqrt(periods_per_year))

    return {
        "ci_low": float(np.percentile(boot_sharpes, 2.5)),
        "ci_high": float(np.percentile(boot_sharpes, 97.5)),
        "mean": float(np.mean(boot_sharpes)),
        "std": float(np.std(boot_sharpes)),
        "n_iterations": n_iterations,
        "n_observations": n,
        "minimum_met": True,
    }


def walk_forward_consistency(
    equity_curve: pd.Series,
    n_windows: int = 5,
    periods_per_year: float = 252.0,
) -> dict[str, float]:
    if len(equity_curve) < n_windows * 2 or n_windows <= 0:
        return {
            "profitable_windows": 0,
            "total_windows": 0,
            "consistency_rate": 0.0,
            "minimum_met": False,
        }

    window_size = len(equity_curve) // n_windows
    window_returns: list[float] = []
    window_sharpes: list[float] = []

    for i in range(n_windows):
        start = i * window_size
        end = start + window_size if i < n_windows - 1 else len(equity_curve)
        segment = equity_curve.iloc[start:end]
        seg_returns = segment.pct_change().dropna()
        if len(seg_returns) < 2:
            continue

        window_return = float((segment.iloc[-1] / segment.iloc[0]) - 1) if segment.iloc[0] > 0 else 0.0
        window_sharpe = (
            float(seg_returns.mean() / seg_returns.std() * np.sqrt(periods_per_year))
            if seg_returns.std() > 0 and periods_per_year > 0
            else 0.0
        )

        window_returns.append(window_return)
        window_sharpes.append(window_sharpe)

    profitable = sum(1 for r in window_returns if r > 0)
    total = len(window_returns)

    return {
        "profitable_windows": profitable,
        "total_windows": total,
        "consistency_rate": profitable / total if total > 0 else 0.0,
        "return_mean": float(np.mean(window_returns)) if window_returns else 0.0,
        "return_std": float(np.std(window_returns)) if len(window_returns) > 1 else 0.0,
        "sharpe_mean": float(np.mean(window_sharpes)) if window_sharpes else 0.0,
        "sharpe_std": float(np.std(window_sharpes)) if len(window_sharpes) > 1 else 0.0,
        "minimum_met": True,
    }
