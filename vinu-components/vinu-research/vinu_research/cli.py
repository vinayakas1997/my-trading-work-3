from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

from vinu_research.config import ResearchConfig, load_config
from vinu_research.loop import StrategyResearchLoop
from vinu_research.models import IterationRecord
from vinu_research.tools import ResearchTools

LOG = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")
_KNOWN_NON_TICKERS = frozenset({
    "A", "I", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO",
    "TO", "UP", "US", "WE",
    "ALL", "AND", "ANY", "ARE", "BAD", "BEST", "BIG", "BUT", "CAN",
    "DID", "FOR", "GET", "GOOD", "HAD", "HAS", "HAVE", "HER", "HIS",
    "HOW", "ITS", "JOB", "LOT", "LOW", "MAN", "NEW", "NOT", "NOW",
    "OLD", "OUR", "OUT", "OWN", "PER", "PUT", "SAY", "SEE", "SHE",
    "TOP", "TWO", "USE", "WAS", "WAY", "WHO", "WILL", "YET", "TEST",
    "SMA", "RSI", "ADX", "MA", "MACD", "DD", "ATR", "EMA",
    "ETF", "IPO", "ROI", "PE", "EPS", "PEG", "PB", "ROE", "YTD",
    "HIGH", "LOW",
})


def _print_separator(char: str = "\u2500") -> None:
    print(char * 60)


def _on_iteration(record: IterationRecord) -> None:
    m = record.result.metrics
    print()
    _print_separator()
    print(f"[Iteration {record.iteration}] Quant Coder: Strategy generated")
    print(f"[Iteration {record.iteration}] Simulator: Sharpe={m.sharpe_ratio:.2f}, "
          f"MaxDD={m.max_drawdown:.1%}, WinRate={m.win_rate:.0%}")
    print(f"[Iteration {record.iteration}] Risk Critic: {record.critique.reasoning}")

    if record.critique.suggestions:
        print(f"[Iteration {record.iteration}] Suggestions:")
        for s in record.critique.suggestions:
            print(f"  \u2192 {s}")

    if record.critique.verdict == "PASS":
        print(f"[Iteration {record.iteration}] \u2713 VERDICT: PASS")
    elif record.critique.verdict == "STOP":
        print(f"[Iteration {record.iteration}] \u2717 VERDICT: STOP")
    else:
        print(f"[Iteration {record.iteration}] \u21bb VERDICT: REFINE")
    _print_separator()


def _validate_date(val: str | None, name: str) -> str | None:
    if val is None:
        return None
    if not _DATE_PATTERN.match(val):
        raise ValueError(
            f"Invalid {name}: '{val}'. Expected format: YYYY-MM-DD"
        )
    return val


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="vinu-research \u2014 Agentic Strategy Researcher"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the strategy research loop")
    run_p.add_argument("idea", help="Strategy idea (e.g. 'test SMA20/SMA50 crossover on AAPL')")
    run_p.add_argument("--symbol", default=None, help="Ticker symbol (extracted from idea if not set)")
    run_p.add_argument(
        "--universe", default=None,
        help="Comma-separated tickers to backtest as a portfolio (e.g. AAPL,MSFT,GOOGL). "
             "The same strategy runs on each symbol and results are aggregated into one "
             "portfolio, with a correlation matrix and beta-hedge overlay in the report.",
    )
    run_p.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD)")
    run_p.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD)")
    run_p.add_argument("--max-iterations", type=int, default=None, help="Max research iterations")
    run_p.add_argument("--indicators", default=None, help="Comma-separated indicator kinds")
    run_p.add_argument("--capital", type=float, default=None, help="Initial capital")
    run_p.add_argument("--approve", action="store_true", help="Approve strategy automatically (non-interactive)")
    run_p.add_argument("--llm", action="store_true", help="Enable LLM-enhanced risk analysis")
    run_p.add_argument("--no-llm", action="store_true", help="Disable LLM-enhanced risk analysis")
    run_p.add_argument("--walk-forward", action="store_true", help="Enable walk-forward validation")
    run_p.add_argument("--wf-method", default=None, help="Walk-forward method: expanding or sliding")
    run_p.add_argument("--wf-windows", type=int, default=None, help="Number of walk-forward windows")
    run_p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    run_p.set_defaults(func=run_main)

    list_p = sub.add_parser("recipes", help="List available strategy recipes")
    list_p.set_defaults(func=recipes_main)

    return parser.parse_args(argv)


