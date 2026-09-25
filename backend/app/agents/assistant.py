"""Crawler Kevin, der KI-Assistent des Crawlers (Nutzeranfrage 25.09.2026: "Richtung KI-Agent,

aber die Übersicht soll bleiben" + "nennen wir ihn Crawler Kevin").

Ergänzt die bestehende Übersicht/Filter/Suche (Kapitel 11) um eine zusätzliche Chat-Oberfläche:
Vincent stellt eine Frage in natürlicher Sprache ("zeig mir alle KI-relevanten Ausschreibungen
in Bayern mit Frist in den nächsten 14 Tagen"), Claude entscheidet per Tool-Use, welches Werkzeug
es dafür braucht, ruft es über die bereits bestehende, geprüfte Such-/Health-/Aktions-Logik ab und
fasst das Ergebnis zusammen.

Zwei Werkzeug-Arten (Nutzeranfrage 25.09.2026 "Kevin darf alle drei Sachen"):
- LESEND (suche_ausschreibungen, quellstatus): werden sofort ausgeführt, das Ergebnis fließt
  direkt in Kevins Antwort ein.
- SCHREIBEND (aktualisieren_starten, suchprofil_anlegen, ausschreibung_merken): werden NICHT
  automatisch ausgeführt. Sobald Kevin eines davon aufruft, bricht die Tool-Schleife ab und die
  Aktion wird Vincent als Vorschlag mit Klartext-Beschreibung vorgelegt (siehe AssistantResult.
  vorschlag) - erst ein expliziter Bestätigungsklick im Frontend führt sie über
  execute_assistant_action(...) wirklich aus. Kevin trifft also nie selbstständig eine Aktion mit
  echter Wirkung (ausgelöster Portal-Lauf, neues Suchprofil, geänderter Datensatz).

Zwei austauschbare Sprachmodell-Anbieter mit identischen Werkzeugen und identischer
Bestätigungslogik (settings.kevin_anbieter, Default "auto"):
- Claude über die Anthropic API, wenn CRAWLER_ANTHROPIC_API_KEY gesetzt ist (kostet pro Anfrage).
- Sonst ein lokales Modell über Ollama (Nutzerwunsch 25.09.2026: "Kevins Antworten kostenlos"),
  angesprochen über Ollamas native /api/chat-Schnittstelle mit Tool-Calling. Läuft Ollama nicht
  oder fehlt das Modell, liefert Kevin einen konkreten Hinweis, wie das zu beheben ist, statt
  eines Fehlers - die restliche Anwendung bleibt davon unberührt.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AssistantPreferences, Category, Portal, SearchProfile, Tender
from app.serializers import portal_to_health_out
from app.tender_queries import search_tenders

logger = logging.getLogger("ausschreibungscrawler.assistant")

MAX_TOOL_ITERATIONEN = 5
MAX_SUCHTREFFER = 20
_NICHT_KONFIGURIERT_HINWEIS = (
    "Crawler Kevin ist nicht konfiguriert (Anbieter Claude gewählt, aber kein ANTHROPIC_API_KEY "
    "hinterlegt - kostenlose Alternative: CRAWLER_KEVIN_ANBIETER=ollama). Nutze in der "
    "Zwischenzeit die normale Suche/Filter in der Übersicht."
)
_OLLAMA_NICHT_GESTARTET_HINWEIS = (
    "Crawler Kevin nutzt ein kostenloses lokales Sprachmodell über Ollama, aber Ollama läuft gerade "
    "nicht. Bitte die Ollama-App öffnen (oder von https://ollama.com installieren) und die Frage "
    "erneut stellen."
)
_OLLAMA_MODELL_FEHLT_HINWEIS = (
    "Das Sprachmodell „{modell}“ ist in Ollama noch nicht heruntergeladen. Einfach den Crawler neu "
    "starten (das Startskript lädt es automatisch) oder im Terminal ausführen: ollama pull {modell}"
)
_NICHT_ERREICHBAR_HINWEIS = "Crawler Kevin ist gerade nicht erreichbar. Bitte versuche es später erneut."
_ZU_KOMPLEX_HINWEIS = "Die Anfrage war zu komplex, um sie in der verfügbaren Zeit zu beantworten. Bitte präzisiere die Frage."

SYSTEM_TEMPLATE = (
    'Du bist "Crawler Kevin", der KI-Kollege im Ausschreibungs-Crawler (Kapitel 17-25 der '
    'Handlungsanweisung, "Search Agent Operating System"). Du beantwortest Fragen von Vincent zu '
    "erfassten öffentlichen Ausschreibungen und zum Status der Datenquellen. Stell dich nur vor, "
    "wenn danach gefragt wird - sonst antworte direkt in der Sache.\n\n"
    "Regeln:\n"
    "- Antworte ausschließlich auf Basis der Werkzeug-Ergebnisse. Erfinde keine Ausschreibungen, "
    "Fristen oder Details, die nicht in den Werkzeug-Ergebnissen stehen.\n"
    "- Nenne bei Treffern Titel und Vergabestelle, keine internen IDs im Fließtext.\n"
    "- KI-Relevanz-Einstufungen sind automatische Schätzungen, keine gesicherten Aussagen "
    "(Kapitel 20.4) - formuliere entsprechend vorsichtig.\n"
    "- Wenn eine Frage mit den Werkzeugen nicht beantwortbar ist, sag das ehrlich statt zu "
    "spekulieren.\n"
    "- Antworte auf Deutsch, prägnant, ohne Floskeln.\n"
    "- Du darfst aktualisieren_starten, suchprofil_anlegen und ausschreibung_merken aufrufen, "
    "wenn Vincent danach fragt oder es offensichtlich sinnvoll ist - diese werden ihm aber immer "
    "erst zur Bestätigung vorgelegt, du führst sie nie direkt aus. Rufe pro Antwort höchstens "
    "eines dieser drei Werkzeuge auf.\n\n"
    "Vincents Prioritäten (versetze dich in seine Position, wenn du Treffer einordnest oder "
    "Vorschläge machst - ohne dass er das jedes Mal wiederholen muss):\n{prioritaeten}\n\n"
    "Heute ist {heute} - rechne relative Angaben wie \"in den nächsten 14 Tagen\" von diesem "
    "Datum aus in ein ISO-Datum (YYYY-MM-DD) um.\n\n"
    "Aktuell aktive Portale (Slug - Name):\n{portale}\n\n"
    "Kategorien (für den Filter kategorien exakt so schreiben):\n{kategorien}"
)
_KEINE_PRIORITAETEN_HINWEIS = "(noch keine hinterlegt - frag ihn gerne danach, oder er trägt sie unter „Präferenzen“ ein)"

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
    {
        "name": "dokumente_lesen",
        "description": (
            "Liest den extrahierten Volltext der Vergabeunterlagen (PDF) einer Ausschreibung - "
            "z. B. um Details zu beantworten, die nicht in der Kurzbeschreibung stehen. "
            "tender_id muss aus einem vorherigen suche_ausschreibungen-Ergebnis stammen. Nicht "
            "jedes Dokument hat einen Volltext (kein PDF, Download/Parsing fehlgeschlagen, oder "
            "nur die ersten paar Dokumente je Ausschreibung werden ausgewertet)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"tender_id": {"type": "string"}},
            "required": ["tender_id"],
        },
    },
]

# Schreibende Werkzeuge - werden NIE direkt ausgeführt (siehe Moduldocstring), sondern lösen
# einen Vorschlag aus, den Vincent im Frontend bestätigen oder ablehnen kann.
WRITE_TOOLS = [
    {
        "name": "aktualisieren_starten",
        "description": (
            "Stößt einen Aktualisieren-Lauf an, der neue Ausschreibungen von den Portalen holt "
            "(kann mehrere Minuten dauern). Entweder ein einzelnes Portal (portal_slug) oder, "
            "wenn weggelassen, alle aktiven Portale parallel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "portal_slug": {"type": "string", "description": "Slug eines einzelnen Portals aus der Liste im Systemprompt - weglassen für alle aktiven Portale"},
            },
        },
    },
    {
        "name": "suchprofil_anlegen",
        "description": "Legt ein neues gespeichertes Suchprofil an (erscheint danach unter 'Suchprofile' in der Übersicht).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name des Suchprofils"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "portal_slugs": {"type": "array", "items": {"type": "string"}, "description": "Auf diese Portale beschränken, leer lassen für alle"},
                "ki_relevanz_min": {"type": "string", "enum": ["moeglich", "stark"]},
                "region": {"type": "string"},
                "mindestwert": {"type": "number"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ausschreibung_merken",
        "description": "Markiert eine Ausschreibung als gemerkt/interessant, optional mit Notiz. tender_id muss aus einem vorherigen suche_ausschreibungen-Ergebnis stammen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tender_id": {"type": "string"},
                "notiz": {"type": "string"},
            },
            "required": ["tender_id"],
        },
    },
]
_WRITE_TOOL_NAMEN = {t["name"] for t in WRITE_TOOLS}
ALLE_TOOLS = TOOLS + WRITE_TOOLS


@dataclass
class AssistantActionProposal:
    name: str
    input: dict
    beschreibung: str


@dataclass
class AssistantResult:
    antwort: str
    tenders: list[Tender] = field(default_factory=list)
    vorschlag: AssistantActionProposal | None = None
    verfuegbar: bool = True


@dataclass
class AssistantActionResult:
    erfolg: bool
    meldung: str


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _formatiere_prioritaeten(praeferenzen: AssistantPreferences | None) -> str:
    if praeferenzen is None:
        return _KEINE_PRIORITAETEN_HINWEIS
    teile = []
    if praeferenzen.prioritaeten_text:
        teile.append(praeferenzen.prioritaeten_text)
    if praeferenzen.bevorzugte_kategorien:
        teile.append(f"Bevorzugte Kategorien: {', '.join(praeferenzen.bevorzugte_kategorien)}")
    if praeferenzen.bevorzugte_regionen:
        teile.append(f"Bevorzugte Regionen: {', '.join(praeferenzen.bevorzugte_regionen)}")
    if praeferenzen.mindestwert is not None:
        teile.append(f"Mindestwert: {praeferenzen.mindestwert:,.0f} €")
    return "\n".join(f"- {t}" for t in teile) if teile else _KEINE_PRIORITAETEN_HINWEIS


def _build_system_prompt(db: Session) -> str:
    portale = db.scalars(select(Portal).where(Portal.aktiv.is_(True)).order_by(Portal.name)).all()
    zeilen = "\n".join(f"- {p.slug}: {p.name}" for p in portale)
    praeferenzen = db.get(AssistantPreferences, "singleton")
    return SYSTEM_TEMPLATE.format(
        heute=date.today().isoformat(),
        portale=zeilen or "(keine aktiven Portale)",
        kategorien="\n".join(f"- {name}" for name in _kategorie_namen(db)) or "(keine)",
        prioritaeten=_formatiere_prioritaeten(praeferenzen),
    )


def _kategorie_namen(db: Session) -> list[str]:
    return list(db.scalars(select(Category.name).order_by(Category.name)).all())


def _ordne_kategorien_zu(db: Session, angefragt: list[str] | None) -> tuple[list[str] | None, list[str]]:
    """Ordnet ungefähre Kategorienamen den echten zu ("KI" -> "KI & Machine Learning").

    Sprachmodelle (vor allem kleine lokale) schreiben Kategorien oft nicht exakt - ein exakter
    Filter lieferte dann stillschweigend 0 Treffer. Nicht zuordenbare Namen werden weggelassen und
    zurückgemeldet, statt die ganze Suche leer laufen zu lassen.
    """
    if not angefragt:
        return None, []
    echte = _kategorie_namen(db)
    zugeordnet: list[str] = []
    unbekannt: list[str] = []
    for name in angefragt:
        suche = str(name).strip().lower()
        treffer = [k for k in echte if k.lower() == suche] or [k for k in echte if suche and suche in k.lower()]
        if treffer:
            zugeordnet.extend(k for k in treffer if k not in zugeordnet)
        else:
            unbekannt.append(str(name))
    return (zugeordnet or None), unbekannt


def _tool_suche_ausschreibungen(db: Session, tool_input: dict, gefundene: dict[str, Tender]) -> dict:
    limit = max(1, min(int(tool_input.get("limit") or 10), MAX_SUCHTREFFER))
    kategorien, unbekannte_kategorien = _ordne_kategorien_zu(db, tool_input.get("kategorien"))
    items, total = search_tenders(
        db,
        q=tool_input.get("q"),
        portal=tool_input.get("portal_slugs"),
        kategorie=kategorien,
        ki_relevanz_min=tool_input.get("ki_relevanz_min"),
        frist_bis=_parse_iso_date(tool_input.get("frist_bis")),
        status=tool_input.get("status"),
        sort=tool_input.get("sort") or "ranking",
        page=1,
        page_size=limit,
    )
    for t in items:
        gefundene[t.id] = t
    hinweise = {}
    if unbekannte_kategorien:
        hinweise["ignorierte_unbekannte_kategorien"] = unbekannte_kategorien
    if total == 0 and any(tool_input.get(k) for k in ("q", "kategorien", "ki_relevanz_min", "frist_bis", "status", "portal_slugs")):
        hinweise["hinweis"] = "Keine Treffer mit diesen Filtern - ggf. mit weniger Filtern erneut suchen."
    return {
        **hinweise,
        "gesamttreffer": total,
        "treffer": [
            {
                "id": t.id,
                "titel": t.titel,
                "vergabestelle": t.vergabestelle,
                "portal": t.portal.name,
                "angebotsfrist": t.angebotsfrist.isoformat() if t.angebotsfrist else None,
                "ki_relevanz": t.ki_relevanz_score,
                "kategorien": [tk.category.name for tk in t.kategorien],
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


_DOKUMENT_AUSZUG_ZEICHEN = 3000


def _tool_dokumente_lesen(db: Session, tool_input: dict) -> dict:
    tender = db.get(Tender, tool_input.get("tender_id"))
    if tender is None:
        return {"fehler": "Ausschreibung nicht gefunden."}
    dokumente = [
        {
            "titel": d.titel,
            "url": d.url,
            "volltext_auszug": d.volltext[:_DOKUMENT_AUSZUG_ZEICHEN] if d.volltext else None,
            "hinweis": None if d.volltext else "Kein Volltext verfügbar für dieses Dokument.",
        }
        for d in tender.dokumente
    ]
    return {"titel": tender.titel, "dokumente": dokumente}


def _execute_tool(db: Session, name: str, tool_input: dict, gefundene: dict[str, Tender]) -> dict:
    if name == "suche_ausschreibungen":
        return _tool_suche_ausschreibungen(db, tool_input, gefundene)
    if name == "quellstatus":
        return _tool_quellstatus(db)
    if name == "dokumente_lesen":
        return _tool_dokumente_lesen(db, tool_input)
    return {"fehler": f"Unbekanntes Werkzeug: {name}"}


def _portal_von_slug(db: Session, slug: str) -> Portal | None:
    return db.scalars(select(Portal).where(Portal.slug == slug)).first()


def _beschreibe_aktion(db: Session, name: str, tool_input: dict) -> str:
    if name == "aktualisieren_starten":
        slug = tool_input.get("portal_slug")
        if not slug:
            return "Kevin möchte einen Aktualisieren-Lauf für alle aktiven Portale starten."
        portal = _portal_von_slug(db, slug)
        ziel = portal.name if portal else slug
        return f"Kevin möchte einen Aktualisieren-Lauf für „{ziel}“ starten."
    if name == "suchprofil_anlegen":
        return f"Kevin möchte das Suchprofil „{tool_input.get('name', '(ohne Namen)')}“ anlegen."
    if name == "ausschreibung_merken":
        tender = db.get(Tender, tool_input.get("tender_id"))
        titel = tender.titel if tender else tool_input.get("tender_id", "(unbekannt)")
        return f"Kevin möchte die Ausschreibung „{titel}“ merken."
    return f"Kevin möchte das Werkzeug „{name}“ ausführen."


def kevin_anbieter() -> str:
    """Welcher Sprachmodell-Anbieter tatsächlich genutzt wird: "anthropic" oder "ollama"."""
    gewuenscht = (settings.kevin_anbieter or "auto").strip().lower()
    if gewuenscht in ("anthropic", "ollama"):
        return gewuenscht
    return "anthropic" if settings.anthropic_api_key else "ollama"


def run_assistant_chat(
    db: Session, nachricht: str, verlauf: list[dict] | None = None, client=None, ollama_http=None
) -> AssistantResult:
    if client is None and kevin_anbieter() == "ollama":
        return _run_ollama_chat(db, nachricht, verlauf, ollama_http)
    if client is None:
        if not settings.anthropic_api_key:
            return AssistantResult(_NICHT_KONFIGURIERT_HINWEIS, verfuegbar=False)
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
                tools=ALLE_TOOLS,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                text = "".join(block.text for block in response.content if hasattr(block, "text"))
                return AssistantResult(text or "(keine Antwort)", list(gefundene_tenders.values()))

            text_bisher = "".join(block.text for block in response.content if hasattr(block, "text"))
            schreibender_block = next(
                (
                    block for block in response.content
                    if getattr(block, "type", None) == "tool_use" and block.name in _WRITE_TOOL_NAMEN
                ),
                None,
            )
            if schreibender_block is not None:
                # Nie direkt ausführen (siehe Moduldocstring) - Schleife hier abbrechen und den
                # Vorschlag zur Bestätigung zurückgeben, auch wenn dieselbe Antwort noch weitere
                # (ggf. lesende) tool_use-Blöcke enthielte.
                vorschlag = AssistantActionProposal(
                    name=schreibender_block.name,
                    input=schreibender_block.input,
                    beschreibung=_beschreibe_aktion(db, schreibender_block.name, schreibender_block.input),
                )
                return AssistantResult(
                    text_bisher or vorschlag.beschreibung, list(gefundene_tenders.values()), vorschlag
                )

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
        logger.exception("Crawler Kevin: Anfrage fehlgeschlagen")
        return AssistantResult(_NICHT_ERREICHBAR_HINWEIS)


# --- Ollama (lokales, kostenloses Sprachmodell) ------------------------------------------------

_OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
    }
    for t in ALLE_TOOLS
]
_DENK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)

# Zusätzliche Regeln nur für lokale Modelle: im Test (25.09.2026, qwen3:8b) beschrieb das Modell
# ohne jeden Werkzeugaufruf eine frei erfundene Ausschreibung und filterte ungefragt auf
# bestimmte Portale - Claude braucht diese Nachschärfung nicht.
_OLLAMA_ZUSATZREGELN = (
    "\n\nZusätzliche Regeln (streng einhalten):\n"
    "- Bevor du irgendetwas über Ausschreibungen oder Portale sagst, rufe IMMER zuerst ein "
    "Werkzeug auf (suche_ausschreibungen bzw. quellstatus). Du kennst keine Ausschreibungen aus "
    "dem Gedächtnis.\n"
    "- Setze Filter nur, wenn die Frage sie verlangt: portal_slugs nur bei Frage nach einem "
    "bestimmten Portal, ki_relevanz_min nur bei ausdrücklicher Frage nach starker Relevanz.\n"
    "- Findest du nichts, suche einmal mit weniger Filtern erneut, bevor du antwortest.\n"
    "- tender_id für ausschreibung_merken nur aus einem Suchergebnis dieses Gesprächs übernehmen."
)
_OHNE_WERKZEUG_NACHHAKEN = (
    "Du hast noch kein Werkzeug benutzt. Falls die Frage Ausschreibungen oder Portale betrifft, "
    "rufe jetzt zuerst das passende Werkzeug auf und antworte erst danach - nicht aus dem Gedächtnis. "
    "Falls nicht (z. B. Begrüßung), antworte einfach erneut."
)


class _OllamaModellFehlt(Exception):
    pass


def _ollama_anfrage(http: httpx.Client, messages: list[dict]) -> dict:
    nutzlast = {
        "model": settings.ollama_model,
        "messages": messages,
        "tools": _OLLAMA_TOOLS,
        "stream": False,
        "options": {"temperature": 0.2},
        # Denk-Modus (z. B. Qwen3) aus: auf einem Mac sonst deutlich langsamer, für Werkzeugwahl +
        # kurze Zusammenfassung nicht nötig. Ältere Ollama-Versionen/Modelle ohne Denk-Modus
        # lehnen das Feld ggf. ab - dann einmal ohne erneut versuchen.
        "think": False,
    }
    antwort = http.post("/api/chat", json=nutzlast)
    if antwort.status_code == 400 and "think" in antwort.text.lower():
        nutzlast.pop("think")
        antwort = http.post("/api/chat", json=nutzlast)
    if antwort.status_code == 404:
        raise _OllamaModellFehlt()
    antwort.raise_for_status()
    return antwort.json().get("message") or {}


def _ollama_tool_argumente(roh) -> dict:
    if isinstance(roh, dict):
        return roh
    if isinstance(roh, str) and roh.strip():
        try:
            geparst = json.loads(roh)
            return geparst if isinstance(geparst, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _bereinige_text(text: str | None) -> str:
    return _DENK_BLOCK.sub("", text or "").strip()


def _vorschlag_fehler(db: Session, name: str, tool_input: dict) -> str | None:
    """Prüft einen Aktionsvorschlag auf offensichtlich ungültige Angaben, bevor er Vincent
    vorgelegt wird. None = in Ordnung."""
    if name == "ausschreibung_merken" and db.get(Tender, tool_input.get("tender_id") or "") is None:
        return (
            "Unbekannte tender_id. Erst mit suche_ausschreibungen suchen und die id aus einem "
            "Treffer verwenden."
        )
    if name == "aktualisieren_starten" and tool_input.get("portal_slug") and _portal_von_slug(db, tool_input["portal_slug"]) is None:
        return "Unbekannter portal_slug - nur Slugs aus der Portal-Liste im Systemprompt verwenden, oder weglassen für alle."
    if name == "suchprofil_anlegen" and not str(tool_input.get("name") or "").strip():
        return "Das Suchprofil braucht einen Namen."
    return None


def _run_ollama_chat(
    db: Session, nachricht: str, verlauf: list[dict] | None, http: httpx.Client | None
) -> AssistantResult:
    messages: list[dict] = [{"role": "system", "content": _build_system_prompt(db) + _OLLAMA_ZUSATZREGELN}]
    for eintrag in verlauf or []:
        rolle = "assistant" if eintrag.get("rolle") == "assistant" else "user"
        messages.append({"role": rolle, "content": eintrag.get("text", "")})
    messages.append({"role": "user", "content": nachricht})

    gefundene_tenders: dict[str, Tender] = {}
    eigener_client = http is None
    if eigener_client:
        http = httpx.Client(base_url=settings.ollama_url, timeout=settings.ollama_timeout_seconds)
    try:
        werkzeug_genutzt = False
        nachgehakt = False
        for _ in range(MAX_TOOL_ITERATIONEN):
            antwort = _ollama_anfrage(http, messages)
            tool_calls = antwort.get("tool_calls") or []
            text = _bereinige_text(antwort.get("content"))
            if not tool_calls and not werkzeug_genutzt and not nachgehakt:
                # Schutz gegen erfundene Antworten: einmal nachhaken, bevor eine Antwort ohne
                # jeden Werkzeugaufruf durchgeht.
                nachgehakt = True
                messages.append({"role": "assistant", "content": antwort.get("content") or ""})
                messages.append({"role": "user", "content": _OHNE_WERKZEUG_NACHHAKEN})
                continue
            if not tool_calls:
                return AssistantResult(text or "(keine Antwort)", list(gefundene_tenders.values()))
            werkzeug_genutzt = True

            aufrufe = [
                ((tc.get("function") or {}).get("name", ""), _ollama_tool_argumente((tc.get("function") or {}).get("arguments")))
                for tc in tool_calls
            ]
            schreibend = next(((n, a) for n, a in aufrufe if n in _WRITE_TOOL_NAMEN), None)
            fehler = _vorschlag_fehler(db, *schreibend) if schreibend is not None else None
            if fehler is not None:
                # Erfundene ID o. ä. (kleine lokale Modelle): nicht Vincent zur Bestätigung
                # vorlegen, sondern dem Modell zurückmelden, damit es erst richtig sucht.
                messages.append({"role": "assistant", "content": antwort.get("content") or "", "tool_calls": tool_calls})
                messages.append({"role": "tool", "tool_name": schreibend[0], "content": json.dumps({"fehler": fehler}, ensure_ascii=False)})
                continue
            if schreibend is not None:
                # Wie bei Claude: nie direkt ausführen, nur zur Bestätigung vorschlagen.
                name, tool_input = schreibend
                vorschlag = AssistantActionProposal(
                    name=name, input=tool_input, beschreibung=_beschreibe_aktion(db, name, tool_input)
                )
                return AssistantResult(text or vorschlag.beschreibung, list(gefundene_tenders.values()), vorschlag)

            messages.append({"role": "assistant", "content": antwort.get("content") or "", "tool_calls": tool_calls})
            for name, tool_input in aufrufe:
                ergebnis = _execute_tool(db, name, tool_input, gefundene_tenders)
                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": json.dumps(ergebnis, ensure_ascii=False, default=str),
                })

        return AssistantResult(_ZU_KOMPLEX_HINWEIS, list(gefundene_tenders.values()))
    except httpx.ConnectError:
        return AssistantResult(_OLLAMA_NICHT_GESTARTET_HINWEIS)
    except _OllamaModellFehlt:
        return AssistantResult(_OLLAMA_MODELL_FEHLT_HINWEIS.format(modell=settings.ollama_model))
    except Exception:
        logger.exception("Crawler Kevin (Ollama): Anfrage fehlgeschlagen")
        return AssistantResult(_NICHT_ERREICHBAR_HINWEIS)
    finally:
        if eigener_client:
            http.close()


def execute_assistant_action(db: Session, name: str, tool_input: dict) -> AssistantActionResult:
    """Führt eine von Kevin vorgeschlagene und von Vincent im Frontend bestätigte Aktion aus.

    Wird ausschließlich nach expliziter Bestätigung aufgerufen (POST /assistant/actions/execute) -
    nie automatisch aus run_assistant_chat heraus (siehe Moduldocstring).
    """
    if name == "aktualisieren_starten":
        return _aktion_aktualisieren_starten(db, tool_input)
    if name == "suchprofil_anlegen":
        return _aktion_suchprofil_anlegen(db, tool_input)
    if name == "ausschreibung_merken":
        return _aktion_ausschreibung_merken(db, tool_input)
    return AssistantActionResult(False, f"Unbekannte Aktion: {name}")


def _aktion_aktualisieren_starten(db: Session, tool_input: dict) -> AssistantActionResult:
    from fastapi import HTTPException

    from app.api import run as run_api

    slug = tool_input.get("portal_slug")
    portal_ids = None
    ziel = "alle aktiven Portale"
    if slug:
        portal = _portal_von_slug(db, slug)
        if portal is None:
            return AssistantActionResult(False, f"Portal mit Slug '{slug}' nicht gefunden.")
        portal_ids = [portal.id]
        ziel = portal.name

    try:
        run_api.start_run(portal_ids=portal_ids)
    except HTTPException as exc:
        return AssistantActionResult(False, str(exc.detail))
    return AssistantActionResult(True, f"Aktualisieren-Lauf für {ziel} gestartet - Fortschritt siehe Übersicht.")


def _aktion_suchprofil_anlegen(db: Session, tool_input: dict) -> AssistantActionResult:
    name = (tool_input.get("name") or "").strip()
    if not name:
        return AssistantActionResult(False, "Suchprofil braucht einen Namen.")

    portal_slugs = tool_input.get("portal_slugs") or []
    portal_ids = set(portal_slugs)
    if portal_slugs:
        slug_ids = [p.id for p in db.scalars(select(Portal).where(Portal.slug.in_(portal_slugs)))]
        portal_ids = set(slug_ids)

    filter_json: dict = {}
    if tool_input.get("ki_relevanz_min"):
        filter_json["ki_relevanz_min"] = tool_input["ki_relevanz_min"]
    if tool_input.get("region"):
        filter_json["region"] = tool_input["region"]
    if tool_input.get("mindestwert") is not None:
        filter_json["mindestwert"] = tool_input["mindestwert"]

    profile = SearchProfile(
        name=name,
        portale=list(portal_ids),
        keywords=tool_input.get("keywords") or [],
        filter_json=filter_json,
        aktiv=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    from app.agents.search import recompute_profile_hits

    treffer = recompute_profile_hits(db, profile)
    return AssistantActionResult(True, f"Suchprofil „{name}“ angelegt ({treffer} aktuelle Treffer).")


def _aktion_ausschreibung_merken(db: Session, tool_input: dict) -> AssistantActionResult:
    tender = db.get(Tender, tool_input.get("tender_id"))
    if tender is None:
        return AssistantActionResult(False, "Ausschreibung nicht gefunden.")
    tender.gemerkt = True
    if tool_input.get("notiz"):
        tender.merk_notiz = tool_input["notiz"]
    db.commit()
    return AssistantActionResult(True, f"„{tender.titel}“ gemerkt.")
