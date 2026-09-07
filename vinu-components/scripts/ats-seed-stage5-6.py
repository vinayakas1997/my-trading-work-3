#!/usr/bin/env python3
"""ATS seed + stage-5/6 driver for the 6->9 lifecycle plumbing check.

Runs INSIDE the vinu-agent container (uses the real AgentService stores).
Stage 5 (the sweep verdict gate) is the only thing being bypassed, and it is
bypassed honestly: stage 5's ONLY downstream contract is "a BENCHING artifact
exists", so we create that artifact through the REAL
`write_artifact_from_research_pass` -- byte-identical to what a genuine
research PASS writes. Nothing about stages 6-9 changes whether the artifact
got there by a real PASS or by this seed.

Stage 6 (risk_gatekeeper) is then driven through its REAL hook
(`apply_risk_gatekeeper_verdict`) with a realistic APPROVED manager answer +
sizing_inputs -- because stage 6 currently has NO worker/route that ever
invokes it (a genuine gap: a real stage-5 PASS parks at BENCHING forever).
Exercising the hook directly runs 100% of the real store/ledger/position-
sizing/transition code the only thing not run is the LLM that would emit the
same JSON block.

Stages 7/8/9 are then left to the REAL running workers (capital-allocator /
shadow / trade-plan) on their cadence -- this tool does not touch them.

Usage (from vinu-components/, PowerShell):
    Get-Content scripts/ats-seed-stage5-6.py -Raw |
        docker compose exec -T agent-api python - --symbol AAPL
"""
from __future__ import annotations

import argparse
import json
import os


def _manager_block(payload: dict) -> str:
    return "verdict:\n```json\n" + json.dumps(payload) + "\n```"


def _seed_bench(store, symbol: str, run_id: str) -> str | None:
    from vinu_agent.agent.research_artifact_writer import write_artifact_from_research_pass
    code = (
        f"# ATS-seeded crossover ({symbol})\n"
        "fast, slow = 10, 30\n"
        "fast_ma = sma(close, fast)\n"
        "slow_ma = sma(close, slow)\n"
        "position = where(cross_above(fast_ma, slow_ma), 1, where(cross_below(fast_ma, slow_ma), 0, None))\n"
    )
    return write_artifact_from_research_pass(
        _manager_block({
            "verdict": "PASS", "symbol": symbol, "strategy_code": code,
            "sharpe": 1.9, "max_drawdown": -0.11, "angles_used": ["macd_cross", "trend_lifecycle"],
        }),
        strategy_store=store, source_run_id=run_id,
    )


def _drive_stage6(store, ledger, artifact_id: str, symbol: str):
    from vinu_agent.agent.risk_gatekeeper_hook import apply_risk_gatekeeper_verdict
    content = _manager_block({
        "verdict": "APPROVED", "artifact_id": artifact_id,
        "approved_size": 25000.0,
        "sizing_inputs": {
            "account_equity": 100000.0, "method": "fractional_kelly",
            "win_rate": 0.56, "payoff_ratio": 1.4, "kelly_fraction": 0.25,
            "risk_pct": 0.02, "entry_price": 0.0, "atr": 0.0, "atr_stop_multiple": 2.0,
        },
    })
    return apply_risk_gatekeeper_verdict(
        content, strategy_store=store, ticker_ledger_store=ledger,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="AAPL")
    ap.add_argument("--skip-stage6", action="store_true", help="seed BENCHING only, leave for manual stage-6")
    args = ap.parse_args()

    from vinu_agent.service import AgentService
    from vinu_research.models import ArtifactStatus

    symbol = args.symbol.upper()
    run_id = f"ats-seed-{symbol.lower()}"
    with AgentService() as service:
        store = service._strategy_store
        ledger = service.ticker_ledger
        aid = _seed_bench(store, symbol, run_id)
        if not aid:
            print(f"[ats-seed] could not create BENCHING for {symbol} (already exists?)")
            return 1
        art = store.get_artifact(aid)
        print(f"[ats-seed] {symbol} BENCHING created: {aid} status={art.status.value}")

        if not args.skip_stage6:
            got = _drive_stage6(store, ledger, aid, symbol)
            art = store.get_artifact(aid)
            print(f"[ats-seed] stage-6 hook -> {got!r}; status now={art.status.value} "
                  f"approved_size={art.approved_size}")
        print(f"[ats-seed] artifact for downstream workers: {aid} (status={art.status.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
