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
    frist_quelle: str | None = None  # None = vom Portal; "seite"/"ki" = nachträglich ermittelt
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


class BewertungOut(BaseModel):
    empfehlung: str  # bewerben | pruefen | nicht_bewerben
    passwert: int  # 0-100
    zusammenfassung: str
    begruendung: str
    ausschlusskriterien: list[str] = []
    pflichtnachweise: list[str] = []
    zuschlagskriterien: list[str] = []
    fristen: list[str] = []
    fehlende_nachweise: list[str] = []
    risiken: list[str] = []
    naechste_schritte: list[str] = []
    passende_referenzen: list[str] = []
    entfernt_ohne_beleg: int = 0  # Punkte, die der Prüfer nicht im Quelltext fand und verworfen hat
    quellen: list[str] = []  # woraus bewertet wurde (Unterlagen, Verfahrensseite, Bekanntmachung)
    modell: str
    firmenprofil_fehlte: bool = False
    bewertet_am: datetime | None = None


class TenderDetailOut(TenderOut):
    volltext: str | None
    dokumente: list[DokumentOut]
    ranking_aufschluesselung: RankingBreakdown
    bewertung: BewertungOut | None = None
    checkliste: list[ChecklistenPunkt] = []


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
    qualitaet: dict | None = None  # {"anzahl": n, "quoten": {feld: 0..1}} des letzten Laufs


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
    automatisch_um: str | None = None  # tägliche automatische Aktualisierung (HH:MM) oder None


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


class AssistantPreferencesIn(BaseModel):
    prioritaeten_text: str | None = None
    firmenprofil: str | None = None
    bevorzugte_kategorien: list[str] = []
    bevorzugte_regionen: list[str] = []
    mindestwert: float | None = None


class AssistantPreferencesOut(AssistantPreferencesIn):
    aktualisiert_am: datetime


class AssistantDigestOut(BaseModel):
    text: str
    neue_relevante_anzahl: int
    bald_ablaufend_anzahl: int
    portale_mit_problem: list[str]
    tenders: list[TenderOut]


class WunschOut(BaseModel):
    id: str
    titel: str
    beschreibung: str
    status: str
    erstellt_am: datetime


class WunschStatusIn(BaseModel):
    status: str  # offen | erledigt


class ChecklistenPunkt(BaseModel):
    id: str
    text: str
    art: str = "eigen"  # nachweis | ausschluss | frist | eigen
    status: str = "offen"  # offen | vorhanden | fehlt | erledigt


class ReferenzIn(BaseModel):
    titel: str
    auftraggeber: str | None = None
    jahr: int | None = None
    volumen: float | None = None
    beschreibung: str | None = None


class ReferenzOut(ReferenzIn):
    id: str
    erstellt_am: datetime


class FristOut(BaseModel):
    tender_id: str
    titel: str
    vergabestelle: str | None
    art: str  # Angebotsfrist | Fragenfrist
    datum: datetime
    grund: str  # warum im Kalender: gemerkt / bewertet / Checkliste
    direktlink: str
