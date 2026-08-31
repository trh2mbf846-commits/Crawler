"""Seed der Portal-Konfiguration (Kapitel 3, 9.3) und der Kategorien-Taxonomie (Kapitel 7).

Nur die 3 vom Auftraggeber vorgegebenen Portale werden angelegt (Kapitel 16.2). Die von Claude
Code vorgeschlagenen Ergänzungsportale (Kapitel 16.3 / 3) werden bewusst NICHT automatisch
angelegt, da laut Handlungsanweisung eine kurze Abstimmung mit Vincent vor Phase 3 aussteht.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.classification import CATEGORY_ORDER
from app.db import SessionLocal, init_db
from app.models import Category, Portal

PFLICHT_PORTALE = [
    dict(
        slug="vergabekooperation-berlin",
        name="Vergabeplattform Berlin (Vergabekooperation Berlin)",
        base_url="https://vergabekooperation.berlin/NetServer/LoginControllerServlet?function=CookiesCheckDone",
        betreiber="Land Berlin – zentrale Vergabeplattform für Berliner Vergabestellen, u. a. BVG",
        robots_status="ungeprueft",
        tos_hinweis=(
            "Noch nicht geprüft: In dieser Entwicklungsumgebung ist ausgehender Internetzugriff "
            "blockiert (Egress-Proxy), robots.txt/ToS konnten nicht abgerufen werden. Vor "
            "Produktivbetrieb gemäß Kapitel 9.3 nachholen."
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
            "Noch nicht geprüft (siehe oben). Zusätzlich vermutlich JS-basierte SPA - "
            "Playwright-Browser konnten in dieser Umgebung mangels Netzzugriff nicht installiert werden."
        ),
        intervall_minuten=180,
        vorgegeben=True,
    ),
    dict(
        slug="itdz-berlin",
        name="ITDZ Berlin – Aktuelle Ausschreibungen",
        base_url="https://www.itdz-berlin.de/unternehmen/ausschreibungen/aktuelle-ausschreibungen/",
        betreiber="IT-Dienstleistungszentrum Berlin (Land Berlin)",
        robots_status="ungeprueft",
        tos_hinweis="Noch nicht geprüft (siehe oben).",
        intervall_minuten=120,
        vorgegeben=True,
    ),
]


def run_seed(db: Session) -> None:
    for name in CATEGORY_ORDER:
        if db.scalars(select(Category).where(Category.name == name)).first() is None:
            db.add(Category(name=name))

    for daten in PFLICHT_PORTALE:
        if db.scalars(select(Portal).where(Portal.slug == daten["slug"])).first() is None:
            db.add(Portal(**daten))

    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
        print(f"Seed abgeschlossen: {len(PFLICHT_PORTALE)} Portale, {len(CATEGORY_ORDER)} Kategorien.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
