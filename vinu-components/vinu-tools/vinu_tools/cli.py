"""CLI entry points for vinu-tools."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from vinu_tools.compute.feature_catalog import format_help, indicator_meta_to_dict, list_indicators
from vinu_tools.config import load_config
from vinu_tools.server.app import create_app
from vinu_tools.service import FeatureService


def _parse_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=str, default="", help="Override VINU_FEATURES_DATA_DIR")
    parser.add_argument("--meta-db", type=str, default="", help="Override VINU_FEATURES_META_DB_PATH")


def _service_from_args(args: argparse.Namespace) -> FeatureService:
    return FeatureService(
        data_dir=getattr(args, "data_dir", None) or None,
        meta_db_path=getattr(args, "meta_db", None) or None,
    )


def _print_json(obj: object) -> None:
    if hasattr(obj, "to_dict"):
        print(json.dumps(obj.to_dict(), indent=2))
    elif isinstance(obj, list):
        print(json.dumps([x.to_dict() for x in obj], indent=2))
    else:
        print(json.dumps(obj, indent=2))


def _handle_submit(args: argparse.Namespace, service: FeatureService) -> None:
    legacy = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else []
    specs = list(args.feature_specs or [])
    if legacy and specs:
        print("Use either --features or --feature, not both", file=sys.stderr)
        sys.exit(1)
    features: list[str | dict] = legacy if legacy else specs
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


def _handle_status(args: argparse.Namespace, service: FeatureService) -> None:
    if not args.id and not args.title:
        print("Provide --title or --id", file=sys.stderr)
        sys.exit(1)
    req = service.get_request(args.id) if args.id else service.get_by_title(args.title)
    if req is None:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _print_json(req)


def _handle_list(args: argparse.Namespace, service: FeatureService) -> None:
    _print_json(service.list_requests(status=args.status, title=args.title, limit=args.limit))


def _handle_worker(args: argparse.Namespace, service: FeatureService) -> None:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.loop:
        while True:
            results = service.run_worker(once=True, limit=args.limit)
            for req in results:
                logging.info(
                    "Processed request %s status=%s path=%s",
                    req.id,
                    req.status,
                    req.file_path,
                )
            time.sleep(max(1, args.interval))
    else:
        _print_json(service.run_worker(once=True, limit=args.limit))


def _handle_delete(args: argparse.Namespace, service: FeatureService) -> None:
    req = service.delete_request(args.id)
    if req is None:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _print_json(req)


def _handle_presets(args: argparse.Namespace, service: FeatureService) -> None:
    _print_json(service.list_presets())


def _handle_features(args: argparse.Namespace, service: FeatureService) -> None:
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


def _handle_factors(args: argparse.Namespace, service: FeatureService) -> None:
    if args.cmd == "list":
        factors = service.list_factors()
        if args.group:
            factors = [f for f in factors if f["group"] == args.group]
        print(f"Count: {len(factors)}")
        for f in factors:
            desc = f["description"][:60] if f.get("description") else ""
            print(f"  {f['id']:25s} [{f['group']:12s}] {desc}")
        return
    if args.cmd == "search":
        results = service.search_factors(args.query)
        print(f"Found {len(results)} results:")
        for fid in results[:20]:
            print(f"  {fid}")
        if len(results) > 20:
            print(f"  ... and {len(results) - 20} more")
        return
    if args.cmd == "spec":
        spec = service.get_factor_spec(args.factor_id)
        if spec is None:
            print(f"Unknown factor: {args.factor_id}", file=sys.stderr)
            sys.exit(1)
        _print_json(spec)
        return


def _handle_ml(args: argparse.Namespace, service: FeatureService) -> None:
    if args.cmd == "models":
        models = service.list_ml_models()
        print(f"{len(models)} models:")
        for m in models:
            print(f"  - {m}")
        return


def _handle_serve(args: argparse.Namespace, service: FeatureService) -> None:
    import uvicorn

    cfg = load_config()
    host = args.host or cfg.host
    port = args.port or cfg.port
    uvicorn.run(create_app(), host=host, port=port)


_COMMANDS: dict[str, callable] = {
    "submit": _handle_submit,
    "status": _handle_status,
    "list": _handle_list,
    "worker": _handle_worker,
    "delete": _handle_delete,
    "presets": _handle_presets,
    "features": _handle_features,
    "factors": _handle_factors,
    "ml": _handle_ml,
    "serve": _handle_serve,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vinu-tools", description="Feature run registry and worker")
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

    p_factors = sub.add_parser("factors", help="List/search/inspect alpha factors")
    p_factors_sub = p_factors.add_subparsers(dest="cmd", required=True)
    p_flist = p_factors_sub.add_parser("list", help="List all factors")
    p_flist.add_argument("--group", default=None, help="Filter by group (gtja191, alpha101, academic, fundamental)")
    p_fsearch = p_factors_sub.add_parser("search", help="Search factors by concept")
    p_fsearch.add_argument("query", help="Search query (e.g. 'short term reversal')")
    p_fspec = p_factors_sub.add_parser("spec", help="Get factor spec by ID")
    p_fspec.add_argument("factor_id", help="e.g. gtja191_001")
    _parse_data_args(p_factors)

    p_ml = sub.add_parser("ml", help="List ML models")
    p_ml_sub = p_ml.add_subparsers(dest="cmd", required=True)
    p_ml_models = p_ml_sub.add_parser("models", help="List available ML models")
    _parse_data_args(p_ml)

    p_serve = sub.add_parser("serve", help="Run HTTP API")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    _parse_data_args(p_serve)

    args = parser.parse_args(argv)
    _COMMANDS[args.command](args, _service_from_args(args))


if __name__ == "__main__":
    main()
