"""Master Prompt Library (Kapitel 25). Alle Prompts liefern strukturiertes JSON; jede Ausgabe

wird im System als KI-gestützte Einschätzung gekennzeichnet, nie als gesicherte Tatsache
(Grundsatz aus Kapitel 20.4). Ohne konfigurierten ANTHROPIC_API_KEY liefert call_llm_json(...)
None und die aufrufende Stelle fällt auf die regelbasierte Einstufung zurück (Kapitel 4.1/4.2
bleiben damit auch ohne LLM-Zugang voll funktionsfähig, wie in Kapitel 14 Phase 1/2 gefordert).
"""
from __future__ import annotations

import json

from app.config import settings

KI_RELEVANZ_SYSTEM = (
    "Du bewertest eine öffentliche Ausschreibung auf ihre Relevanz für Künstliche Intelligenz / "
    "KI-Entwicklung im Sinne von Kapitel 4 dieser Handlungsanweisung. Antworte ausschließlich mit "
    'JSON im Format {"einstufung": "stark_relevant|moeglich_relevant|nicht_relevant", '
    '"begruendung": "...", "konfidenz": 0.0}. Die Begründung hat maximal 2 Sätze.'
)

QUELLSTATUS_SYSTEM = (
    "Du unterstützt den Source-Health-Agent bei der Einschätzung, warum ein automatisierter Abruf "
    "eines Vergabeportals fehlgeschlagen ist oder unerwartet 0 Treffer geliefert hat. Antworte "
    'ausschließlich mit JSON im Format {"vermutete_ursache": "...", "rueckfrage_noetig": true, '
    '"kurzbegruendung": "..."}.'
)

DUPLIKAT_SYSTEM = (
    "Du bewertest, ob zwei erfasste Datensätze dieselbe Ausschreibung beschreiben. Antworte "
    'ausschließlich mit JSON im Format {"ist_duplikat": true, "konfidenz": 0.0, "begruendung": "..."}.'
)

KATEGORISIERUNG_SYSTEM = (
    "Ordne die Ausschreibung einer oder mehreren Kategorien aus der Themen-Taxonomie zu: "
    "KI & Machine Learning, Softwareentwicklung & IT-Dienstleistungen, Cloud & Infrastruktur, "
    "Daten & Analytics, Beratung & Strategie, Planung & Technische Beratung, "
    "Bauüberwachung & Bauleitung, Prozessautomatisierung, Cybersecurity, Sonstige IT, "
    'Nicht-IT. Antworte ausschließlich mit JSON im Format {"kategorien": ["..."]}.'
)

RUECKFRAGE_SYSTEM = (
    "Formuliere eine Rückfrage an Vincent im Format aus Abschnitt 10.3 der Handlungsanweisung "
    "(vier Abschnitte: Kontext, Problem, Optionen, Empfehlung, Auswirkung auf Zeitplan). Verwende "
    "ausschließlich Informationen aus dem gegebenen Kontext, erfinde keine Details."
)


def ki_relevanz_user(titel: str, kurzbeschreibung: str | None, vergabestelle: str | None) -> str:
    return f"Titel: {titel}\nKurzbeschreibung: {kurzbeschreibung or ''}\nVergabestelle: {vergabestelle or ''}"


def kategorisierung_user(titel: str, kurzbeschreibung: str | None) -> str:
    return f"Titel: {titel}\nKurzbeschreibung: {kurzbeschreibung or ''}"


def duplikat_user(a_titel: str, a_vergabestelle: str | None, a_frist, b_titel: str, b_vergabestelle: str | None, b_frist) -> str:
    return (
        f"Datensatz A: {a_titel} | {a_vergabestelle or ''} | {a_frist or ''}\n"
        f"Datensatz B: {b_titel} | {b_vergabestelle or ''} | {b_frist or ''}"
    )


def quellstatus_user(portal_name: str, referenz_snippet: str, aktuelle_snippet: str, fehler: str) -> str:
    return (
        f"Portal: {portal_name}\nZuletzt funktionierendes Muster: {referenz_snippet}\n"
        f"Aktuelle Antwort: {aktuelle_snippet}\nFehlerprotokoll: {fehler}"
    )


def call_llm_json(system: str, user: str) -> dict | None:
    """Ruft die Claude API auf, sofern konfiguriert; liefert None, wenn kein Key gesetzt ist oder

    der Aufruf fehlschlägt (in diesem Fall übernimmt die regelbasierte Klassifikation, siehe
    keywords.py/classification.py - kein harter Fehler nur wegen fehlender LLM-Anbindung).
    """
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        return json.loads(text)
    except Exception:
        return None