def _extract_symbol(idea: str) -> str | None:
    words = _TICKER_PATTERN.findall(idea.upper())
    candidates = [t for t in words if t not in _KNOWN_NON_TICKERS]
    if not candidates:
        return None
    candidates.sort(key=lambda x: -len(x))
    return candidates[0]


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_") or "strategy"


def run_main(args: argparse.Namespace) -> None:
    config = load_config()
    overrides: dict[str, Any] = {}
    if args.max_iterations is not None:
        overrides["max_iterations"] = args.max_iterations
    if args.capital is not None:
        overrides["initial_capital"] = args.capital
    if args.llm:
        overrides["llm_enabled"] = True
    if args.no_llm:
        overrides["llm_enabled"] = False
    if args.walk_forward:
        overrides["walk_forward_enabled"] = True
    if args.wf_method is not None:
        overrides["walk_forward_method"] = args.wf_method
    if args.wf_windows is not None:
        overrides["walk_forward_windows"] = args.wf_windows
    if overrides:
        config = ResearchConfig(**{**config.__dict__, **overrides})

    symbol = args.symbol or _extract_symbol(args.idea) or "AAPL"
    symbol = symbol.upper()

    from_date = _validate_date(args.from_date, "--from") or "2024-01-01"
    to_date = _validate_date(args.to_date, "--to") or "2024-12-31"

    indicators: list[str] | None = None
    if args.indicators:
        indicators = [k.strip().lower() for k in args.indicators.split(",") if k.strip()]

    universe: list[str] | None = None
    if getattr(args, "universe", None):
        universe = [t.strip().upper() for t in args.universe.split(",") if t.strip()]

    tools = ResearchTools(config)

    on_iteration = None if args.quiet else _on_iteration
    loop = StrategyResearchLoop(
        tools=tools,
        config=config,
        on_iteration=on_iteration,
    )

    print(f"[vinu-research] Strategy: {args.idea}")
    print(f"[vinu-research] Ticker: {symbol}")
    print(f"[vinu-research] Period: {from_date} \u2192 {to_date}")
    print(f"[vinu-research] Max iterations: {config.max_iterations}")
    if indicators:
        print(f"[vinu-research] Indicators: {', '.join(indicators)}")
    if universe and len(set(universe)) > 1:
        print(f"[vinu-research] Universe: {', '.join(universe)}")
    if config.walk_forward_enabled:
        print(f"[vinu-research] Walk-forward: enabled ({config.walk_forward_method}, {config.walk_forward_windows} windows)")
    _print_separator()

    try:
        result = asyncio.run(
            loop.run(
                user_idea=args.idea,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                indicators=indicators,
                initial_capital=config.initial_capital,
                universe=universe,
            )
        )
    except KeyboardInterrupt:
        print("\n[vinu-research] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[vinu-research] Error: {e}")
        LOG.exception("Research loop failed")
        sys.exit(1)
    finally:
        asyncio.run(tools.close())

    print()
    print(result.report_md)

    saved_path = None
    if result.best_result:
        safe_sym = _sanitize_filename(symbol.lower())
        safe_name = _sanitize_filename(result.best_result.strategy_name.lower())
        output_path = Path("output") / f"{safe_sym}_{safe_name}.py"
        best_rec = next(
            (r for r in result.iterations if r.iteration == result.best_iteration),
            result.iterations[-1] if result.iterations else None,
        )
        if best_rec:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(best_rec.strategy_code)
            saved_path = output_path
            print(f"\nOptimized Strategy Code: saved to {output_path}")

    _print_separator()
    approved = bool(args.approve) if hasattr(args, "approve") else False
    if not approved and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        try:
            resp = input("\nApprove this strategy for use? [y/N] ").strip().lower()
            approved = resp in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            pass
    if approved:
        print("[vinu-research] \u2713 Strategy approved")
        if saved_path:
            approved_path = saved_path.parent / f"{saved_path.stem}_approved.py"
            saved_path.rename(approved_path)
            print(f"[vinu-research] Approved strategy saved to {approved_path}")
    else:
        print("[vinu-research] Strategy saved but not approved (run with --approve or re-run later)")


def recipes_main(args: argparse.Namespace) -> None:
    from vinu_research.generator import list_recipes
    print("Available strategy recipes:")
    for r in list_recipes():
        print(f"  - {r}")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARN,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    if hasattr(args, "func"):
        args.func(args)
    else:
        _parse_args(["--help"])
