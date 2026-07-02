"""HTTP routes for feature catalog."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vinu_features.compute.feature_catalog import format_help, indicator_meta_to_dict, list_indicators
from vinu_features.server.schemas import FeatureCatalogResponse, IndicatorMetaOut

router = APIRouter(tags=["catalog"])


@router.get("/features", response_model=FeatureCatalogResponse)
def list_features() -> FeatureCatalogResponse:
    data = [IndicatorMetaOut(**indicator_meta_to_dict(m)) for m in list_indicators()]
    return FeatureCatalogResponse(count=len(data), data=data)


@router.get("/features/{kind}", response_model=IndicatorMetaOut)
def get_feature(kind: str) -> IndicatorMetaOut:
    from vinu_features.compute.feature_catalog import get_indicator

    try:
        meta = get_indicator(kind)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    out = IndicatorMetaOut(**indicator_meta_to_dict(meta))
    out.help_text = format_help(kind)
    return out
