"""Shared channel-independent patch-transformer core.

Used by two angles:
  - `patchtst` (20-patchtst.md): patch-embed + transformer-encode + linear
    head, used directly.
  - `lpatchtst` (23-lpatchtst.md): "LSTM + PatchTST hybrid" — LPatchTST is
    literally an LSTM branch fused with a PatchTST branch (per the spec's
    own title/explanation), so `lpatchtst/compute.py` imports
    `PatchEncoderBranch` from here as its PatchTST half rather than
    reimplementing patch-embedding + attention a second time.

Kept as one shared module (rather than duplicated) because both angles are
literally the same patching/attention core at different roles — PatchTST
uses it standalone, LPatchTST uses it as one branch of a hybrid.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


class PatchEncoderBranch(nn.Module):
    """Channel-independent patch embedding + transformer encoder.

    Input: (batch, lookback) — a single channel/variate's window (channel
    independence, per 20-patchtst.md, means channels are never mixed
    inside this module).
    Output of `forward`: (batch, n_patches, d_model) encoded patch tokens.
    `encode_flat` additionally flattens to (batch, n_patches * d_model) for
    feeding a plain linear head.
    """

    def __init__(
        self,
        lookback: int,
        patch_len: int = 8,
        stride: int = 4,
        d_model: int = 16,
        nhead: int = 2,
        num_layers: int = 1,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if lookback < patch_len:
            raise ValueError("lookback must be >= patch_len")
        self.lookback = lookback
        self.patch_len = patch_len
        self.stride = stride
        self.n_patches = (lookback - patch_len) // stride + 1
        if self.n_patches < 1:
            raise ValueError("lookback too short for given patch_len/stride")

        self.embed = nn.Linear(patch_len, d_model)
        self.pos = nn.Parameter(torch.zeros(1, self.n_patches, d_model))
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 2,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.out_dim = self.n_patches * d_model

    def _patchify(self, x: torch.Tensor) -> torch.Tensor:
        # (batch, lookback) -> (batch, n_patches, patch_len)
        return x.unfold(1, self.patch_len, self.stride)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        patches = self._patchify(x)
        tokens = self.embed(patches) + self.pos
        return self.encoder(tokens)

    def encode_flat(self, x: torch.Tensor) -> torch.Tensor:
        enc = self.forward(x)
        return enc.reshape(enc.shape[0], -1)


def make_windows(series: np.ndarray, lookback: int, horizon: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Sliding-window (X, y) pairs from a 1-D series for next-step forecasting."""
    n = len(series)
    xs, ys = [], []
    for i in range(n - lookback - horizon + 1):
        xs.append(series[i:i + lookback])
        ys.append(series[i + lookback:i + lookback + horizon])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def zscore(series: np.ndarray) -> tuple[np.ndarray, float, float]:
    mean = float(np.mean(series))
    std = float(np.std(series))
    if std < 1e-8:
        std = 1.0
    return (series - mean) / std, mean, std


def direction(forecast_return: float, eps: float = 1e-4) -> str:
    if forecast_return > eps:
        return "up"
    if forecast_return < -eps:
        return "down"
    return "flat"
