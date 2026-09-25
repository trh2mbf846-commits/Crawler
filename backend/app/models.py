"""SQLAlchemy-Modelle nach dem Datenmodell aus Kapitel 6 und dem SQL-Schema aus Kapitel 22.

Hinweis: Die Handlungsanweisung gibt das Schema im PostgreSQL-Dialekt vor (UUID, TEXT[],
JSONB, tsvector-GIN-Index). Für die lokale Entwicklung läuft dieses Projekt gegen SQLite
(einfacher Start ohne DB-Server, siehe README); daher werden UUID als String, Arrays als
JSON-Liste und Volltextsuche als einfache LIKE-Abfrage über die Repository-Schicht abgebildet.
Das vollständige PostgreSQL-DDL aus Kapitel 22 liegt unverändert in
`docs/schema_postgresql.sql` für den späteren Produktivbetrieb bereit;
Tabellennamen, Spalten und Fremdschlüsselbeziehungen sind zwischen beiden identisch.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Portal(Base):
    __tablename__ = "portals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    betreiber: Mapped[str | None] = mapped_column(Text, nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # geprueft_ok | geprueft_einschraenkung | ungeprueft (Kapitel 9.3)
    robots_status: Mapped[str] = mapped_column(String, nullable=False, default="ungeprueft")
    tos_hinweis: Mapped[str | None] = mapped_column(Text, nullable=True)
    intervall_minuten: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    vorgegeben: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenders: Mapped[list["Tender"]] = relationship(back_populates="portal")


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (UniqueConstraint("portal_id", "dedupe_hash", name="uq_tender_dedupe"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    portal_id: Mapped[str] = mapped_column(String, ForeignKey("portals.id"), nullable=False)
    externe_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    titel: Mapped[str] = mapped_column(Text, nullable=False)
    kurzbeschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    volltext: Mapped[str | None] = mapped_column(Text, nullable=True)
    vergabestelle: Mapped[str | None] = mapped_column(Text, nullable=True)
    ort_region: Mapped[str | None] = mapped_column(Text, nullable=True)
    veroeffentlichungsdatum: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    angebotsfrist: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fragenfrist: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verfahrensart: Mapped[str | None] = mapped_column(Text, nullable=True)
    cpv_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    geschaetzter_wert: Mapped[float | None] = mapped_column(Float, nullable=True)
    direktlink: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="neu")
    zugangsart: Mapped[str] = mapped_column(String, nullable=False, default="oeffentlich")
    # stark | moeglich | nicht | NULL (noch nicht bewertet)
    ki_relevanz_score: Mapped[str | None] = mapped_column(String, nullable=True)
    ki_relevanz_konfidenz: Mapped[float | None] = mapped_column(Float, nullable=True)
    ki_relevanz_begruendung: Mapped[str | None] = mapped_column(Text, nullable=True)
    ki_relevanz_quelle: Mapped[str | None] = mapped_column(String, nullable=True)  # keyword|cpv|llm
    dedupe_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Heuristische, portalübergreifende Duplikaterkennung (Nutzeranfrage 25.09.2026: bekannte
    # Überschneidung Bekanntmachungsservice/TED/DTVP). Der oben stehende dedupe_hash ist bewusst
    # je Portal isoliert (Kapitel 5.3) und erkennt daher NICHT, wenn dieselbe Ausschreibung über
    # mehrere Portale läuft - diese beiden Felder ergänzen das um einen unverbindlichen Hinweis,
    # ohne Datensätze zusammenzuführen (Ähnlichkeit ist nie sicher genug für ein automatisches
    # Merge, siehe app/agents/duplicate.py:_erkenne_cross_portal_duplikat).
    moeglicherweise_duplikat_von: Mapped[str | None] = mapped_column(String, nullable=True)
    moeglicherweise_duplikat_hinweis: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Von Vincent (manuell oder über Crawler Kevin, Nutzeranfrage 25.09.2026 "Kevin darf alle
    # drei Sachen") als interessant markiert - rein persönliche Merkliste, keine fachliche
    # Bewertung wie ki_relevanz_score.
    gemerkt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    merk_notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    erfasst_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    zuletzt_geprueft_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portal: Mapped[Portal] = relationship(back_populates="tenders")
    dokumente: Mapped[list["TenderDocument"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    history: Mapped[list["TenderHistory"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", order_by="TenderHistory.erkannt_am"
    )
    kategorien: Mapped[list["TenderCategory"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    ranking: Mapped["RankingScore | None"] = relationship(
        back_populates="tender", cascade="all, delete-orphan", uselist=False
    )


class TenderDocument(Base):
    __tablename__ = "tender_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tender_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    titel: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Zusatz (25.09.2026, Nutzerrecherche zu guten Crawling-Agenten): bei PDF-Vergabeunterlagen
    # best-effort extrahierter Text statt nur des Links, siehe app/agents/document_extraction.py.
    # NULL, wenn kein PDF, Download/Parsing fehlgeschlagen, oder (noch) nicht versucht.
    volltext: Mapped[str | None] = mapped_column(Text, nullable=True)

    tender: Mapped[Tender] = relationship(back_populates="dokumente")


class TenderHistory(Base):
    __tablename__ = "tender_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tender_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    feld: Mapped[str] = mapped_column(Text, nullable=False)
    alter_wert: Mapped[str | None] = mapped_column(Text, nullable=True)
    neuer_wert: Mapped[str | None] = mapped_column(Text, nullable=True)
    erkannt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tender: Mapped[Tender] = relationship(back_populates="history")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    tenders: Mapped[list["TenderCategory"]] = relationship(back_populates="category")


class TenderCategory(Base):
    __tablename__ = "tender_categories"

    tender_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[str] = mapped_column(String, ForeignKey("categories.id"), primary_key=True)

    tender: Mapped[Tender] = relationship(back_populates="kategorien")
    category: Mapped[Category] = relationship(back_populates="tenders")


class AssistantPreferences(Base):
    """Vincents Prioritäten für Crawler Kevin (Nutzeranfrage 25.09.2026: "Kevin soll sich in

    meine Position versetzen"). Bewusst ein Singleton (eine Zeile, feste id) statt ein eigenes
    Benutzerkonto-System - diese Anwendung hat nur einen Nutzer (Kapitel 5.2: kein
    überdimensionierter Mechanismus). Fließt in Kevins Systemprompt (app/agents/assistant.py)
    und in den täglichen Kurzbericht (app/agents/digest.py) ein.
    """
    __tablename__ = "assistant_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "singleton")
    prioritaeten_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    bevorzugte_kategorien: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    bevorzugte_regionen: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mindestwert: Mapped[float | None] = mapped_column(Float, nullable=True)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    portale: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    filter_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hits: Mapped[list["SearchProfileHit"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class SearchProfileHit(Base):
    __tablename__ = "search_profile_hits"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("search_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    tender_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.id", ondelete="CASCADE"), primary_key=True
    )
    gesehen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    markiert_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped[SearchProfile] = relationship(back_populates="hits")
    tender: Mapped[Tender] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # discovery|analysis|normalization|duplicate|classification|search|source_health
    typ: Mapped[str] = mapped_column(String, nullable=False)
    portal_id: Mapped[str | None] = mapped_column(String, ForeignKey("portals.id"), nullable=True)
    ziel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # queued|running|succeeded|failed|waiting_for_decision
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    versuch_nr: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_versuche: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    fehler: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    gestartet_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    beendet_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    events: Mapped[list["JobEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    agent: Mapped[str] = mapped_column(String, nullable=False)
    ereignis: Mapped[str] = mapped_column(String, nullable=False)  # started|succeeded|failed|escalated
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dauer_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zeitstempel: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship(back_populates="events")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str | None] = mapped_column(String, ForeignKey("jobs.id"), nullable=True)
    portal_id: Mapped[str | None] = mapped_column(String, ForeignKey("portals.id"), nullable=True)
    # login_erforderlich|captcha|tos_verbot|ip_sperre|kategorisierung_unklar|sonstiges
    kategorie: Mapped[str] = mapped_column(String, nullable=False)
    kontext: Mapped[str] = mapped_column(Text, nullable=False)
    optionen: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    empfehlung: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="offen")  # offen|beantwortet|geparkt
    entscheidung: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    beantwortet_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SourceHealthMetric(Base):
    __tablename__ = "source_health_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    portal_id: Mapped[str] = mapped_column(String, ForeignKey("portals.id"), nullable=False)
    lauf_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    erfolgreich: Mapped[bool] = mapped_column(Boolean, nullable=False)
    treffer_anzahl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neu_anzahl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aktualisiert_anzahl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fehlerrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fehlertyp: Mapped[str | None] = mapped_column(String, nullable=True)
    dauer_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RankingScore(Base):
    __tablename__ = "ranking_scores"

    tender_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.id", ondelete="CASCADE"), primary_key=True
    )
    ki_relevanz_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dringlichkeit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profil_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aktualitaet_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gesamtscore: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    berechnet_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tender: Mapped[Tender] = relationship(back_populates="ranking")
