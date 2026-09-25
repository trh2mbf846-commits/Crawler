"""API-Absicherung (Nutzeranfrage 25.09.2026): seit Crawler Kevin echte Aktionen auslösen kann

(Läufe starten, Suchprofile anlegen, Datensätze ändern), wiegt eine komplett offene API deutlich
schwerer als vorher. Einfacher, für eine Single-User-Anwendung ausreichender Mechanismus: ein
gemeinsames API-Schlüssel-Geheimnis statt eines vollen Login-Systems (Kapitel 5.2: kein
überdimensionierter Mechanismus für einen Einzelnutzer-Dienst - hier gibt es nur Vincent, keine
Rollen/Rechte zu unterscheiden).

Ist CRAWLER_API_KEY nicht gesetzt, bleibt die API wie bisher komplett offen (Entwicklungs-Default,
damit `uvicorn --reload` ohne Zusatzschritt weiterläuft) - für ein echtes Deployment MUSS er
gesetzt werden (siehe README, Deployment-Abschnitt). /api/health bleibt bewusst ungeschützt
(Load-Balancer-/Uptime-Checks brauchen keinen Schlüssel).
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(401, "Ungültiger oder fehlender API-Schlüssel (Header X-API-Key).")
