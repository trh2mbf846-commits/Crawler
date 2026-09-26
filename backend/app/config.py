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
    # 2 statt 1 (26.09.2026): kleine Portale wie ITDZ Berlin haben regelmäßig einfach gerade keine
    # offene Ausschreibung - ein einzelner 0-Treffer-Lauf ist kein Warnsignal.
    health_null_treffer_warnung_ab: int = 2
    health_null_treffer_eskalation_ab: int = 3
    health_fehlerrate_warnung: float = 0.2
    # Fehlerrate erst ab so vielen fehlgeschlagenen Schritten werten: seit dem inkrementellen
    # Abrufen hat ein Lauf oft nur wenige Schritte, ein einzelner Fehlschlag ergäbe sonst gleich 33 %.
    health_fehlerrate_min_fehler: int = 3
    health_ausfall_faktor_intervall: float = 3.0
    health_trefferrueckgang_warnung: float = 0.5

    # Optionaler LLM-Einsatz (Kapitel 4.3, 8.3, 25) - ohne Key laeuft die reine
    # Keyword-/CPV-Klassifikation weiter, LLM-Nachbewertung wird uebersprungen.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # Crawler Kevin ohne API-Kosten (Nutzerwunsch 25.09.2026: "Kevins Antworten kostenlos"):
    # lokales Sprachmodell über Ollama (https://ollama.com), siehe app/agents/assistant.py.
    # "auto" = Claude, wenn CRAWLER_ANTHROPIC_API_KEY gesetzt ist, sonst Ollama.
    kevin_anbieter: str = "auto"  # auto | anthropic | ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout_seconds: float = 300.0
    # Suche nach Bedeutung (app/semantik.py) - EXPERIMENTELL und standardmäßig aus: Messungen an
    # echten Daten (26.09.2026, qwen3-embedding:0.6b und bge-m3) ergaben bei kurzen, allgemeinen
    # Ausschreibungstiteln zu unzuverlässige Treffer. Kevin nutzt stattdessen Synonym-Suche.
    semantik_aktiv: bool = False
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    # Absolute Ähnlichkeitswerte streuen je Anfrage stark (Messung 26.09.2026: relevante 0,22-0,62,
    # irrelevante bis 0,62) - daher relative Auswahl: die ähnlichsten N, sofern nah am besten Treffer.
    semantik_max_treffer: int = 10
    semantik_relativ: float = 0.85  # Anteil der Ähnlichkeit des besten Treffers

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

    # Inkrementelles Crawling: unveränderte, bekannte Ausschreibungen erst nach so vielen Tagen
    # wieder im Detail abrufen (Sicherheitsnetz für Änderungen, die in der Liste nicht sichtbar sind).
    detail_neupruefung_tage: int = 7
    # Fehlende Angebotsfristen aus der Verfahrensseite ergänzen (agents/frist_ergaenzung.py):
    # höchstens so viele Ausschreibungen pro Nachlauf (je ein höflicher Seitenabruf).
    frist_ergaenzung_pro_lauf: int = 40

    # Tägliche automatische Aktualisierung (Nutzeranfrage 25.09.2026), lokale Uhrzeit "HH:MM",
    # leer = aus. Unabhängig von scheduler_enabled, siehe app/tagesaktualisierung.py.
    auto_aktualisieren_uhrzeit: str = "07:00"

    # Benachrichtigung bei neuen Treffern (Nutzeranfrage 25.09.2026), siehe app/benachrichtigung.py:
    # Mac-Mitteilung (nur unter macOS wirksam) und - falls gesetzt - zusätzlich an
    # CRAWLER_DIGEST_WEBHOOK_URL.
    benachrichtigung_mac: bool = True

    # Proaktive Push-Benachrichtigung (Nutzeranfrage 25.09.2026, "was können gute Agenten noch"):
    # Kevins Kurzbericht (app/agents/digest.py) lädt bisher nur beim Öffnen des Tabs (Pull). Mit
    # gesetzter Webhook-URL schickt der Scheduler ihn zusätzlich täglich unaufgefordert dorthin
    # (Slack/Discord/Mattermost-Incoming-Webhook, n8n, Zapier o. ä. - alle akzeptieren einen
    # simplen JSON-POST mit "text"/"content"). Ohne gesetzten Wert bleibt es beim reinen
    # Pull-Kurzbericht wie bisher, nur der Scheduler muss dafür laufen (CRAWLER_SCHEDULER_ENABLED).
    digest_webhook_url: str | None = None
    digest_stunde: int = 7  # Uhrzeit (UTC) für den täglichen Kurzbericht, falls Webhook gesetzt


settings = Settings()
(BACKEND_DIR / "data").mkdir(parents=True, exist_ok=True)
