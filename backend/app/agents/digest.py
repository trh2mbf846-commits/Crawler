"""Kevins täglicher Kurzbericht (Nutzeranfrage 25.09.2026: "Kevin soll proaktiv unterstützen,

sich in meine Position versetzen"). Rein deterministisch aus der Datenbank berechnet (kein LLM
nötig) - funktioniert also auch ohne ANTHROPIC_API_KEY (wie in dieser Entwicklungsumgebung).
Wird von Kevins Chat-Seite beim Öffnen automatisch geladen und als erste Nachricht gezeigt, statt
dass Vincent erst fragen muss (siehe api/assistant.py: GET /assistant/digest). Berücksichtigt
Vincents Prioritäten (app/models.py:AssistantPreferences), falls gesetzt.

Zusätzlich (Nutzeranfrage 25.09.2026, echte Push-Benachrichtigung statt nur Pull): mit gesetzter
CRAWLER_DIGEST_WEBHOOK_URL schickt send_digest_webhook(...) denselben Bericht als einfachen
JSON-POST an eine Webhook-URL - kompatibel mit Slack/Discord/Mattermost-Incoming-Webhooks sowie
n8n/Zapier, da sowohl "text" als auch "content" mitgeschickt werden. Der Scheduler
(app/scheduler.py) ruft das täglich auf, wenn die URL konfiguriert ist.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import source_health
from app.config import settings
from app.models import AssistantPreferences, Portal, RankingScore, Tender

logger = logging.getLogger("ausschreibungscrawler.digest")

_NEU_FENSTER_STUNDEN = 24
_FRIST_FENSTER_TAGE = 7
_MAX_ZEILEN_JE_ABSCHNITT = 5
_MAX_TENDERS_IM_BERICHT = 8
_WEBHOOK_TIMEOUT_SEKUNDEN = 10.0


@dataclass
class DigestResult:
    text: str
    neue_relevante_anzahl: int
    bald_ablaufend_anzahl: int
    portale_mit_problem: list[str] = field(default_factory=list)
    tenders: list[Tender] = field(default_factory=list)


def build_daily_digest(db: Session) -> DigestResult:
    jetzt = datetime.utcnow()

    neue = list(
        db.scalars(
            select(Tender)
            .outerjoin(RankingScore, RankingScore.tender_id == Tender.id)
            .where(
                Tender.erfasst_am >= jetzt - timedelta(hours=_NEU_FENSTER_STUNDEN),
                Tender.ki_relevanz_score.in_(["stark", "moeglich"]),
            )
            .order_by(RankingScore.gesamtscore.desc().nulls_last())
        )
    )

    bald_ablaufend = list(
        db.scalars(
            select(Tender)
            .where(
                Tender.angebotsfrist.isnot(None),
                Tender.angebotsfrist >= jetzt,
                Tender.angebotsfrist <= jetzt + timedelta(days=_FRIST_FENSTER_TAGE),
                Tender.status != "abgelaufen",
                (Tender.gemerkt.is_(True)) | (Tender.ki_relevanz_score.in_(["stark", "moeglich"])),
            )
            .order_by(Tender.angebotsfrist.asc())
        )
    )

    portale_mit_problem = [
        p.name
        for p in db.scalars(select(Portal).where(Portal.aktiv.is_(True)))
        if source_health.evaluate(db, p)["status_ampel"] == "rot"
    ]

    praeferenzen = db.get(AssistantPreferences, "singleton")

    zeilen: list[str] = []
    if neue:
        zeilen.append(f"{len(neue)} neue relevante Ausschreibung(en) in den letzten {_NEU_FENSTER_STUNDEN}h:")
        for t in neue[:_MAX_ZEILEN_JE_ABSCHNITT]:
            zeilen.append(f"- {t.titel} ({t.portal.name}, {t.vergabestelle or 'Vergabestelle unbekannt'})")
    else:
        zeilen.append(f"Keine neuen relevanten Ausschreibungen in den letzten {_NEU_FENSTER_STUNDEN}h.")

    if bald_ablaufend:
        zeilen.append(f"\n{len(bald_ablaufend)} Frist(en) laufen in den nächsten {_FRIST_FENSTER_TAGE} Tagen ab:")
        for t in bald_ablaufend[:_MAX_ZEILEN_JE_ABSCHNITT]:
            frist = t.angebotsfrist.strftime("%d.%m.%Y") if t.angebotsfrist else "?"
            zeilen.append(f"- {t.titel} - Frist {frist}")
    else:
        zeilen.append(f"\nKeine dringenden Fristen in den nächsten {_FRIST_FENSTER_TAGE} Tagen.")

    if portale_mit_problem:
        zeilen.append(f"\n⚠️ Probleme bei: {', '.join(portale_mit_problem)}")

    if praeferenzen and praeferenzen.prioritaeten_text:
        zeilen.append(f"\n(Berücksichtigt deine Prioritäten: {praeferenzen.prioritaeten_text})")

    zusammengefasst: dict[str, Tender] = {}
    for t in neue[:_MAX_ZEILEN_JE_ABSCHNITT] + bald_ablaufend[:_MAX_ZEILEN_JE_ABSCHNITT]:
        zusammengefasst[t.id] = t

    return DigestResult(
        text="\n".join(zeilen),
        neue_relevante_anzahl=len(neue),
        bald_ablaufend_anzahl=len(bald_ablaufend),
        portale_mit_problem=portale_mit_problem,
        tenders=list(zusammengefasst.values())[:_MAX_TENDERS_IM_BERICHT],
    )


def send_digest_webhook(digest: DigestResult) -> bool:
    """Schickt den Kurzbericht als einfachen JSON-POST an CRAWLER_DIGEST_WEBHOOK_URL, falls

    gesetzt. "text" und "content" werden beide mitgeschickt, damit ohne Zusatzkonfiguration
    sowohl Slack/Mattermost-artige ("text") als auch Discord-artige ("content")
    Incoming-Webhooks sowie generische Automatisierungstools (n8n, Zapier) etwas Sinnvolles
    bekommen. Liefert False ohne konfigurierte URL oder bei jedem Fehlschlag (never crash den
    aufrufenden Scheduler-Job dafür) - der Pull-Kurzbericht in der Chat-Seite bleibt davon
    unberührt.
    """
    if not settings.digest_webhook_url:
        return False
    try:
        response = httpx.post(
            settings.digest_webhook_url,
            json={
                "text": digest.text,
                "content": digest.text,
                "neue_relevante_anzahl": digest.neue_relevante_anzahl,
                "bald_ablaufend_anzahl": digest.bald_ablaufend_anzahl,
                "portale_mit_problem": digest.portale_mit_problem,
            },
            timeout=_WEBHOOK_TIMEOUT_SEKUNDEN,
        )
        if response.status_code >= 400:
            logger.warning("Digest-Webhook lehnte den Bericht ab: HTTP %s", response.status_code)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Digest-Webhook nicht erreichbar: %s", exc)
        return False
