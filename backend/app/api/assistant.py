"""Endpunkt für den KI-Assistenten (Nutzeranfrage 25.09.2026: "Richtung KI-Agent, aber die

Übersicht soll bleiben") - ergänzt die bestehende Übersicht/Filter/Suche um eine zusätzliche,
rein lesende Chat-Oberfläche. Siehe app/agents/assistant.py für die eigentliche Tool-Use-Logik.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.assistant import run_assistant_chat
from app.config import settings
from app.db import get_db
from app.schemas import AssistantChatIn, AssistantChatOut
from app.serializers import tender_to_out

router = APIRouter(tags=["assistant"])


@router.post("/assistant/chat", response_model=AssistantChatOut)
def assistant_chat(payload: AssistantChatIn, db: Session = Depends(get_db)) -> AssistantChatOut:
    ergebnis = run_assistant_chat(
        db, payload.nachricht, verlauf=[m.model_dump() for m in payload.verlauf]
    )
    return AssistantChatOut(
        antwort=ergebnis.antwort,
        verfuegbar=bool(settings.anthropic_api_key),
        tenders=[tender_to_out(t) for t in ergebnis.tenders],
    )
