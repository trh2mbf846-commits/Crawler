"""AI-Classification-Agent (Kapitel 18): Keyword-/CPV-Filterung (Kapitel 4.1/4.2, immer aktiv)

plus optionale LLM-Nachbewertung von Grenzfällen (Kapitel 4.3/8.3/25.1). Vergibt außerdem
Kategorie-Tags (Kapitel 7/25.4). LLM-Einstufungen werden klar als solche gekennzeichnet
(ki_relevanz_quelle="llm") und nie mit einer manuell geprüften Einstufung verwechselt (Kapitel 24).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.agents import ranking, search
from app.keywords import find_cpv_hits, find_keyword_hits
from app.models import Category, Job, Tender, TenderCategory

CATEGORY_ORDER = [
    "KI & Machine Learning",
    "Softwareentwicklung & IT-Dienstleistungen",
    "Cloud & Infrastruktur",
    "Daten & Analytics",
    "Beratung & Strategie",
    "Planung & Technische Beratung",
    "Bauüberwachung & Bauleitung",
    "Prozessautomatisierung",
    "Cybersecurity",
    "Sonstige IT",
    "Nicht-IT",
]

_CLOUD_HINTS = ["cloud", "infrastruktur", "hosting", "rechenzentrum", "kubernetes"]
_SECURITY_HINTS = ["cybersecurity", "informationssicherheit", "it-sicherheit", "penetrationstest", "security"]
_BERATUNG_HINTS = [
    "beratung", "strategie", "consulting", "change management", "business development",
    "projektmanagement", "service-management", "prozessberatung",
]
_DATEN_HINTS = ["daten", "analytics", "business intelligence", "reporting"]
_IT_HINTS = ["software", "it-", "informationstechnik", "digitalisierung", "system"]

# Kapitel 4.1-Analog für Nicht-KI-Geschäftsfelder (Nutzeranfrage 01.09.2026, abgeleitet aus
# double-skill.com): erweitert die Taxonomie über reine IT-Themen hinaus, damit Ausschreibungen
# aus Planung/Bauüberwachung/Beratung ebenfalls sinnvoll kategorisiert werden, statt in
# "Sonstige IT"/"Nicht-IT" zu landen. Kurze Akronyme (ava, vob, bim) bewusst mit
# Leerzeichen-Wortgrenzen gepolstert, siehe keywords.py-Dokumentation zum selben Bug-Muster.
_PLANUNG_HINTS = [
    "technische planung", "konzeption und planung", "technisches projektmanagement",
    "itk-infrastruktur", "ingenieurleistungen", " bim ", "building information modeling",
    "technologieberatung", "machbarkeitsstudie", "planungsleistungen", "technology engineering",
]
_BAUUEBERWACHUNG_HINTS = [
    "bauüberwachung", "baueberwachung", "bauleitung", "bauleiter", "projektsteuerung",
    "baukostenmanagement", " ava ", " vob ", "leistungsverzeichnis", "objektüberwachung",
    "objektueberwachung", "bauherrenvertretung",
]


def run_classification(db: Session, job: Job) -> dict:
    tender = db.get(Tender, job.payload["tender_id"])
    if tender is None:
        return {"uebersprungen": "tender nicht mehr vorhanden"}

    text_basis = f"{tender.titel} {tender.kurzbeschreibung or ''}"
    keyword_hits = find_keyword_hits(tender.titel, tender.kurzbeschreibung, tender.volltext)
    cpv_hits = find_cpv_hits(tender.cpv_codes)

    if cpv_hits or len(keyword_hits) >= 2:
        einstufung, konfidenz = "stark", 0.8
    elif keyword_hits:
        einstufung, konfidenz = "moeglich", 0.5
    else:
        einstufung, konfidenz = "nicht", 0.3

    quelle = "cpv" if cpv_hits else ("keyword" if keyword_hits else "keyword")
    begruendung = (
        f"Treffer: {', '.join(keyword_hits or cpv_hits) or 'keine Keyword-/CPV-Treffer'} "
        f"(regelbasierte Einschätzung, Kapitel 4.1/4.2)."
    )

    # Kapitel 4.3/8.3: LLM-gestützte Nachbewertung nur für den echten Grenzfall ("moeglich"),
    # nie als Ersatz für die nachvollziehbare Keyword-/CPV-Basis.
    if einstufung == "moeglich":
        llm_result = prompts.call_llm_json(
            prompts.KI_RELEVANZ_SYSTEM,
            prompts.ki_relevanz_user(tender.titel, tender.kurzbeschreibung, tender.vergabestelle),
        )
        if llm_result and llm_result.get("einstufung") in ("stark_relevant", "moeglich_relevant", "nicht_relevant"):
            einstufung = llm_result["einstufung"].replace("_relevant", "")
            konfidenz = float(llm_result.get("konfidenz", konfidenz))
            begruendung = f"[KI-Einschätzung, keine gesicherte Tatsache] {llm_result.get('begruendung', '')}"
            quelle = "llm"

    tender.ki_relevanz_score = einstufung
    tender.ki_relevanz_konfidenz = konfidenz
    tender.ki_relevanz_begruendung = begruendung
    tender.ki_relevanz_quelle = quelle

    kategorien = _kategorisieren(text_basis, keyword_hits, cpv_hits)
    if not kategorien:
        llm_kat = prompts.call_llm_json(
            prompts.KATEGORISIERUNG_SYSTEM,
            prompts.kategorisierung_user(tender.titel, tender.kurzbeschreibung),
        )
        if llm_kat and llm_kat.get("kategorien"):
            kategorien = [k for k in llm_kat["kategorien"] if k in CATEGORY_ORDER] or ["Sonstige IT"]
        else:
            kategorien = ["Nicht-IT"]

    _set_categories(db, tender, kategorien)
    db.commit()

    ranking.compute_and_store(db, tender)
    search.match_tender_to_profiles(db, tender)

    return {"ki_relevanz_score": einstufung, "kategorien": kategorien}


def _kategorisieren(text_basis: str, keyword_hits: list[str], cpv_hits: list[str]) -> list[str]:
    # Führendes/folgendes Leerzeichen, damit auch mit Leerzeichen gepolsterte Hints (" bim ",
    # " ava ", " vob ") am Anfang/Ende des Texts korrekt matchen (gleiches Muster wie in
    # keywords.find_keyword_hits, siehe dortige Dokumentation zum zugehörigen Bug).
    text = f" {text_basis.lower()} "
    kategorien: list[str] = []
    if keyword_hits:
        kategorien.append("KI & Machine Learning")
    if any(h in text for h in _CLOUD_HINTS):
        kategorien.append("Cloud & Infrastruktur")
    if any(h in text for h in _SECURITY_HINTS):
        kategorien.append("Cybersecurity")
    if any(h in text for h in _DATEN_HINTS):
        kategorien.append("Daten & Analytics")
    if any(h in text for h in _BERATUNG_HINTS):
        kategorien.append("Beratung & Strategie")
    if any(h in text for h in _PLANUNG_HINTS):
        kategorien.append("Planung & Technische Beratung")
    if any(h in text for h in _BAUUEBERWACHUNG_HINTS):
        kategorien.append("Bauüberwachung & Bauleitung")
    if cpv_hits or any(h in text for h in _IT_HINTS):
        if "KI & Machine Learning" not in kategorien:
            kategorien.append("Softwareentwicklung & IT-Dienstleistungen")
    return kategorien


def _set_categories(db: Session, tender: Tender, names: list[str]) -> None:
    db.execute(TenderCategory.__table__.delete().where(TenderCategory.tender_id == tender.id))
    for name in names:
        category = db.scalars(select(Category).where(Category.name == name)).first()
        if category is None:
            category = Category(name=name)
            db.add(category)
            db.flush()
        db.add(TenderCategory(tender_id=tender.id, category_id=category.id))
