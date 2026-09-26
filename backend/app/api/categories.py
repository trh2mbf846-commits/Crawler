from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.classification import CATEGORY_ORDER
from app.db import get_db
from app.themen import aktive_themen

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)) -> list[str]:
    # Feste Grundkategorien + vom Nutzer gepflegte Themen (app/themen.py).
    return CATEGORY_ORDER + [t.name for t in aktive_themen(db) if t.name not in CATEGORY_ORDER]
