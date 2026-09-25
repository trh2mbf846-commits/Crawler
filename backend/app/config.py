"""Zentrale Konfiguration (Kapitel 5.3, 12 - Sicherheit: Zugangsdaten nur aus Umgebungsvariablen)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLER_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'ausschreibungscrawler.db'}"

    # Ranking-Gewichte, Kapitel 20.5 - zentral konfigurierbar, nicht hart codiert.
    ranking_weight_ki_relevanz: float = 0.4
    ranking_weight_dringlichkeit: float = 0.3
    ranking_weight_profil: float = 0.2
    ranking_weight_aktualitaet: float = 0.1

    # Source Health Schwellenwerte, Kapitel 21.3.
    health_null_treffer_warnung_ab: int = 1
    health_null_treffer_eskalation_ab: int = 3
    health_fehlerrate_warnung: float = 0.2
    health_ausfall_faktor_intervall: float = 3.0
    health_trefferrueckgang_warnung: float = 0.5

    # Optionaler LLM-Einsatz (Kapitel 4.3, 8.3, 25) - ohne Key laeuft die reine
    # Keyword-/CPV-Klassifikation weiter, LLM-Nachbewertung wird uebersprungen.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    http_user_agent: str = "AusschreibungsCrawlerBot/0.1 (+Kontakt: siehe Portal-Konfiguration)"
    http_request_delay_seconds: float = 1.5  # Rate-Limiting, Kapitel 9.1

    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]

    # API-Absicherung (Nutzeranfrage 25.09.2026): seit Crawler Kevin echte Aktionen auslösen kann
    # (Läufe starten, Suchprofile anlegen, Datensätze ändern), wiegt eine komplett offene API
    # deutlich schwerer. Ohne gesetzten Schlüssel bleibt die API wie bisher offen
    # (Entwicklungs-Default) - für ein echtes Deployment sollte er gesetzt werden, siehe
    # app/security.py und README (Deployment-Abschnitt).
    api_key: str | None = None

    # Nutzerwunsch (01.09.2026): kein dauerhaftes Hintergrund-Update, sondern ein manueller
    # Aktualisieren-Button (siehe api/run.py). Für lokale Entwicklung/Tests bleibt der
    # periodische Scheduler an; im on-demand-Deployment (render.yaml) wird er per
    # CRAWLER_SCHEDULER_ENABLED=false abgeschaltet.
    scheduler_enabled: bool = True


settings = Settings()
(BACKEND_DIR / "data").mkdir(parents=True, exist_ok=True)
