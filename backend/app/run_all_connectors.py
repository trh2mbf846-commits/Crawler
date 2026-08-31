"""Manuell auslösbarer Testlauf aller drei Pflicht-Connectoren (Kapitel 14 Phase 1, Kapitel 15).

Aufruf: python -m app.run_all_connectors
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Portal
from app.pipeline import run_portal_cycle
from app.seed import run_seed


def main() -> int:
    init_db()
    db = SessionLocal()
    exit_code = 0
    try:
        run_seed(db)
        portale = list(db.scalars(select(Portal).order_by(Portal.name)))
        if not portale:
            print("Keine Portale konfiguriert.")
            return 1

        for portal in portale:
            print(f"\n=== Testlauf: {portal.name} ({portal.slug}) ===")
            try:
                ergebnis = run_portal_cycle(db, portal)
                print(f"Ergebnis: {ergebnis}")
                if ergebnis["quellstatus"]["status_ampel"] == "rot":
                    exit_code = 2
            except Exception as exc:  # Testlauf soll die übrigen Portale nicht verhindern (Kapitel 9.4).
                print(f"Unerwarteter Fehler bei {portal.slug}: {exc}")
                exit_code = 2
        return exit_code
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
