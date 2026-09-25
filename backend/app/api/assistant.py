"""Endpunkte für Crawler Kevin (Nutzeranfrage 25.09.2026: "Richtung KI-Agent, aber die

Übersicht soll bleiben" + "Kevin darf alle drei Sachen"). Zwei Endpunkte: /assistant/chat für
die Konversation (lesende Werkzeuge werden sofort ausgeführt, schreibende nur vorgeschlagen) und
/assistant/actions/execute, das einen zuvor vorgeschlagenen und im Frontend bestätigten Schreib-
vorgang tatsächlich ausführt. Siehe app/agents/assistant.py für die eigentliche Tool-Use-Logik.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.assistant import execute_assistant_action, run_assistant_chat
from app.config import settings
from app.db import get_db
from app.schemas import (
    AssistantActionIn,
    AssistantActionOut,
    AssistantActionProposalOut,
    AssistantChatIn,
    AssistantChatOut,
)
from app.serializers import tender_to_out

router = APIRouter(tags=["assistant"])


@router.post("/assistant/chat", response_model=AssistantChatOut)
def assistant_chat(payload: AssistantChatIn, db: Session = Depends(get_db)) -> AssistantChatOut:
    ergebnis = run_assistant_chat(
        db, payload.nachricht, verlauf=[m.model_dump() for m in payload.verlauf]
    )
    vorschlag = (
        AssistantActionProposalOut(
            name=ergebnis.vorschlag.name, input=ergebnis.vorschlag.input, beschreibung=ergebnis.vorschlag.beschreibung
        )
        if ergebnis.vorschlag
        else None
    )
    return AssistantChatOut(
        antwort=ergebnis.antwort,
        verfuegbar=bool(settings.anthropic_api_key),
        tenders=[tender_to_out(t) for t in ergebnis.tenders],
        vorschlag=vorschlag,
    )


@router.post("/assistant/actions/execute", response_model=AssistantActionOut)
def assistant_execute_action(payload: AssistantActionIn, db: Session = Depends(get_db)) -> AssistantActionOut:
    """Führt eine von Kevin vorgeschlagene Aktion aus - wird nur nach expliziter Bestätigung im

    Frontend aufgerufen (Nutzeranfrage: kein selbstständiges Handeln ohne Rückfrage).
    """
    ergebnis = execute_assistant_action(db, payload.name, payload.input)
    return AssistantActionOut(erfolg=ergebnis.erfolg, meldung=ergebnis.meldung)
