from __future__ import annotations

import argparse
import os


def serve_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the vinu-models model-serving API")
    parser.add_argument("--host", default=os.getenv("VINU_MODELS_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VINU_MODELS_PORT", "8096")))
    args = parser.parse_args(argv)

    import uvicorn

    from vinu_models.server.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    serve_main()
