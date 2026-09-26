"""Bewerbungsalltag (26.09.2026, nach Recherche zu Profi-Vergabetools): Abgabe-Checkliste pro
Ausschreibung, Fristen-Kalender (inkl. .ics-Export für den Mac-Kalender) und Referenz-Datenbank.

- Checkliste: wird aus der Go/No-Go-Bewertung erzeugt (Pflichtnachweise, Ausschlusskriterien,
  Fristen; laut Bewertung fehlende Nachweise gleich als "fehlt"), jeder Punkt lässt sich abhaken
  bzw. als vorhanden/fehlt markieren, eigene Punkte können ergänzt werden. Eine neue Bewertung
  ergänzt nur neue Punkte, vorhandene Häkchen bleiben erhalten.
- Fristen: Angebots- und Fragenfristen aller Ausschreibungen, an denen man arbeitet (gemerkt,
  bewertet mit "bewerben"/"prüfen" oder mit Checkliste).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Tender


def _punkt(text: str, art: str, status: str = "offen") -> dict:
    return {"id": uuid.uuid4().hex[:10], "text": text.strip(), "art": art, "status": status}


def checkliste_aus_bewertung(tender: Tender) -> list[dict]:
    """Vorhandene Checkliste um die Punkte der Bewertung ergänzen (ohne Doppelte, Häkchen bleiben)."""
    punkte = list(tender.checkliste_json or [])
    bekannt = {p["text"].strip().lower() for p in punkte}
    b = tender.bewertung_json or {}
    fehlend = {f.strip().lower() for f in b.get("fehlende_nachweise", [])}

    def neu(text: str, art: str, status: str = "offen") -> None:
        if text and text.strip().lower() not in bekannt:
            punkte.append(_punkt(text, art, status))
            bekannt.add(text.strip().lower())

    for text in b.get("pflichtnachweise", []):
        neu(text, "nachweis", "fehlt" if text.strip().lower() in fehlend else "offen")
    for text in b.get("fehlende_nachweise", []):
        neu(text, "nachweis", "fehlt")
    for text in b.get("ausschlusskriterien", []):
        neu(f"Ausschlusskriterium prüfen: {text}", "ausschluss")
    for text in b.get("fristen", []):
        neu(f"Frist beachten: {text}", "frist")
    tender.checkliste_json = punkte
    return punkte


def fristen(db: Session, tage: int = 90) -> list[dict]:
    jetzt = datetime.utcnow()
    bis = jetzt + timedelta(days=tage)
    tenders = db.scalars(
        select(Tender).where(
            Tender.status.not_in(("abgelaufen", "vergeben")),
            or_(Tender.gemerkt.is_(True), Tender.bewertung_json.is_not(None), Tender.checkliste_json.is_not(None)),
        )
    )
    eintraege = []
    for t in tenders:
        empfehlung = (t.bewertung_json or {}).get("empfehlung")
        if not t.gemerkt and not t.checkliste_json and empfehlung == "nicht_bewerben":
            continue  # bewertet, aber lohnt sich nicht - nicht in den Kalender
        grund = "gemerkt" if t.gemerkt else ("Checkliste" if t.checkliste_json else "bewertet")
        for art, datum in (("Fragenfrist", t.fragenfrist), ("Angebotsfrist", t.angebotsfrist)):
            if datum and jetzt - timedelta(days=1) <= datum <= bis:
                eintraege.append({
                    "tender_id": t.id, "titel": t.titel, "vergabestelle": t.vergabestelle, "art": art,
                    "datum": datum, "grund": grund, "direktlink": t.direktlink,
                })
    return sorted(eintraege, key=lambda e: e["datum"])


def _ics_text(text: str) -> str:
    # RFC 5545: Backslash, Semikolon, Komma und Zeilenumbruch maskieren.
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fristen_ics(eintraege: list[dict]) -> str:
    """iCalendar-Datei - im Mac-Kalender per Doppelklick importierbar. Erinnerung 3 Tage vorher."""
    zeilen = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ausschreibungs-Crawler//Fristen//DE", "CALSCALE:GREGORIAN"]
    stempel = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for e in eintraege:
        beginn = e["datum"]
        hat_uhrzeit = beginn.hour or beginn.minute
        zeilen += [
            "BEGIN:VEVENT",
            f"UID:{e['tender_id']}-{e['art']}@ausschreibungs-crawler",
            f"DTSTAMP:{stempel}",
            f"DTSTART:{beginn.strftime('%Y%m%dT%H%M%S')}" if hat_uhrzeit else f"DTSTART;VALUE=DATE:{beginn.strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_text(e['art'] + ': ' + e['titel'][:120])}",
            f"DESCRIPTION:{_ics_text((e['vergabestelle'] or '') + ' - ' + e['direktlink'])}",
            f"URL:{e['direktlink']}",
            "BEGIN:VALARM", "TRIGGER:-P3D", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_text(e['art'] + ' in 3 Tagen')}", "END:VALARM",
            "END:VEVENT",
        ]
    zeilen.append("END:VCALENDAR")
    return "\r\n".join(zeilen) + "\r\n"
