"""CLI entry points for vinu-features."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from vinu_features.config import load_config
from vinu_features.server.app import create_app
from vinu_features.service import FeatureService


def _parse_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=str, default="", help="Override VINU_FEATURES_DATA_DIR")
    parser.add_argument("--meta-db", type=str, default="", help="Override VINU_FEATURES_META_DB_PATH")


def _apply_env_overrides(args: argparse.Namespace) -> None:
    import os

    if getattr(args, "data_dir", None) and args.data_dir:
        os.environ["VINU_FEATURES_DATA_DIR"] = args.data_dir
    if getattr(args, "meta_db", None) and args.meta_db:
        os.environ["VINU_FEATURES_META_DB_PATH"] = args.meta_db


def _print_json(obj: object) -> None:
    if hasattr(obj, "to_dict"):
        print(json.dumps(obj.to_dict(), indent=2))
    elif isinstance(obj, list):
        print(json.dumps([x.to_dict() for x in obj], indent=2))
    else:
        print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vinu-features", description="Feature run registry and worker")
    sub = parser.add_subparsers(dest="command", required=True)

    p_submit = sub.add_parser("submit", help="Submit a feature run request")
    p_submit.add_argument("--title", required=True)
    p_submit.add_argument("--symbols", required=True, help="Comma-separated tickers")
    p_submit.add_argument("--days", type=int, default=365)
    p_submit.add_argument("--from-ts", type=int, default=None)
    p_submit.add_argument("--to-ts", type=int, default=None)
    p_submit.add_argument("--interval", default="1d")
    p_submit.add_argument("--preset", default=None)
    p_submit.add_argument("--features", default="", help="Comma-separated legacy feature names")
    p_submit.add_argument(
        "--feature",
        action="append",
        default=[],
        dest="feature_specs",
        help="Structured feature spec, e.g. rsi:period=20 (repeatable)",
    )
    p_submit.add_argument("--conditions", default=None)
    p_submit.add_argument("--run", action="store_true", help="Process immediately after submit")
    _parse_data_args(p_submit)

    p_status = sub.add_parser("status", help="Get request by title or id")
    p_status.add_argument("--title", default=None)
    p_status.add_argument("--id", type=int, default=None)
    _parse_data_args(p_status)

    p_list = sub.add_parser("list", help="List feature requests")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--title", default=None)
    p_list.add_argument("--limit", type=int, default=100)
    _parse_data_args(p_list)

    p_worker = sub.add_parser("worker", help="Process pending feature requests")
    mode = p_worker.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    p_worker.add_argument("--limit", type=int, default=1)
    p_worker.add_argument("--interval", type=int, default=5)
    p_worker.add_argument("--verbose", action="store_true")
    _parse_data_args(p_worker)

    p_delete = sub.add_parser("delete", help="Delete a feature run")
    p_delete.add_argument("--id", type=int, required=True)
    _parse_data_args(p_delete)

    p_presets = sub.add_parser("presets", help="List preset blueprints")
    _parse_data_args(p_presets)

    p_features = sub.add_parser("features", help="List indicators and feature help")
    p_features_sub = p_features.add_subparsers(dest="features_cmd", required=True)
    p_features_list = p_features_sub.add_parser("list", help="List indicators and presets")
    p_features_list.add_argument("--format", choices=("text", "json"), default="text")
    p_features_help = p_features_sub.add_parser("help", help="Help for one indicator kind")
    p_features_help.add_argument("kind", nargs="?", default=None)
    _parse_data_args(p_features)

    p_serve = sub.add_parser("serve", help="Run HTTP API")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    _parse_data_args(p_serve)

    args = parser.parse_args(argv)
    _apply_env_overrides(args)

    if args.command == "submit":
        legacy = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else []
        specs = list(args.feature_specs or [])
        if legacy and specs:
            print("Use either --features or --feature, not both", file=sys.stderr)
            sys.exit(1)
        features: list[str | dict] = legacy if legacy else specs
        with FeatureService() as service:
            req = service.submit(
                title=args.title,
                symbols=[s.strip() for s in args.symbols.split(",") if s.strip()],
                from_ts=args.from_ts,
                to_ts=args.to_ts,
                days=args.days,
                interval=args.interval,
                preset=args.preset,
                features=features,
                conditions=args.conditions,
                run_immediately=args.run,
            )
            _print_json(req)
        return

    if args.command == "status":
        if not args.id and not args.title:
            print("Provide --title or --id", file=sys.stderr)
            sys.exit(1)
        with FeatureService() as service:
            req = service.get_request(args.id) if args.id else service.get_by_title(args.title)
            if req is None:
                print("Not found", file=sys.stderr)
                sys.exit(1)
            _print_json(req)
        return

    if args.command == "list":
        with FeatureService() as service:
            _print_json(service.list_requests(status=args.status, title=args.title, limit=args.limit))
        return

    if args.command == "worker":
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

        def run_batch() -> list[object]:
            with FeatureService() as service:
                return service.run_worker(once=True, limit=args.limit)

        if args.loop:
            while True:
                results = run_batch()
                for req in results:
                    logging.info(
                        "Processed request %s status=%s path=%s",
                        req.id,
                        req.status,
                        req.file_path,
                    )
                time.sleep(max(1, args.interval))
        else:
            _print_json(run_batch())
        return

    if args.command == "delete":
        with FeatureService() as service:
            req = service.delete_request(args.id)
            if req is None:
                print("Not found", file=sys.stderr)
                sys.exit(1)
            _print_json(req)
        return

    if args.command == "presets":
        with FeatureService() as service:
            _print_json(service.list_presets())
        return

    if args.command == "features":
        from vinu_features.compute.feature_catalog import format_help, indicator_meta_to_dict, list_indicators

        if args.features_cmd == "list":
            if args.format == "json":
                _print_json([indicator_meta_to_dict(m) for m in list_indicators()])
            else:
                print(format_help(None))
            return
        if args.features_cmd == "help":
            try:
                print(format_help(args.kind))
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)
            return

    if args.command == "serve":
        import uvicorn

        cfg = load_config()
        host = args.host or cfg.host
        port = args.port or cfg.port
        uvicorn.run(create_app(), host=host, port=port)
        return


if __name__ == "__main__":
    main()
