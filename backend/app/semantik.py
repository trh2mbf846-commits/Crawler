"""Suche nach Bedeutung (Nutzeranfrage 25.09.2026): findet Ausschreibungen auch dann, wenn sie
andere Wörter benutzen ("Sprachmodell", "Assistenzsystem zur automatischen Beantwortung" statt
"KI"). Ratgeber und Forschung zu Vergabesuche nennen genau das als Hauptschwäche reiner
Stichwortsuche.

Technik: ein kleines, mehrsprachiges Embedding-Modell über Ollama (settings.ollama_embedding_model,
lokal, kostenlos) übersetzt den Titel jeder offenen Ausschreibung einmalig in einen Bedeutungsvektor
(Tabelle tender_embeddings, im Nachlauf nach jeder Aktualisierung ergänzt). Eine Suchanfrage wird
ebenso übersetzt und per Kosinus-Ähnlichkeit verglichen.

Messung an echten Daten (26.09.2026, 5 echte KI-Ausschreibungen unter 155): nur der Titel (ohne
Beschreibung, ohne Anfrage-Instruktion) ordnete am besten - Ränge 1, 2, 4, 6/12. Absolute Werte
streuen aber stark und überlappen zwischen relevant und irrelevant, deshalb liefert
aehnlichkeiten() die ähnlichsten N (relativ zum besten Treffer) statt alles über einer festen
Schwelle. Die Bedeutungssuche ERGÄNZT die Stichwortsuche (Stichwort-Treffer zuerst), sie ersetzt
sie nicht.

Zweite Messung am kompletten Bestand (1547 Ausschreibungen, 7 Suchanfragen): bei eindeutigen
Begriffen gut ("Cybersecurity" -> Security Managed Services, "Streusalz Winterdienst" ->
Winterdienst), bei "künstliche Intelligenz"/"Sprachmodell"/"Chatbot" aber überwiegend
Fehltreffer wie "Maschinentechnik" oder "Zugfahrzeug" - mit bge-m3 nicht besser. Daher
EXPERIMENTELL und standardmäßig aus (CRAWLER_SEMANTIK_AKTIV=true schaltet es ein).

Ohne Ollama bzw. Modell bleibt einfach die normale Stichwortsuche aktiv.
"""
from __future__ import annotations

import logging
import math
from array import array

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Tender, TenderEmbedding

logger = logging.getLogger("ausschreibungscrawler.semantik")

_STAPEL = 32
_OFFEN = ("abgelaufen", "vergeben")


_TEXTVARIANTE = "titel"  # Teil des gespeicherten Modellnamens: ändert sich die Variante, wird neu berechnet


def _modell_kennung() -> str:
    return f"{settings.ollama_embedding_model}#{_TEXTVARIANTE}"


def _text(tender: Tender) -> str:
    return tender.titel


def einbetten(texte: list[str], timeout: float = 300.0) -> list[list[float]] | None:
    """Vektoren für mehrere Texte (normiert), None wenn Ollama/Modell nicht verfügbar."""
    try:
        antwort = httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/embed",
            json={"model": settings.ollama_embedding_model, "input": texte},
            timeout=timeout,
        )
        antwort.raise_for_status()
        vektoren = antwort.json().get("embeddings") or []
    except Exception as exc:
        logger.info("Embedding nicht verfügbar: %s", exc)
        return None
    if len(vektoren) != len(texte):
        return None
    ergebnis = []
    for v in vektoren:
        laenge = math.sqrt(sum(x * x for x in v)) or 1.0
        ergebnis.append([x / laenge for x in v])
    return ergebnis


def _als_bytes(vektor: list[float]) -> bytes:
    return array("f", vektor).tobytes()


def _aus_bytes(daten: bytes) -> array:
    werte = array("f")
    werte.frombytes(daten)
    return werte


def aktualisiere_embeddings(db: Session, limit: int | None = None) -> int:
    """Fehlende Vektoren für offene Ausschreibungen berechnen. Liefert die Anzahl neuer Vektoren.
    Nur bei CRAWLER_SEMANTIK_AKTIV=true (experimentell, siehe config.py)."""
    if not settings.semantik_aktiv:
        return 0
    modell = _modell_kennung()
    offen = db.scalars(
        select(Tender)
        .outerjoin(TenderEmbedding, TenderEmbedding.tender_id == Tender.id)
        .where(Tender.status.not_in(_OFFEN))
        .where((TenderEmbedding.tender_id.is_(None)) | (TenderEmbedding.modell != modell))
    ).all()
    if limit is not None:
        offen = offen[:limit]
    neu = 0
    for start in range(0, len(offen), _STAPEL):
        stapel = offen[start:start + _STAPEL]
        vektoren = einbetten([_text(t) for t in stapel])
        if vektoren is None:
            break
        for tender, vektor in zip(stapel, vektoren):
            vorhanden = db.get(TenderEmbedding, tender.id)
            if vorhanden is None:
                db.add(TenderEmbedding(tender_id=tender.id, modell=modell, vektor=_als_bytes(vektor)))
            else:
                vorhanden.modell, vorhanden.vektor = modell, _als_bytes(vektor)
            neu += 1
        db.commit()
    if neu:
        logger.info("Suche nach Bedeutung: %d Ausschreibungen neu erfasst.", neu)
    return neu


def aehnlichkeiten(db: Session, anfrage: str) -> dict[str, float] | None:
    """Die der Anfrage ähnlichsten Ausschreibungen (höchstens settings.semantik_max_treffer,
    nur solche nah am besten Treffer). None = Bedeutungssuche nicht verfügbar."""
    if not settings.semantik_aktiv:
        return None
    vektoren = einbetten([anfrage], timeout=60)
    if not vektoren:
        return None
    frage = vektoren[0]
    werte = [
        (sum(a * b for a, b in zip(frage, _aus_bytes(daten))), tender_id)
        for tender_id, daten in db.execute(
            select(TenderEmbedding.tender_id, TenderEmbedding.vektor).where(TenderEmbedding.modell == _modell_kennung())
        )
    ]
    if not werte:
        return {}
    werte.sort(reverse=True)
    grenze = werte[0][0] * settings.semantik_relativ
    return {tid: wert for wert, tid in werte[: settings.semantik_max_treffer] if wert >= grenze}
