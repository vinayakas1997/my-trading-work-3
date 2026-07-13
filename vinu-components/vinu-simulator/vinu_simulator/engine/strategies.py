from __future__ import annotations

from typing import Any

import pandas as pd


class BaseStrategy:
    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.generate_weights is BaseStrategy.generate_weights:
            raise TypeError(
                f"Class {cls.__name__} must override generate_weights method"
            )
