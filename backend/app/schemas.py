"""Pydantic-Schemas für die REST-API (Kapitel 23)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PortalRef(BaseModel):
    id: str
    name: str


class TenderOut(BaseModel):
    id: str
    titel: str
    kurzbeschreibung: str | None
    vergabestelle: str | None
    ort_region: str | None
    portal: PortalRef
    veroeffentlichungsdatum: datetime | None
    angebotsfrist: datetime | None
    fragenfrist: datetime | None
    verfahrensart: str | None
    cpv_codes: list[str]
    geschaetzter_wert: float | None
    direktlink: str
    status: str
    zugangsart: str
    ki_relevanz_score: str | None
    ki_relevanz_begruendung: str | None
    kategorien: list[str]
    gesamtscore: float
    moeglicherweise_duplikat_hinweis: str | None
    gemerkt: bool
    merk_notiz: str | None
    erfasst_am: datetime
    zuletzt_geprueft_am: datetime


class RankingBreakdown(BaseModel):
    ki_relevanz: float
    dringlichkeit: float
    profil_uebereinstimmung: float
    aktualitaet: float


class DokumentOut(BaseModel):
    titel: str | None
    url: str


class TenderDetailOut(TenderOut):
    volltext: str | None
    dokumente: list[DokumentOut]
    ranking_aufschluesselung: RankingBreakdown


class TenderListOut(BaseModel):
    items: list[TenderOut]
    total: int
    page: int
    page_size: int


class HistoryEntryOut(BaseModel):
    feld: str
    alter_wert: str | None
    neuer_wert: str | None
    erkannt_am: datetime


class PortalHealthOut(BaseModel):
    id: str
    name: str
    betreiber: str | None
    base_url: str
    aktiv: bool
    robots_status: str
    tos_hinweis: str | None
    status_ampel: str
    letzter_erfolgreicher_lauf: datetime | None
    letzte_trefferzahl: int | None
    fehlerrate_gleitend: float | None
    meldung: str | None


class SearchProfileIn(BaseModel):
    name: str
    portale: list[str] = []
    keywords: list[str] = []
    filter_json: dict = {}
    aktiv: bool = True


class SearchProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    portale: list[str]
    keywords: list[str]
    filter_json: dict
    aktiv: bool
    erstellt_am: datetime
    neue_treffer_anzahl: int = 0


class EscalationOut(BaseModel):
    id: str
    job_id: str | None
    portal_id: str | None
    kategorie: str
    kontext: str
    optionen: list[str]
    empfehlung: str | None
    status: str
    entscheidung: str | None
    erstellt_am: datetime
    beantwortet_am: datetime | None


class EscalationResolveIn(BaseModel):
    entscheidung: str


class RunTriggerOut(BaseModel):
    started: bool
    ergebnis: dict | None = None


class RunAllPortalResultOut(BaseModel):
    portal_id: str
    portal_name: str
    status_ampel: str | None = None
    treffer_anzahl: int | None = None
    fehler: str | None = None


class RunAllStatusOut(BaseModel):
    laeuft: bool
    gestartet_am: datetime | None
    beendet_am: datetime | None
    aktuelle_portale: list[str]
    ergebnisse: list[RunAllPortalResultOut]


class AssistantMessageIn(BaseModel):
    rolle: str  # user | assistant
    text: str


class AssistantChatIn(BaseModel):
    nachricht: str
    verlauf: list[AssistantMessageIn] = []


class AssistantActionProposalOut(BaseModel):
    name: str
    input: dict
    beschreibung: str


class AssistantChatOut(BaseModel):
    antwort: str
    verfuegbar: bool
    tenders: list[TenderOut]
    vorschlag: AssistantActionProposalOut | None = None


class AssistantActionIn(BaseModel):
    name: str
    input: dict = {}


class AssistantActionOut(BaseModel):
    erfolg: bool
    meldung: str
