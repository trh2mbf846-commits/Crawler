"""KI-Assistent (Nutzeranfrage 25.09.2026: "Richtung KI-Agent, aber die Übersicht soll bleiben").

Ergänzt die bestehende Übersicht/Filter/Suche (Kapitel 11) um eine zusätzliche, rein lesende
Chat-Oberfläche: Vincent stellt eine Frage in natürlicher Sprache ("zeig mir alle KI-relevanten
Ausschreibungen in Bayern mit Frist in den nächsten 14 Tagen"), Claude entscheidet per Tool-Use,
welche der beiden Werkzeuge (Ausschreibungssuche, Quellstatus) es dafür braucht, ruft sie über die
bereits bestehende, geprüfte Such-/Health-Logik ab und fasst das Ergebnis zusammen. Bewusst KEINE
schreibenden Werkzeuge (kein Auto-Anstoßen eines Laufs, kein Ändern von Datensätzen) - der
Assistent ergänzt die Übersicht, ersetzt sie nicht, und trifft keine eigenständigen Aktionen ohne
menschliche Bestätigung.

Ohne konfigurierten ANTHROPIC_API_KEY liefert run_assistant_chat(...) einen klaren Hinweis statt
eines Fehlers (gleiches Prinzip wie call_llm_json in app/prompts.py) - die restliche Anwendung
bleibt davon unberührt.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Portal, Tender
from app.serializers import portal_to_health_out
from app.tender_queries import search_tenders

logger = logging.getLogger("ausschreibungscrawler.assistant")

MAX_TOOL_ITERATIONEN = 5
MAX_SUCHTREFFER = 20
_NICHT_KONFIGURIERT_HINWEIS = (
    "Der KI-Assistent ist nicht konfiguriert (kein ANTHROPIC_API_KEY hinterlegt). Nutze in der "
    "Zwischenzeit die normale Suche/Filter in der Übersicht."
)
_NICHT_ERREICHBAR_HINWEIS = "Der KI-Assistent ist gerade nicht erreichbar. Bitte versuche es später erneut."
_ZU_KOMPLEX_HINWEIS = "Die Anfrage war zu komplex, um sie in der verfügbaren Zeit zu beantworten. Bitte präzisiere die Frage."

SYSTEM_TEMPLATE = (
    "Du bist der KI-Assistent des Ausschreibungs-Crawlers (Kapitel 17-25 der Handlungsanweisung, "
    '"Search Agent Operating System"). Du beantwortest Fragen von Vincent zu erfassten '
    "öffentlichen Ausschreibungen und zum Status der Datenquellen.\n\n"
    "Regeln:\n"
    "- Antworte ausschließlich auf Basis der Werkzeug-Ergebnisse. Erfinde keine Ausschreibungen, "
    "Fristen oder Details, die nicht in den Werkzeug-Ergebnissen stehen.\n"
    "- Nenne bei Treffern Titel und Vergabestelle, keine internen IDs im Fließtext.\n"
    "- KI-Relevanz-Einstufungen sind automatische Schätzungen, keine gesicherten Aussagen "
    "(Kapitel 20.4) - formuliere entsprechend vorsichtig.\n"
    "- Wenn eine Frage mit den Werkzeugen nicht beantwortbar ist, sag das ehrlich statt zu "
    "spekulieren.\n"
    "- Antworte auf Deutsch, prägnant, ohne Floskeln.\n\n"
    "Aktuell aktive Portale (Slug - Name):\n{portale}"
)

TOOLS = [
    {
        "name": "suche_ausschreibungen",
        "description": (
            "Durchsucht die erfassten Ausschreibungen nach Stichwort, Portal, Kategorie, "
            "KI-Relevanz, Angebotsfrist und Status. Liefert eine Trefferliste (max. 20) sowie "
            "die Gesamttrefferzahl."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Freitextsuche in Titel/Kurzbeschreibung/Vergabestelle"},
                "portal_slugs": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Einer oder mehrere Portal-Slugs aus der Liste im Systemprompt",
                },
                "kategorien": {"type": "array", "items": {"type": "string"}},
                "ki_relevanz_min": {"type": "string", "enum": ["nicht", "moeglich", "stark"]},
                "frist_bis": {"type": "string", "description": "ISO-Datum YYYY-MM-DD - nur Ausschreibungen mit Angebotsfrist bis zu diesem Datum"},
                "status": {"type": "string", "enum": ["neu", "aktualisiert", "unveraendert", "vergeben", "abgelaufen"]},
                "sort": {"type": "string", "enum": ["ranking", "frist", "veroeffentlichung"]},
                "limit": {"type": "integer", "description": "Max. Anzahl Treffer (1-20), Standard 10"},
            },
        },
    },
    {
        "name": "quellstatus",
        "description": (
            "Liefert den aktuellen Status aller konfigurierten Portale (aktiv/inaktiv, "
            "Ampel grün/gelb/rot, letzte Trefferzahl, gleitende Fehlerrate)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


@dataclass
class AssistantResult:
    antwort: str
    tenders: list[Tender] = field(default_factory=list)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _build_system_prompt(db: Session) -> str:
    portale = db.scalars(select(Portal).where(Portal.aktiv.is_(True)).order_by(Portal.name)).all()
    zeilen = "\n".join(f"- {p.slug}: {p.name}" for p in portale)
    return SYSTEM_TEMPLATE.format(portale=zeilen or "(keine aktiven Portale)")


def _tool_suche_ausschreibungen(db: Session, tool_input: dict, gefundene: dict[str, Tender]) -> dict:
    limit = max(1, min(int(tool_input.get("limit") or 10), MAX_SUCHTREFFER))
    items, total = search_tenders(
        db,
        q=tool_input.get("q"),
        portal=tool_input.get("portal_slugs"),
        kategorie=tool_input.get("kategorien"),
        ki_relevanz_min=tool_input.get("ki_relevanz_min"),
        frist_bis=_parse_iso_date(tool_input.get("frist_bis")),
        status=tool_input.get("status"),
        sort=tool_input.get("sort") or "ranking",
        page=1,
        page_size=limit,
    )
    for t in items:
        gefundene[t.id] = t
    return {
        "gesamttreffer": total,
        "treffer": [
            {
                "id": t.id,
                "titel": t.titel,
                "vergabestelle": t.vergabestelle,
                "portal": t.portal.name,
                "angebotsfrist": t.angebotsfrist.isoformat() if t.angebotsfrist else None,
                "ki_relevanz": t.ki_relevanz_score,
                "kurzbeschreibung": (t.kurzbeschreibung or "")[:200],
            }
            for t in items
        ],
    }


def _tool_quellstatus(db: Session) -> dict:
    portale = db.scalars(select(Portal).order_by(Portal.name)).all()
    ausgabe = []
    for p in portale:
        health = portal_to_health_out(db, p)
        ausgabe.append({
            "name": p.name,
            "aktiv": p.aktiv,
            "status_ampel": health.status_ampel,
            "letzte_trefferzahl": health.letzte_trefferzahl,
            "fehlerrate_gleitend": health.fehlerrate_gleitend,
            "meldung": health.meldung,
        })
    return {"portale": ausgabe}


def _execute_tool(db: Session, name: str, tool_input: dict, gefundene: dict[str, Tender]) -> dict:
    if name == "suche_ausschreibungen":
        return _tool_suche_ausschreibungen(db, tool_input, gefundene)
    if name == "quellstatus":
        return _tool_quellstatus(db)
    return {"fehler": f"Unbekanntes Werkzeug: {name}"}


def run_assistant_chat(
    db: Session, nachricht: str, verlauf: list[dict] | None = None, client=None
) -> AssistantResult:
    if client is None:
        if not settings.anthropic_api_key:
            return AssistantResult(_NICHT_KONFIGURIERT_HINWEIS)
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = []
    for eintrag in verlauf or []:
        rolle = "assistant" if eintrag.get("rolle") == "assistant" else "user"
        messages.append({"role": rolle, "content": eintrag.get("text", "")})
    messages.append({"role": "user", "content": nachricht})

    system = _build_system_prompt(db)
    gefundene_tenders: dict[str, Tender] = {}

    try:
        for _ in range(MAX_TOOL_ITERATIONEN):
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                text = "".join(block.text for block in response.content if hasattr(block, "text"))
                return AssistantResult(text or "(keine Antwort)", list(gefundene_tenders.values()))

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                ergebnis = _execute_tool(db, block.name, block.input, gefundene_tenders)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(ergebnis, ensure_ascii=False, default=str),
                })
            messages.append({"role": "user", "content": tool_results})

        return AssistantResult(_ZU_KOMPLEX_HINWEIS, list(gefundene_tenders.values()))
    except Exception:
        logger.exception("KI-Assistent: Anfrage fehlgeschlagen")
        return AssistantResult(_NICHT_ERREICHBAR_HINWEIS)
