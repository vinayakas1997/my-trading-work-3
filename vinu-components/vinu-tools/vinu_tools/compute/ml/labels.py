"""Label creation interface — wraps ml_models labels."""

from vinu_tools.compute.ml.models.labels.labels import build_label_column


def create_label(rows, label_type: str = "forward_return_1"):
    """Build forward return labels from row data.

    Supported label_type values:
        forward_return_1, fwd_ret_1, label  →  1-bar forward return
        forward_return_5                     →  5-bar forward return

    Returns list of float | None, aligned with input rows.
    """
    return build_label_column(rows, label_type)
