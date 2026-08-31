from __future__ import annotations

from fastapi import APIRouter

from app.agents.classification import CATEGORY_ORDER

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    return CATEGORY_ORDER
