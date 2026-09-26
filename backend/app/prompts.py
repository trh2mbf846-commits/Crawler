"""Master Prompt Library (Kapitel 25). Alle Prompts liefern strukturiertes JSON; jede Ausgabe

wird im System als KI-gestützte Einschätzung gekennzeichnet, nie als gesicherte Tatsache
(Grundsatz aus Kapitel 20.4). Ohne konfigurierten ANTHROPIC_API_KEY liefert call_llm_json(...)
None und die aufrufende Stelle fällt auf die regelbasierte Einstufung zurück (Kapitel 4.1/4.2
bleiben damit auch ohne LLM-Zugang voll funktionsfähig, wie in Kapitel 14 Phase 1/2 gefordert).
"""
from __future__ import annotations

import json

import httpx

from app.config import settings

KI_RELEVANZ_SYSTEM = (
    "Du bewertest eine öffentliche Ausschreibung auf ihre Relevanz für Künstliche Intelligenz / "
    "KI-Entwicklung im Sinne von Kapitel 4 dieser Handlungsanweisung. Sei streng (Nutzerwunsch "
    "25.09.2026: Ausschreibungen, die KI nur nebenbei erwähnen, sollen nicht als relevant gelten):\n"
    "- stark_relevant: KI/Machine Learning ist der KERN des Auftrags (KI-System entwickeln, "
    "einführen, betreiben oder beraten; Hardware ausdrücklich für KI-Rechenlasten).\n"
    "- moeglich_relevant: KI ist ein ausdrücklich genannter, aber untergeordneter Teil des "
    "Auftrags.\n"
    "- nicht_relevant: allgemeine IT/Software/Webseiten/Beratung ohne konkreten KI-Bezug, KI nur "
    "beiläufig erwähnt, oder 'KI'/'AI' ist Teil eines Namens oder einer Abkürzung (z. B. ein "
    "Projektname).\n"
    "Antworte ausschließlich mit JSON im Format "
    '{"einstufung": "stark_relevant|moeglich_relevant|nicht_relevant", '
    '"begruendung": "...", "konfidenz": 0.0}. Die Begründung hat maximal 2 Sätze, auf Deutsch.'
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

FRIST_SYSTEM = (
    "Du liest den Text der Webseite eines öffentlichen Vergabeverfahrens und bestimmst die Frist "
    "für den Eingang der Angebote (Angebotsfrist / Schlusstermin der Angebotsabgabe) - NICHT die "
    "Frist für Bieterfragen, Teilnahmeanträge oder die Bindefrist. Antworte ausschließlich mit JSON "
    'im Format {"angebotsfrist": "YYYY-MM-DDTHH:MM" oder null, "beleg": "wörtliches Zitat aus dem '
    'Text, in dem die Frist steht"}. Steht keine Angebotsfrist im Text: {"angebotsfrist": null, '
    '"beleg": ""}. Erfinde nichts.'
)

GO_NOGO_SYSTEM = (
    "Du bist Vergabe-Experte und bewertest für ein Unternehmen, ob es sich auf eine öffentliche "
    "Ausschreibung bewerben sollte (Go/No-Go). Nutze ausschließlich die gegebenen Texte, erfinde "
    "nichts; steht etwas nicht drin, lass die Liste leer. Wenn kein Firmenprofil angegeben ist, "
    "bewerte die Passung nur anhand der Prioritäten und sage das in der Begründung.\n"
    "Antworte ausschließlich mit JSON im Format "
    '{"empfehlung": "bewerben|pruefen|nicht_bewerben", "passwert": 0, '
    '"zusammenfassung": "worum es geht, 1-2 Sätze", "begruendung": "max. 3 Sätze", '
    '"ausschlusskriterien": [], "pflichtnachweise": [], "zuschlagskriterien": [], "fristen": [], '
    '"fehlende_nachweise": [], "risiken": [], "naechste_schritte": [], "passende_referenzen": []}. '
    "passwert: 0-100 (wie gut Auftrag und Unternehmen zusammenpassen). Listen: kurze Stichpunkte "
    "auf Deutsch, höchstens 6 je Liste. Übernimm Kriterien, Nachweise und Fristen möglichst "
    "wortnah aus dem Text (sie werden gegen den Text geprüft). fehlende_nachweise: geforderte "
    "Nachweise, die laut Firmenprofil fehlen oder unklar sind. passende_referenzen: Titel der "
    "gegebenen Referenzprojekte (exakt wie angegeben), die zu dieser Ausschreibung passen."
)

RUECKFRAGE_SYSTEM = (
    "Formuliere eine Rückfrage an Vincent im Format aus Abschnitt 10.3 der Handlungsanweisung "
    "(vier Abschnitte: Kontext, Problem, Optionen, Empfehlung, Auswirkung auf Zeitplan). Verwende "
    "ausschließlich Informationen aus dem gegebenen Kontext, erfinde keine Details."
)


def ki_relevanz_user(
    titel: str, kurzbeschreibung: str | None, vergabestelle: str | None, volltext: str | None = None
) -> str:
    text = f"Titel: {titel}\nKurzbeschreibung: {kurzbeschreibung or ''}\nVergabestelle: {vergabestelle or ''}"
    if volltext and volltext != kurzbeschreibung:
        text += f"\nAuszug Beschreibung: {volltext[:1500]}"
    return text


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


def llm_anbieter() -> str:
    """Welcher Sprachmodell-Anbieter genutzt wird: "anthropic" oder "ollama" (lokal, kostenlos).

    settings.kevin_anbieter gilt für Kevin und die KI-Nachprüfung gleichermaßen; "auto" = Claude,
    wenn ein Anthropic-Key gesetzt ist, sonst Ollama.
    """
    gewuenscht = (settings.kevin_anbieter or "auto").strip().lower()
    if gewuenscht in ("anthropic", "ollama"):
        return gewuenscht
    return "anthropic" if settings.anthropic_api_key else "ollama"


def llm_bezeichnung() -> str:
    return f"lokales Modell {settings.ollama_model}" if llm_anbieter() == "ollama" else f"Claude ({settings.anthropic_model})"


def call_llm_json(system: str, user: str, lokal_erlaubt: bool = False) -> dict | None:
    """Ruft die Claude API auf, sofern konfiguriert; liefert None, wenn kein Key gesetzt ist oder

    der Aufruf fehlschlägt (in diesem Fall übernimmt die regelbasierte Klassifikation, siehe
    keywords.py/classification.py - kein harter Fehler nur wegen fehlender LLM-Anbindung).

    lokal_erlaubt=True (nur für seltene, gezielte Aufrufe wie die KI-Nachprüfung): ohne Claude
    wird stattdessen das lokale Ollama-Modell gefragt. Bewusst nicht für massenhafte Aufrufe
    (z. B. Kategorisierung jeder einzelnen Ausschreibung) - lokal wäre das zu langsam.
    """
    if llm_anbieter() == "ollama":
        return _ollama_json(system, user) if lokal_erlaubt else None
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


def _ollama_json(system: str, user: str) -> dict | None:
    try:
        antwort = httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": "json",
                "stream": False,
                "think": False,
                # Standard-Kontext von Ollama (2-4k Token) reicht für Unterlagen-Auszüge nicht.
                "options": {"temperature": 0, "num_ctx": 8192},
            },
            timeout=settings.ollama_timeout_seconds,
        )
        antwort.raise_for_status()
        inhalt = (antwort.json().get("message") or {}).get("content") or ""
        ergebnis = json.loads(inhalt)
        return ergebnis if isinstance(ergebnis, dict) else None
    except Exception:
        return None
