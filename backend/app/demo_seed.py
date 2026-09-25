"""Optionale Demo-Testdaten, damit sich Übersicht/Filter/Suche/Ranking/Dashboard begutachten

lassen, obwohl die 3 echten Connectoren mangels Netzzugriff in dieser Entwicklungsumgebung noch
nicht gegen echte Portale laufen konnten (siehe README). Alle Datensätze sind klar als Testdaten
gekennzeichnet (Portal-Name "Demo-Quelle (Testdaten)", Vergabestelle-Präfix "[DEMO]") und das
Demo-Portal ist inaktiv (aktiv=False), damit der Scheduler es nie automatisch anfasst.

Aufruf: python -m app.demo_seed
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.agents.duplicate import run_duplicate
from app.db import SessionLocal, init_db
from app.models import Portal
from app.pipeline import drain_queue
from app.queue import enqueue
from app.seed import run_seed

DEMO_PORTAL_SLUG = "demo-testdaten"

_BEISPIELE = [
    dict(
        externe_id="DEMO-1",
        titel="KI-gestützte Dokumentenprüfung für Genehmigungsverfahren",
        volltext=(
            "Gesucht wird ein Anbieter für die Entwicklung eines Systems zur automatisierten "
            "Dokumentenprüfung mittels Machine Learning und Natural Language Processing im Rahmen "
            "von Genehmigungsverfahren. Large Language Models sollen zur Vorprüfung eingereichter "
            "Unterlagen eingesetzt werden."
        ),
        vergabestelle="[DEMO] Senatsverwaltung für Digitalisierung",
        tage_bis_frist=5,
        wert=450000,
    ),
    dict(
        externe_id="DEMO-2",
        titel="Chatbot für den Bürgerservice",
        volltext=(
            "Entwicklung eines virtuellen Assistenten (Conversational AI) zur Beantwortung "
            "häufiger Bürgeranfragen, Anbindung an bestehende Fachverfahren."
        ),
        vergabestelle="[DEMO] ITDZ Berlin",
        tage_bis_frist=18,
        wert=180000,
    ),
    dict(
        externe_id="DEMO-3",
        titel="Beratungsleistungen zur KI-Strategie 2027",
        volltext="Strategieberatung zur Entwicklung einer KI-Roadmap für die Verwaltung.",
        vergabestelle="[DEMO] Staatskanzlei",
        tage_bis_frist=45,
        wert=95000,
    ),
    dict(
        externe_id="DEMO-4",
        titel="Wartung der Aufzugsanlagen in Verwaltungsgebäuden",
        volltext="Wartung und Instandhaltung von Aufzugsanlagen an mehreren Standorten.",
        vergabestelle="[DEMO] Bau- und Liegenschaftsbetrieb",
        tage_bis_frist=60,
        wert=60000,
    ),
    dict(
        externe_id="DEMO-5",
        titel="Cloud-Infrastruktur und Datenanalyse-Plattform",
        volltext=(
            "Aufbau einer Cloud-Infrastruktur inkl. Data-Science-Plattform für Predictive "
            "Analytics und Datenanalyse im Gesundheitswesen."
        ),
        vergabestelle="[DEMO] Landesamt für Gesundheit",
        tage_bis_frist=3,
        wert=620000,
    ),
]


def run_demo_seed(db) -> int:
    portal = db.scalars(select(Portal).where(Portal.slug == DEMO_PORTAL_SLUG)).first()
    if portal is None:
        portal = Portal(
            slug=DEMO_PORTAL_SLUG,
            name="Demo-Quelle (Testdaten)",
            base_url="https://example.invalid/demo",
            betreiber="Keine echte Quelle - siehe README",
            aktiv=False,
            robots_status="ungeprueft",
            tos_hinweis="Keine echte Quelle, dient nur der UI-Vorschau ohne Netzzugriff.",
            vorgegeben=False,
        )
        db.add(portal)
        db.commit()
        db.refresh(portal)

    erzeugt = 0
    now = datetime.utcnow()
    for beispiel in _BEISPIELE:
        normalized = {
            "externe_id": beispiel["externe_id"],
            "direktlink": f"https://example.invalid/demo/{beispiel['externe_id']}",
            "titel": beispiel["titel"],
            "volltext": beispiel["volltext"],
            "kurzbeschreibung": beispiel["volltext"][:200],
            "vergabestelle": beispiel["vergabestelle"],
            "ort_region": "Berlin",
            "veroeffentlichungsdatum": (now - timedelta(days=2)).isoformat(),
            "angebotsfrist": (now + timedelta(days=beispiel["tage_bis_frist"])).isoformat(),
            "fragenfrist": None,
            "verfahrensart": "Offenes Verfahren",
            "cpv_codes": [],
            "geschaetzter_wert": beispiel["wert"],
            "dokumente_links": [],
            "zugangsart": "oeffentlich",
        }
        job = enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": normalized})
        run_duplicate(db, job)
        erzeugt += 1

    drain_queue(db)
    return erzeugt


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
        anzahl = run_demo_seed(db)
        print(f"Demo-Testdaten eingespielt: {anzahl} Ausschreibungen (Portal '{DEMO_PORTAL_SLUG}', inaktiv).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
