"""Datenqualität pro Lauf (26.09.2026, Profi-Empfehlung: "nicht nur Erfolg/Misserfolg überwachen,
sondern die Qualität der Daten" - ein Lauf kann erfolgreich sein und trotzdem nach einer
Layout-Änderung des Portals plötzlich leere Felder liefern, z. B. keine Fristen mehr).

messe() berechnet für die im Lauf gesehenen, offenen Ausschreibungen eines Portals den Anteil mit
Frist, Vergabestelle, Beschreibung, Ort und verfahrensspezifischem Link; source_health.evaluate()
vergleicht das mit den vorherigen Läufen und warnt bei einem deutlichen Einbruch.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.connector.verfahrenslink import ist_verfahrensspezifisch
from app.models import Portal, Tender

FELDER = {
    "angebotsfrist": "Frist",
    "vergabestelle": "Vergabestelle",
    "kurzbeschreibung": "Beschreibung",
    "ort_region": "Ort",
    "direktlink": "Verfahrenslink",
}
MIN_ANZAHL = 10  # darunter sind Quoten zu zufällig für eine Warnung
EINBRUCH_PUNKTE = 0.30  # Warnung, wenn ein Anteil um mindestens 30 Prozentpunkte fällt ...
MIN_VORHER = 0.50  # ... und vorher mindestens bei 50 % lag


def _hat(tender: Tender, feld: str) -> bool:
    wert = getattr(tender, feld)
    if feld == "direktlink":
        return bool(wert) and ist_verfahrensspezifisch(wert)
    return bool(wert)


def messe(db: Session, portal: Portal, seit: datetime) -> dict | None:
    tenders = list(
        db.scalars(
            select(Tender).where(
                Tender.portal_id == portal.id,
                Tender.zuletzt_geprueft_am >= seit,
                Tender.status.not_in(("abgelaufen", "vergeben")),
            )
        )
    )
    if not tenders:
        return None
    return {
        "anzahl": len(tenders),
        "quoten": {feld: round(sum(_hat(t, feld) for t in tenders) / len(tenders), 3) for feld in FELDER},
    }


def einbrueche(aktuell: dict | None, vorher: list[dict]) -> list[str]:
    """Meldungen für Felder, deren Anteil gegenüber dem Durchschnitt der Vorläufe eingebrochen ist."""
    if not aktuell or aktuell.get("anzahl", 0) < MIN_ANZAHL:
        return []
    vorher = [v for v in vorher if v and v.get("anzahl", 0) >= MIN_ANZAHL]
    if not vorher:
        return []
    meldungen = []
    for feld, name in FELDER.items():
        frueher = sum(v["quoten"].get(feld, 0) for v in vorher) / len(vorher)
        jetzt = aktuell["quoten"].get(feld, 0)
        if frueher >= MIN_VORHER and frueher - jetzt >= EINBRUCH_PUNKTE:
            meldungen.append(f"Anteil mit {name} von {frueher:.0%} auf {jetzt:.0%} gefallen")
    return meldungen
