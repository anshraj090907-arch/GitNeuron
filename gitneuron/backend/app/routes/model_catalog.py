from __future__ import annotations

from fastapi import APIRouter

from app.core.model_catalog import list_models
from app.models import ModelOption

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelOption])
def get_models() -> list[ModelOption]:
    return list_models()
