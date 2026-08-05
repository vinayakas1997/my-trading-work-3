"""FinBERT-based sentiment scoring.

Why this exists: `sentiment.py`'s `score_sentiment()` is a rule-based
keyword/lexicon tally (-N..+N int score). Empirical testing (news-analysis-
code/07_robustness_and_direction.py) showed that score has ZERO usable
directional value even on articles independently confirmed to have moved
price — sentiment-agrees-with-actual-direction rate was consistently
*below* a 50% coin flip, on both AAPL and TSLA, and confirmed with pooled
data (n=209) too. That's a feature-quality ceiling, not a sample-size
problem — more data made the estimate more precise, not more favorable.

FinBERT (ProsusAI/finbert) is a BERT model fine-tuned on financial text
specifically for 3-way sentiment classification (positive/negative/
neutral), and is the standard reference model for this exact task. This
module scores headline+summary text and returns a continuous score in
[-1, 1] (P(positive) - P(negative)) plus the argmax label, intended to
replace `sentiment_score` as the feature fed into direction-prediction
work — NOT to replace the existing rule-based `sentiment`/`sentiment_score`
columns used elsewhere (impact classification, priority, etc.), which stay
as-is to avoid disturbing existing behavior.

Model loading: weights live in the shared models dir
(`vinu-infra/models.py` — `{VINU_MODELS_DIR or data/models}/finbert`),
downloaded once via `vinu-models` / `make models` and mounted read-only
into the container at serve time. The model is no longer baked into the
Docker image, and there is no writable HF cache to wipe on restart. If the
local dir is missing, `ensure_model` auto-downloads it (fallback path).
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

LOG = logging.getLogger(__name__)


def _model_dir() -> Path:
    from vinu_infra.models import model_path

    return model_path("finbert")


_lock = threading.Lock()
_tokenizer = None
_model = None


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
        torch.set_num_threads(1)  # container is limited to 1 cpu; avoid thread thrash
        return _tokenizer, _model


def score_finbert_batch(texts: list[str], batch_size: int = 16) -> list[dict]:
    """Score a batch of texts. Returns one dict per input:
    {"finbert_label": "positive"|"negative"|"neutral", "finbert_score": float in [-1, 1]}
    Empty/whitespace-only texts get a neutral 0.0 score without running inference.
    """
    import torch

    tokenizer, model = _load()
    results: list[dict] = [None] * len(texts)  # type: ignore[list-item]

    scoreable_idx = [i for i, t in enumerate(texts) if t and t.strip()]
    for start in range(0, len(scoreable_idx), batch_size):
        chunk_idx = scoreable_idx[start:start + batch_size]
        chunk_texts = [texts[i] for i in chunk_idx]
        inputs = tokenizer(chunk_texts, return_tensors="pt", truncation=True, max_length=512, padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        # ProsusAI/finbert label order: 0=positive, 1=negative, 2=neutral
        id2label = model.config.id2label
        for row_i, i in enumerate(chunk_idx):
            row = probs[row_i]
            label_idx = int(torch.argmax(row).item())
            label = id2label[label_idx].lower()
            pos = float(row[_label_index(id2label, "positive")])
            neg = float(row[_label_index(id2label, "negative")])
            results[i] = {"finbert_label": label, "finbert_score": round(pos - neg, 4)}

    for i, t in enumerate(texts):
        if results[i] is None:
            results[i] = {"finbert_label": "neutral", "finbert_score": 0.0}
    return results


def score_finbert(text: str) -> dict:
    return score_finbert_batch([text])[0]


def _label_index(id2label: dict, name: str) -> int:
    for idx, label in id2label.items():
        if label.lower() == name:
            return idx
    raise ValueError(f"label {name!r} not found in model config id2label={id2label}")
