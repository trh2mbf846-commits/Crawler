"""Endpunkte für Crawler Kevin (Nutzeranfrage 25.09.2026: "Richtung KI-Agent, aber die

Übersicht soll bleiben" + "Kevin darf alle drei Sachen" + "proaktiv, kennt meinen Kontext").
- /assistant/chat: die Konversation (lesende Werkzeuge werden sofort ausgeführt, schreibende
  nur vorgeschlagen).
- /assistant/actions/execute: führt eine zuvor vorgeschlagene und im Frontend bestätigte
  Schreibaktion tatsächlich aus.
- /assistant/preferences (GET/PUT): Vincents Prioritäten, fließen in Kevins Systemprompt und
  den Kurzbericht ein ("Kevin soll sich in meine Position versetzen").
- /assistant/digest (GET): deterministisch berechneter täglicher Kurzbericht, den das Frontend
  beim Öffnen von Kevins Tab automatisch lädt statt dass Vincent erst fragen muss.

Siehe app/agents/assistant.py für die Tool-Use-Logik und app/agents/digest.py für den Kurzbericht.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.assistant import execute_assistant_action, run_assistant_chat
from app.agents.digest import build_daily_digest
from app.db import get_db
from app.models import AssistantPreferences
from app.schemas import (
    AssistantActionIn,
    AssistantActionOut,
    AssistantActionProposalOut,
    AssistantChatIn,
    AssistantChatOut,
    AssistantDigestOut,
    AssistantPreferencesIn,
    AssistantPreferencesOut,
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
        verfuegbar=ergebnis.verfuegbar,
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


def _get_or_create_preferences(db: Session) -> AssistantPreferences:
    praeferenzen = db.get(AssistantPreferences, "singleton")
    if praeferenzen is None:
        praeferenzen = AssistantPreferences(id="singleton")
        db.add(praeferenzen)
        db.commit()
        db.refresh(praeferenzen)
    return praeferenzen


@router.get("/assistant/preferences", response_model=AssistantPreferencesOut)
def get_preferences(db: Session = Depends(get_db)) -> AssistantPreferencesOut:
    return AssistantPreferencesOut.model_validate(_get_or_create_preferences(db), from_attributes=True)


@router.put("/assistant/preferences", response_model=AssistantPreferencesOut)
def update_preferences(payload: AssistantPreferencesIn, db: Session = Depends(get_db)) -> AssistantPreferencesOut:
    praeferenzen = _get_or_create_preferences(db)
    for feld, wert in payload.model_dump().items():
        setattr(praeferenzen, feld, wert)
    db.commit()
    db.refresh(praeferenzen)
    return AssistantPreferencesOut.model_validate(praeferenzen, from_attributes=True)


@router.get("/assistant/digest", response_model=AssistantDigestOut)
def get_digest(db: Session = Depends(get_db)) -> AssistantDigestOut:
    ergebnis = build_daily_digest(db)
    return AssistantDigestOut(
        text=ergebnis.text,
        neue_relevante_anzahl=ergebnis.neue_relevante_anzahl,
        bald_ablaufend_anzahl=ergebnis.bald_ablaufend_anzahl,
        portale_mit_problem=ergebnis.portale_mit_problem,
        tenders=[tender_to_out(t) for t in ergebnis.tenders],
    )
