"""Platzhalter-Connector für Portale, die bereits als Quelle registriert sind (Kapitel 3/16,

Nutzeranfrage 01.09.2026: mindestens 10 Quellen sichtbar), deren Connector-Logik aber noch
nicht fertig implementiert ist. Liefert einen klaren, sprechenden Fehler statt eines
generischen "Kein Connector registriert" - taucht im Quellstatus-Dashboard nachvollziehbar
als "in Vorbereitung" auf, statt den Lauf unklar abzubrechen.
"""
from __future__ import annotations

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure


def make_pending_connector(slug: str, name: str, base_url: str, hinweis: str) -> type[BaseConnector]:
    # WICHTIG: Die abstrakten Methoden müssen bereits im Klassenkörper (nicht per nachträglicher
    # Attributzuweisung) definiert werden - sonst berücksichtigt ABCMeta sie nicht bei der
    # Berechnung von __abstractmethods__, und die Klasse bleibt trotz "vorhandener" Methoden
    # abstrakt und nicht instanziierbar (TypeError beim ersten echten Lauf).
    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        raise TechnicalFailure(
            f"Connector für '{name}' ist als Quelle registriert, aber noch nicht implementiert. {hinweis}"
        )

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:  # pragma: no cover - nie erreicht
        raise TechnicalFailure(f"Connector für '{name}' ist noch nicht implementiert.")

    return type(
        f"Pending_{slug.replace('-', '_')}",
        (BaseConnector,),
        {
            "slug": slug,
            "name": name,
            "base_url": base_url,
            "vorgegeben": False,
            "robots_status": "ungeprueft",
            "tos_hinweis": hinweis,
            "fetch_list_page": fetch_list_page,
            "fetch_detail": fetch_detail,
        },
    )
