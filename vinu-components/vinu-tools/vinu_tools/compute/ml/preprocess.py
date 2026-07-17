"""Preprocessing interface — wraps ml_models normalize."""

from vinu_tools.compute.ml.models.normalize.normalize import zscore_column


def normalize(values):
    """Z-score normalize a list of float | None values.

    Returns list of float | None, preserving None positions.
    """
    return zscore_column(values)
