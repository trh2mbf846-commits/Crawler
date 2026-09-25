"""Source-Health-Agent (Kapitel 18, 21): überwacht fortlaufend die Qualität jedes Connectors

und sorgt dafür, dass Probleme auch ohne tägliche manuelle Kontrolle zuverlässig auffallen
(Voraussetzung für den in Kapitel 17 beschriebenen unbeaufsichtigten Langzeitbetrieb).

Selbstdiagnose bei Eskalation (Nutzerrecherche 25.09.2026 zu guten Crawling-Agenten:
"LLM als Reparaturtechniker, nur im Fehlerfall, nie im Normalbetrieb" statt teurem Dauereinsatz).
Bewusste Sicherheitsgrenze (siehe Chat-Verlauf/README): die Diagnose schreibt NIE selbstständig
Connector-Code um, sondern liefert Vincent über Escalation.empfehlung eine informierte
Ersteinschätzung ("Zugriffsschranke oder Strukturänderung? Was genau sieht anders aus?"), die er
dann selbst - oder mit einer separaten Coding-Session - umsetzt. Ohne ANTHROPIC_API_KEY läuft
alles wie bisher, nur ohne die automatische Diagnose (siehe _diagnose_portal_problem).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Escalation, Portal, SourceHealthMetric
from app.prompts import QUELLSTATUS_SYSTEM, call_llm_json, quellstatus_user

_DIAGNOSE_TIMEOUT_SEKUNDEN = 10.0
_DIAGNOSE_SNIPPET_ZEICHEN = 4000


def record_run(
    db: Session,
    portal: Portal,
    *,
    erfolgreich: bool,
    treffer_anzahl: int | None = None,
    neu_anzahl: int | None = None,
    aktualisiert_anzahl: int | None = None,
    fehlerrate: float | None = None,
    fehlertyp: str | None = None,
    dauer_ms: int | None = None,
) -> SourceHealthMetric:
    metric = SourceHealthMetric(
        portal_id=portal.id,
        erfolgreich=erfolgreich,
        treffer_anzahl=treffer_anzahl,
        neu_anzahl=neu_anzahl,
        aktualisiert_anzahl=aktualisiert_anzahl,
        fehlerrate=fehlerrate,
        fehlertyp=fehlertyp,
        dauer_ms=dauer_ms,
    )
    db.add(metric)
    db.commit()
    return metric


def evaluate(db: Session, portal: Portal) -> dict:
    """Berechnet Ampel-Status + Meldung für das Quellstatus-Dashboard (Kapitel 21.6) und legt bei

    kritischen Schwellenwerten eine Eskalation an (Kapitel 21.4), sofern nicht schon eine offene
    Eskalation für denselben Zustand existiert (kein Eskalations-Spam bei wiederholten Läufen).
    """
    letzte = list(
        db.scalars(
            select(SourceHealthMetric)
            .where(SourceHealthMetric.portal_id == portal.id)
            .order_by(SourceHealthMetric.lauf_am.desc())
            .limit(10)
        )
    )

    if not letzte:
        return {
            "status_ampel": "gelb",
            "letzter_erfolgreicher_lauf": None,
            "letzte_trefferzahl": None,
            "fehlerrate_gleitend": None,
            "meldung": "Noch kein Lauf protokolliert.",
        }

    letzter_erfolgreicher = next((m for m in letzte if m.erfolgreich), None)
    ampel = "gruen"
    meldungen: list[str] = []

    # 0-Treffer-Serie (Kapitel 21.3).
    null_treffer_serie = 0
    for m in letzte:
        if m.erfolgreich and (m.treffer_anzahl or 0) == 0:
            null_treffer_serie += 1
        else:
            break
    if null_treffer_serie >= settings.health_null_treffer_eskalation_ab:
        ampel = "rot"
        meldungen.append(f"{null_treffer_serie}x in Folge 0 Treffer.")
        _eskaliere_falls_noetig(
            db, portal, "sonstiges",
            f"Portal '{portal.name}' liefert seit {null_treffer_serie} aufeinanderfolgenden Läufen 0 Treffer.",
            ["Portal-Struktur manuell prüfen", "Connector-Selektoren aktualisieren", "Portal vorübergehend pausieren"],
        )
    elif null_treffer_serie >= settings.health_null_treffer_warnung_ab:
        ampel = "gelb" if ampel == "gruen" else ampel
        meldungen.append(f"{null_treffer_serie}x in Folge 0 Treffer (Warnung).")

    # Fehlerrate (Kapitel 21.3).
    letzte_fehlerrate = letzte[0].fehlerrate
    if letzte_fehlerrate is not None and letzte_fehlerrate > settings.health_fehlerrate_warnung:
        ampel = "gelb" if ampel == "gruen" else ampel
        meldungen.append(f"Fehlerrate {letzte_fehlerrate:.0%} über Schwellenwert.")

    # Ausfall seit > 3x Intervall (Kapitel 21.3).
    if letzter_erfolgreicher is not None:
        max_alter = timedelta(minutes=portal.intervall_minuten * settings.health_ausfall_faktor_intervall)
        if datetime.utcnow() - letzter_erfolgreicher.lauf_am > max_alter:
            ampel = "rot"
            meldungen.append("Kein erfolgreicher Lauf seit mehr als dem 3-fachen Intervall.")
            _eskaliere_falls_noetig(
                db, portal, "sonstiges",
                f"Portal '{portal.name}': kein erfolgreicher Lauf seit über {max_alter}.",
                ["Connector-Fehlerprotokoll prüfen", "Portal-Struktur manuell prüfen"],
            )
    else:
        ampel = "rot"
        meldungen.append("Noch nie ein erfolgreicher Lauf.")

    # Trefferrückgang > 50% ggü. gleitendem Durchschnitt (Kapitel 21.3).
    erfolgreiche_treffer = [m.treffer_anzahl for m in letzte[1:] if m.erfolgreich and m.treffer_anzahl is not None]
    if erfolgreiche_treffer and letzte[0].erfolgreich and letzte[0].treffer_anzahl is not None:
        durchschnitt = sum(erfolgreiche_treffer) / len(erfolgreiche_treffer)
        if durchschnitt > 0 and letzte[0].treffer_anzahl < durchschnitt * (1 - settings.health_trefferrueckgang_warnung):
            ampel = "gelb" if ampel == "gruen" else ampel
            meldungen.append("Trefferrückgang über 50% ggü. gleitendem Durchschnitt - möglicherweise Strukturänderung.")

    return {
        "status_ampel": ampel,
        "letzter_erfolgreicher_lauf": letzter_erfolgreicher.lauf_am if letzter_erfolgreicher else None,
        "letzte_trefferzahl": letzte[0].treffer_anzahl,
        "fehlerrate_gleitend": letzte_fehlerrate,
        "meldung": " ".join(meldungen) or None,
    }


def _eskaliere_falls_noetig(db: Session, portal: Portal, kategorie: str, kontext: str, optionen: list[str]) -> None:
    bereits_offen = db.scalars(
        select(Escalation).where(
            Escalation.portal_id == portal.id, Escalation.status == "offen", Escalation.kontext == kontext
        )
    ).first()
    if bereits_offen is not None:
        return
    empfehlung = _formatiere_diagnose(_diagnose_portal_problem(portal, kontext))
    db.add(
        Escalation(
            portal_id=portal.id, kategorie=kategorie, kontext=kontext, optionen=optionen,
            empfehlung=empfehlung, status="offen",
        )
    )
    db.commit()


def _diagnose_portal_problem(portal: Portal, kontext: str) -> dict | None:
    """Ruft im Fehlerfall (nur hier, nicht im Normalbetrieb) einmalig die aktuelle Portalseite ab

    und lässt Claude einschätzen, ob eine Zugriffsschranke oder eine Strukturänderung vorliegt -
    "Reparaturtechniker bei Bedarf" statt Dauereinsatz. Liefert None ohne API-Key oder bei jedem
    Fehlschlag (kein gespeicherter Referenzzustand vorhanden, daher rein auf Basis der aktuellen
    Seite - eine Heuristik, kein Ersatz für eine echte Prüfung).
    """
    if not settings.anthropic_api_key:
        return None
    try:
        response = httpx.get(portal.base_url, timeout=_DIAGNOSE_TIMEOUT_SEKUNDEN, follow_redirects=True)
        aktuelle_snippet = response.text[:_DIAGNOSE_SNIPPET_ZEICHEN]
    except httpx.HTTPError:
        return None

    return call_llm_json(
        QUELLSTATUS_SYSTEM,
        quellstatus_user(
            portal.name,
            referenz_snippet=(
                "(kein gespeicherter Referenzzustand vorhanden - beurteile nur, ob die aktuelle "
                "Seite normal aussieht, eine Zugriffsschranke (Login/CAPTCHA) zeigt oder "
                "strukturell verändert wirkt)"
            ),
            aktuelle_snippet=aktuelle_snippet,
            fehler=kontext,
        ),
    )


def _formatiere_diagnose(diagnose: dict | None) -> str | None:
    if not diagnose:
        return None
    teile = [t for t in (diagnose.get("vermutete_ursache"), diagnose.get("kurzbegruendung")) if t]
    if not teile:
        return None
    text = " - ".join(teile)
    return f"[Automatische Ersteinschätzung, keine gesicherte Diagnose] {text}"
