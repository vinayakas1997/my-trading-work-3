"""FinBERT scoring, in-process. Imports `torch` / `transformers` lazily, so merely importing this module needs neither.

Lives in vinu-infra (next to `models.py`, which owns the weights registry) so the model-serving service and a
service running without a model container (VINU_MODEL_SERVICE_URL unset) use the same code.

Weights: the shared models dir (`vinu_infra.models`, `{VINU_MODELS_DIR or data/models}/finbert`); auto-downloaded via
`ensure_model` if absent. Score in [-1, 1] = P(positive) - P(negative), plus the argmax label.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

LOG = logging.getLogger(__name__)

_lock = threading.Lock()
_tokenizer = None
_model = None


def _model_dir() -> Path:
    from vinu_infra.models import model_path

    return model_path("finbert")


def _load() -> tuple:
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model
    with _lock:
        if _model is not None:
            return _tokenizer, _model
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        local_dir = _model_dir()
        if local_dir.is_dir() and any(local_dir.iterdir()):
            source = str(local_dir)
        else:
            from vinu_infra.models import ensure_model

            source = str(ensure_model("finbert"))
        LOG.info("Loading FinBERT from %s", source)
        _tokenizer = AutoTokenizer.from_pretrained(source)
        _model = AutoModelForSequenceClassification.from_pretrained(source)
        _model.eval()
        torch.set_num_threads(1)
        return _tokenizer, _model


def _label_index(id2label: dict, name: str) -> int:
    for idx, label in id2label.items():
        if label.lower() == name:
            return idx
    raise ValueError(f"label {name!r} not found in model config id2label={id2label}")


def score_finbert_batch(texts: list[str], batch_size: int = 16) -> list[dict]:
    """One dict per input: {"finbert_label": "positive"|"negative"|"neutral", "finbert_score": float in [-1, 1]}.
    Empty / whitespace-only texts get a neutral 0.0 without running inference."""
    results: list[dict | None] = [None] * len(texts)
    scoreable_idx = [i for i, t in enumerate(texts) if t and t.strip()]
    if scoreable_idx:
        import torch

        tokenizer, model = _load()
        for start in range(0, len(scoreable_idx), batch_size):
            chunk_idx = scoreable_idx[start:start + batch_size]
            inputs = tokenizer([texts[i] for i in chunk_idx], return_tensors="pt", truncation=True,
                               max_length=512, padding=True)
            with torch.no_grad():
                probs = torch.softmax(model(**inputs).logits, dim=-1)
            id2label = model.config.id2label
            for row_i, i in enumerate(chunk_idx):
                row = probs[row_i]
                label = id2label[int(torch.argmax(row).item())].lower()
                pos = float(row[_label_index(id2label, "positive")])
                neg = float(row[_label_index(id2label, "negative")])
                results[i] = {"finbert_label": label, "finbert_score": round(pos - neg, 4)}
    return [r if r is not None else {"finbert_label": "neutral", "finbert_score": 0.0} for r in results]
