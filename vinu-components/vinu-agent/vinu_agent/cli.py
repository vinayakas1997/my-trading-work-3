import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from vinu_lib.debug import setup_logging

from .broker.alpaca import AlpacaBroker
from .broker.kill_switch import halt_trading, is_trading_halted, resume_trading
from .broker.mandate import DEFAULT_MANDATE_PATH, TradingMandate
from .config import load_config
from .service import AgentService


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="vinu-agent", description="Vinu Agent CLI")
    sub = parser.add_subparsers(dest="command")

    # ── chat ──
    chat_p = sub.add_parser("chat", help="Start an interactive chat session")
    chat_p.add_argument("--session", "-s", default="", help="Session ID to resume")

    # ── send ──
    send_p = sub.add_parser("send", help="Send a message to a session")
    send_p.add_argument("session_id", help="Session ID")
    send_p.add_argument("message", help="Message content")

    # ── serve ──
    serve_p = sub.add_parser("serve", help="Start the FastAPI server")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8086)

    # ── broker ──
    broker_p = sub.add_parser("broker", help="Broker operations")
    broker_sub = broker_p.add_subparsers(dest="broker_cmd")
    broker_sub.add_parser("status", help="Show account, positions, and open orders")
    broker_sub.add_parser("halt", help="Activate kill switch — block all trading")
    broker_sub.add_parser("resume", help="Deactivate kill switch — resume trading")

    # ── channel ──
    channel_p = sub.add_parser("channel", help="Channel operations")
    channel_sub = channel_p.add_subparsers(dest="channel_cmd")
    channel_sub.add_parser("list", help="List configured channels")
    ch_send = channel_sub.add_parser("send", help="Send a message to a channel")
    ch_send.add_argument("channel_name", help="Channel name (telegram, discord)")
    ch_send.add_argument("chat_id", help="Target chat ID")
    ch_send.add_argument("message", help="Message text")

    # ── swarm ──
    swarm_p = sub.add_parser("swarm", help="Swarm operations")
    swarm_sub = swarm_p.add_subparsers(dest="swarm_cmd")
    swarm_sub.add_parser("list", help="List available swarm presets")
    sw_run = swarm_sub.add_parser("run", help="Run a swarm preset")
    sw_run.add_argument("preset", help="Preset name")
    sw_run.add_argument("--vars", nargs="*", default=[], help="User variables key=val")

    # ── memory ──
    memory_p = sub.add_parser("memory", help="Memory operations")
    memory_sub = memory_p.add_subparsers(dest="memory_cmd")
    mem_search = memory_sub.add_parser("search", help="Search agent memory")
    mem_search.add_argument("query", help="Search query")

    # ── mandate ──
    mandate_p = sub.add_parser("mandate", help="Trading mandate operations")
    mandate_sub = mandate_p.add_subparsers(dest="mandate_cmd")
    mandate_sub.add_parser("show", help="Show current trading mandate")
    mandate_set = mandate_sub.add_parser("set", help="Set a mandate value")
    mandate_set.add_argument("key", help="Mandate field name")
    mandate_set.add_argument("value", help="New value (JSON-encoded)")

    return parser.parse_args(argv)


async def _chat_loop(session_id: str = "") -> None:
    async with AgentService() as svc:
        if session_id:
            session = svc._store.get_session(session_id)
            if not session:
                print(f"Session {session_id} not found")
                return
        else:
            session = await svc.create_session(title="CLI Chat")
            print(f"Session: {session.session_id}")

        print("Type /quit to exit, /cancel to cancel current run")
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\n> ").strip()
                )
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/cancel":
                svc.cancel(session.session_id)
                print("[cancelled]")
                continue

            result = await svc.send_message(session.session_id, line)
            print(f"\n[{result.get('attempt_id', '')}]")
            await asyncio.sleep(0.5)
            messages = svc._store.get_messages(session.session_id, limit=2)
            for m in reversed(messages):
                if m.role == "assistant":
                    print(f"\n{m.content}")


