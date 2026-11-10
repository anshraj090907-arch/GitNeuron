from __future__ import annotations

from fastapi import APIRouter

from app.core.templates import list_templates
from app.models import Template

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[Template])
def get_templates() -> list[Template]:
    return list_templates()
