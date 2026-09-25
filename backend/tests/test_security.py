"""Tests für die API-Absicherung (app/security.py, Nutzeranfrage 25.09.2026)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_ohne_konfigurierten_schluessel_bleibt_api_offen(db):
    assert settings.api_key is None  # Testumgebung setzt bewusst keinen Schlüssel
    response = client.get("/api/portals")
    assert response.status_code == 200


def test_mit_konfiguriertem_schluessel_wird_zugriff_ohne_header_abgelehnt(db):
    settings.api_key = "geheim-123"
    try:
        response = client.get("/api/portals")
        assert response.status_code == 401
    finally:
        settings.api_key = None


def test_mit_konfiguriertem_schluessel_wird_falscher_header_abgelehnt(db):
    settings.api_key = "geheim-123"
    try:
        response = client.get("/api/portals", headers={"X-API-Key": "falsch"})
        assert response.status_code == 401
    finally:
        settings.api_key = None


def test_mit_konfiguriertem_schluessel_und_korrektem_header_erlaubt(db):
    settings.api_key = "geheim-123"
    try:
        response = client.get("/api/portals", headers={"X-API-Key": "geheim-123"})
        assert response.status_code == 200
    finally:
        settings.api_key = None


def test_health_endpoint_bleibt_immer_offen(db):
    settings.api_key = "geheim-123"
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
    finally:
        settings.api_key = None
