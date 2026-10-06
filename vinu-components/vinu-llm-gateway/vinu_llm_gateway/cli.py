from __future__ import annotations

import argparse

from vinu_infra.debug import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(prog="vinu-llm-gateway")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()
    setup_logging("llm-gateway")
    import uvicorn

    from vinu_llm_gateway.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
