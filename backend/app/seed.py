"""Seed der Portal-Konfiguration (Kapitel 3, 9.3) und der Kategorien-Taxonomie (Kapitel 7).

Die 3 vom Auftraggeber vorgegebenen Portale (Kapitel 16.2) sowie die Zusatzportale aus Kapitel
16.3 werden angelegt - die dort vorgesehene kurze Abstimmung mit Vincent ist durch die
Nutzeranfrage vom 01.09.2026 ("nehme die ganzen Vergabeportale mit auf") erfolgt. Portale ohne
fertigen Connector sind trotzdem als Quelle sichtbar (Quellstatus-Dashboard zeigt "in
Vorbereitung", siehe app/agents/connector/pending.py) statt erst nach vollständiger
Implementierung zu erscheinen.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.classification import CATEGORY_ORDER
from app.agents.connector import ZUSATZPORTALE
from app.db import SessionLocal, init_db
from app.models import Category, Portal

PFLICHT_PORTALE = [
    dict(
        slug="vergabekooperation-berlin",
        name="Vergabeplattform Berlin (Vergabekooperation Berlin)",
        base_url="https://vergabekooperation.berlin/NetServer/LoginControllerServlet?function=CookiesCheckDone",
        betreiber="Land Berlin – zentrale Vergabeplattform für Berliner Vergabestellen, u. a. BVG",
        robots_status="geprueft_ok",
        tos_hinweis=(
            "Geprüft 31.08.2026: keine robots.txt vorhanden (404). Teilnahmebedingungen verlangen "
            "Registrierung nur für die Angebotsabgabe, nicht fürs Einsehen öffentlicher "
            "Bekanntmachungen. Kein Hinweis auf Verbot automatisierten Abrufs. Details siehe "
            "docs/portal-notes.md."
        ),
        intervall_minuten=180,
        vorgegeben=True,
    ),
    dict(
        slug="db-bieterportal",
        name="DB Bieterportal (e-Vergabe Deutsche Bahn)",
        base_url="https://bieterportal.noncd.db.de/evergabe.bieter/eva/supplierportal/portal/tabs/vergaben",
        betreiber="Deutsche Bahn AG – konzernweite Vergabeplattform",
        robots_status="ungeprueft",
        tos_hinweis=(
            "Kein echtes robots.txt (Server liefert für jeden Pfad die SPA-Startseite). "
            "Technischer Blocker in dieser Session: Chromium/Playwright-Navigation zu diesem Host "
            "scheitert am Egress-Proxy (WebSocket-Upgrades nicht unterstützt), obwohl einfache "
            "HTTP-Abrufe funktionieren - kein Login/CAPTCHA auf der Seite selbst erkennbar. "
            "Details und Empfehlung siehe docs/portal-notes.md."
        ),
        intervall_minuten=180,
        vorgegeben=True,
    ),
    dict(
        slug="itdz-berlin",
        name="ITDZ Berlin – Aktuelle Ausschreibungen",
        base_url="https://www.itdz-berlin.de/unternehmen/ausschreibungen/aktuelle-ausschreibungen/",
        betreiber="IT-Dienstleistungszentrum Berlin (Land Berlin)",
        robots_status="geprueft_ok",
        tos_hinweis=(
            "Geprüft 31.08.2026: robots.txt erlaubt automatisierten Zugriff explizit bei klarer "
            "User-Agent-Kennung; relevante Disallow-Regeln betreffen diese Seite nicht. Details "
            "siehe docs/portal-notes.md."
        ),
        intervall_minuten=120,
        vorgegeben=True,
    ),
]

# Zusatzportale mit fertig implementiertem, echtem Connector (Kapitel 9.1: "gut machbar" laut
# Recherche vom 04.09.2026) - laufen automatisch im Scheduler. Alle anderen ZUSATZPORTALE
# bleiben inaktiv (blockiert/eingeschränkt/noch nicht umgesetzt, siehe deren tos_hinweis).
AKTIVE_ZUSATZ_SLUGS = {"ted", "dtvp", "evergabe-bund", "oeffentlichevergabe"}


def run_seed(db: Session) -> None:
    for name in CATEGORY_ORDER:
        if db.scalars(select(Category).where(Category.name == name)).first() is None:
            db.add(Category(name=name))

    for daten in PFLICHT_PORTALE:
        if db.scalars(select(Portal).where(Portal.slug == daten["slug"])).first() is None:
            db.add(Portal(**daten))

    for zusatz in ZUSATZPORTALE:
        if db.scalars(select(Portal).where(Portal.slug == zusatz["slug"])).first() is None:
            db.add(
                Portal(
                    slug=zusatz["slug"],
                    name=zusatz["name"],
                    base_url=zusatz["base_url"],
                    betreiber=zusatz["betreiber"],
                    robots_status=zusatz["robots_status"],
                    tos_hinweis=zusatz["hinweis"],
                    intervall_minuten=zusatz["intervall_minuten"],
                    vorgegeben=False,
                    aktiv=zusatz["slug"] in AKTIVE_ZUSATZ_SLUGS,
                )
            )

    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
        anzahl = len(PFLICHT_PORTALE) + len(ZUSATZPORTALE)
        print(f"Seed abgeschlossen: {anzahl} Portale, {len(CATEGORY_ORDER)} Kategorien.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