async def _cmd_broker(args) -> None:
    broker = AlpacaBroker()
    if not broker.is_configured():
        print('{"status": "error", "error": "Alpaca API not configured"}')
        return

    if args.broker_cmd == "halt":
        halt_trading()
        print('{"status": "ok", "message": "Trading halted"}')
        return

    if args.broker_cmd == "resume":
        resume_trading()
        print('{"status": "ok", "message": "Trading resumed"}')
        return

    result = {
        "kill_switch_active": is_trading_halted(),
    }
    try:
        account = broker.get_account()
        result["account"] = {
            "status": account.status,
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
            "buying_power": account.buying_power,
            "equity": account.equity,
        }
        positions = broker.get_positions()
        result["positions"] = [
            {"symbol": p.symbol, "qty": p.qty, "market_value": p.market_value, "unrealized_pl": p.unrealized_pl}
            for p in positions
        ]
        orders = broker.get_orders()
        result["open_orders"] = [
            {"id": o.order_id, "symbol": o.symbol, "side": o.side, "type": o.type, "status": o.status, "qty": o.qty}
            for o in orders
        ]
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, indent=2))


def _cmd_channel(args) -> None:
    if args.channel_cmd == "list":
        print(json.dumps({
            "channels": [
                {"name": "telegram", "configured": bool(__import__("os").environ.get("TELEGRAM_TOKEN", ""))},
                {"name": "discord", "configured": bool(__import__("os").environ.get("DISCORD_TOKEN", ""))},
            ]
        }, indent=2))
    elif args.channel_cmd == "send":
        print(json.dumps({
            "status": "not_implemented",
            "message": "Channel send requires a running bot. Use the API instead.",
        }))


async def _cmd_swarm(args) -> None:
    async with AgentService() as svc:
        runtime = svc.swarm_runtime()
        if args.swarm_cmd == "list":
            presets = runtime.list_presets()
            print(json.dumps(presets, indent=2))
        elif args.swarm_cmd == "run":
            user_vars = {}
            for v in args.vars:
                if "=" in v:
                    k, val = v.split("=", 1)
                    user_vars[k] = val
            run = runtime.create_run(args.preset, user_vars)
            run = runtime.start_run(run.run_id)
            print(json.dumps({
                "run_id": run.run_id,
                "preset": args.preset,
                "status": run.status.value,
            }, indent=2))


def _cmd_mandate(args) -> None:
    if args.mandate_cmd == "show":
        mandate = TradingMandate.load()
        print(json.dumps(mandate.to_dict(), indent=2))
    elif args.mandate_cmd == "set":
        mandate = TradingMandate.load()
        key = args.key
        val = args.value
        if hasattr(mandate, key):
            current = getattr(mandate, key)
            if isinstance(current, bool):
                setattr(mandate, key, val.lower() in ("true", "1", "yes"))
            elif isinstance(current, (int, float)):
                setattr(mandate, key, type(current)(val))
            elif isinstance(current, set):
                if val.startswith("[") or val.startswith('"'):
                    setattr(mandate, key, set(json.loads(val)))
                else:
                    setattr(mandate, key, {val})
            else:
                setattr(mandate, key, val)
            DEFAULT_MANDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            DEFAULT_MANDATE_PATH.write_text(
                yaml.dump(mandate.to_dict(), default_flow_style=False),
                encoding="utf-8",
            )
            print(json.dumps({"status": "ok", "key": key, "value": getattr(mandate, key)}))
        else:
            print(json.dumps({"status": "error", "error": f"Unknown mandate field: {key}"}))


def main() -> None:
    setup_logging("agent")
    args = _parse_args()
    if args.command == "serve":
        from .server.app import run
        run(host=args.host, port=args.port)
    elif args.command == "chat":
        asyncio.run(_chat_loop(session_id=args.session))
    elif args.command == "send":
        async def _send():
            async with AgentService() as svc:
                result = await svc.send_message(args.session_id, args.message)
                print(json.dumps(result, indent=2))
        asyncio.run(_send())
    elif args.command == "broker":
        async def _broker():
            await _cmd_broker(args)
        asyncio.run(_broker())
    elif args.command == "channel":
        _cmd_channel(args)
    elif args.command == "swarm":
        asyncio.run(_cmd_swarm(args))
    elif args.command == "mandate":
        _cmd_mandate(args)
    else:
        _parse_args(["--help"])


if __name__ == "__main__":
    main()
