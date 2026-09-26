"""Benachrichtigung bei neuen Treffern (Nutzeranfrage 25.09.2026: Alerts, damit man nicht selbst
nachsehen muss - laut Ratgebern die am meisten genutzte Funktion professioneller Ausschreibungstools).

Meldet nach jeder Aktualisierung (und KI-Nachprüfung) einmalig:
- neue Treffer zu aktiven Suchprofilen, gruppiert je Profil - oder, solange noch kein Suchprofil
  angelegt ist, neue stark KI-relevante Ausschreibungen;
- per Mac-Mitteilung (osascript, nur unter macOS) und, falls CRAWLER_DIGEST_WEBHOOK_URL gesetzt
  ist, zusätzlich an diesen Webhook (Slack/Discord/Mattermost/n8n/Zapier).

Treffer werden vor dem Melden erneut gegen das Profil geprüft - die KI-Nachprüfung kann eine
Ausschreibung inzwischen herabgestuft haben; solche Treffer werden entfernt statt gemeldet.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.search import profile_matches
from app.config import settings
from app.models import SearchProfile, SearchProfileHit, Tender

logger = logging.getLogger("ausschreibungscrawler.benachrichtigung")

_OFFEN = ("abgelaufen", "vergeben")


@dataclass
class Meldung:
    titel: str
    text: str
    anzahl: int
    tenders: list[Tender] = field(default_factory=list)


def sammle_neue_treffer(db: Session) -> list[Meldung]:
    profile = list(db.scalars(select(SearchProfile).where(SearchProfile.aktiv.is_(True))))
    meldungen: list[Meldung] = []
    if profile:
        for profil in profile:
            neue: list[Tender] = []
            for hit in db.scalars(
                select(SearchProfileHit).where(
                    SearchProfileHit.profile_id == profil.id, SearchProfileHit.benachrichtigt.is_(False)
                )
            ):
                tender = db.get(Tender, hit.tender_id)
                if tender is None or tender.status in _OFFEN or not profile_matches(profil, tender):
                    db.delete(hit)  # nicht (mehr) passend, z. B. durch KI-Nachprüfung herabgestuft
                    continue
                hit.benachrichtigt = True
                neue.append(tender)
            if neue:
                meldungen.append(_meldung(f"{len(neue)} neue Treffer: {profil.name}", neue))
    else:
        neue = list(
            db.scalars(
                select(Tender).where(
                    Tender.ki_relevanz_score == "stark",
                    Tender.ki_benachrichtigt.is_(False),
                    Tender.status.not_in(_OFFEN),
                    # Nur wirklich neu Erfasstes - sonst meldete das erste Update nach Einführung
                    # dieser Funktion den kompletten Altbestand als "neu".
                    Tender.erfasst_am >= datetime.utcnow() - timedelta(days=2),
                )
            )
        )
        for tender in neue:
            tender.ki_benachrichtigt = True
        if neue:
            meldungen.append(_meldung(f"{len(neue)} neue KI-Ausschreibungen", neue))
    db.commit()
    return meldungen


def _meldung(titel: str, tenders: list[Tender]) -> Meldung:
    tenders = sorted(tenders, key=lambda t: (t.angebotsfrist is None, t.angebotsfrist or 0))
    zeilen = [t.titel for t in tenders[:3]]
    if len(tenders) > 3:
        zeilen.append(f"… und {len(tenders) - 3} weitere")
    return Meldung(titel=titel, text="\n".join(zeilen), anzahl=len(tenders), tenders=tenders)


def _mac_mitteilung(meldung: Meldung) -> bool:
    if not settings.benachrichtigung_mac or sys.platform != "darwin" or not shutil.which("osascript"):
        return False

    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " · ")

    skript = f'display notification "{esc(meldung.text)[:230]}" with title "Ausschreibungs-Crawler" subtitle "{esc(meldung.titel)}"'
    try:
        subprocess.run(["osascript", "-e", skript], check=True, timeout=10, capture_output=True)
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Mac-Mitteilung konnte nicht angezeigt werden: %s", exc)
        return False


def _webhook(meldung: Meldung) -> bool:
    if not settings.digest_webhook_url:
        return False
    text = f"{meldung.titel}\n" + "\n".join(
        f"- {t.titel} ({t.direktlink})" for t in meldung.tenders[:10]
    )
    try:
        antwort = httpx.post(settings.digest_webhook_url, json={"text": text, "content": text}, timeout=15)
        return antwort.status_code < 400
    except httpx.HTTPError as exc:
        logger.warning("Benachrichtigungs-Webhook nicht erreichbar: %s", exc)
        return False


def benachrichtige(db: Session) -> list[Meldung]:
    meldungen = sammle_neue_treffer(db)
    for meldung in meldungen:
        mac = _mac_mitteilung(meldung)
        web = _webhook(meldung)
        logger.info("Benachrichtigung „%s“ (Mac: %s, Webhook: %s)", meldung.titel, mac, web)
    return meldungen
