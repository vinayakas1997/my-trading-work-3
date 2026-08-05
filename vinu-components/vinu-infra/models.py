"""Download pretrained model weights into a shared, gitignored models dir.

Replaces the old split handling: FinBERT was baked into the vinu-news Docker
image at build time, and Chronos/TimesFM were downloaded live into a tmpfs
cache that is wiped on every container restart (re-downloading ~1.4GB each
time). Now every downloadable pretrained model is fetched once into
`{VINU_MODELS_DIR or <components>/data/models}/<model>/` by this module's
`download_models()` / `ensure_model()` and served from disk at runtime.

Only models that actually have downloadable weights are registered here;
models with no public weights (TimeGPT is a paid API; PatchFormer/FinCast/
FinMamba) are intentionally absent — the angles that reference them keep
their honest `fallback_proxy` backend. Note: `kronos` needs its companion
tokenizer (`kronos-tokenizer`) downloaded too, and the Kronos model code is
vendored into the kronos angle's `_kronos_model/` package (MIT license).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: name -> Hugging Face Hub repo id. Subdir on disk = the key.
MODELS: dict[str, str] = {
    "finbert": "ProsusAI/finbert",
    "chronos-t5-tiny": "amazon/chronos-t5-tiny",
    "timesfm-2.5-200m-pytorch": "google/timesfm-2.5-200m-pytorch",
    "timer-timerxl": "thuml/timer-base-84m",
    "kronos": "NeoQuasar/Kronos-base",
    "kronos-tokenizer": "NeoQuasar/Kronos-Tokenizer-base",
    # Weights-only entries below are download-ready (folder prepped via
    # `make models`) but their loaders are NOT wired: each requires a shared-env
    # change (moirai -> uni2ts downgrades torch; moment -> momentfm fails to
    # build on Py3.12; lag-llama -> gluonts downgrades pandas + needs repo
    # code). Their angles keep the honest fallback_proxy backend by decision.
    "moirai": "Salesforce/moirai-1.0-R-small",
    "moment": "autonlab/MOMENT-1-small",
    "lag-llama": "time-series-foundation-models/Lag-Llama",
}


def models_dir() -> Path:
    """Resolve the shared models directory.

    Order: $VINU_MODELS_DIR, else <components>/data/models (walk up from this
    file's package location to the vinu-components root), else ./data/models.
    """
    env = __import__("os").environ.get("VINU_MODELS_DIR", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "vinu-infra").is_dir() and (parent / "vinu-news").is_dir():
            return parent / "data" / "models"
    return Path("data/models")


def model_path(name: str) -> Path:
    if name not in MODELS:
        raise ValueError(
            f"Unknown model: {name!r}. Known: {', '.join(sorted(MODELS))}"
        )
    return models_dir() / name


def is_downloaded(name: str) -> bool:
    """True if the model's local dir exists and is non-empty."""
    path = model_path(name)
    return path.is_dir() and any(path.iterdir())


def ensure_model(name: str, *, quiet: bool = False) -> Path:
    """Return the local path for `name`, downloading it first if absent."""
    path = model_path(name)
    if is_downloaded(name):
        return path
    repo_id = MODELS[name]
    if not quiet:
        print(f"[models] downloading {name} <- {repo_id} -> {path}", flush=True)
    from huggingface_hub import snapshot_download

    path.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=repo_id, local_dir=str(path))
    return path


def download_models(names: list[str] | None = None, *, quiet: bool = False) -> dict[str, Path]:
    """Download all (or the given) models. Returns {name: path}."""
    target = names or sorted(MODELS)
    result: dict[str, Path] = {}
    for name in target:
        try:
            result[name] = ensure_model(name, quiet=quiet)
        except Exception as exc:  # pragma: no cover - network/env dependent
            print(f"[models] FAILED {name}: {exc!r}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download pretrained model weights into the shared models dir."
    )
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="Model name to download; repeatable. Default: all.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List known models and their download status, then exit.",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Override the models directory (default: $VINU_MODELS_DIR or data/models).",
    )
    args = parser.parse_args(argv)

    if args.dir:
        import os

        os.environ["VINU_MODELS_DIR"] = args.dir

    if args.list:
        root = models_dir()
        print(f"Models dir: {root}")
        for name in sorted(MODELS):
            status = "downloaded" if is_downloaded(name) else "missing"
            print(f"  {name:28s} {status}  <- {MODELS[name]}")
        return 0

    download_models(names=args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
