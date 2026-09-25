"""Entscheidungs-Posteingang (Kapitel 17.2, 21.4, 23)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Escalation, Job
from app.schemas import EscalationOut, EscalationResolveIn

router = APIRouter(tags=["escalations"])


@router.get("/escalations", response_model=list[EscalationOut])
def list_escalations(status: str | None = Query(None), db: Session = Depends(get_db)) -> list[EscalationOut]:
    query = select(Escalation).order_by(Escalation.erstellt_am.desc())
    if status:
        query = query.where(Escalation.status == status)
    return list(db.scalars(query))


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationOut)
def resolve_escalation(escalation_id: str, body: EscalationResolveIn, db: Session = Depends(get_db)) -> EscalationOut:
    escalation = db.get(Escalation, escalation_id)
    if escalation is None:
        raise HTTPException(404, "Eskalation nicht gefunden.")
    escalation.status = "beantwortet"
    escalation.entscheidung = body.entscheidung
    escalation.beantwortet_am = datetime.utcnow()

    if escalation.job_id:
        job = db.get(Job, escalation.job_id)
        if job is not None:
            job.status = "resumed"
    db.commit()
    db.refresh(escalation)
    return escalation
