"""Go/No-Go-Bewertung einer Ausschreibung (Nutzeranfrage 25.09.2026, angelehnt an professionelle
Ausschreibungstools: "Bewerben / Prüfen / Nicht bewerben" mit Passwert 0-100, dazu aus den
Unterlagen extrahierte Ausschlusskriterien, Pflichtnachweise, Zuschlagskriterien und Fristen).

Textgrundlage, in dieser Reihenfolge und zusammen gekürzt auf ein für lokale Modelle
verarbeitbares Maß:
1. extrahierter Volltext der Vergabeunterlagen (PDF, agents/document_extraction.py), falls vorhanden;
2. sonst der sichtbare Text der verlinkten Verfahrensseite (ein einzelner, höflicher Abruf);
3. immer: Titel, Beschreibung, Vergabestelle, Frist, Wert aus der Bekanntmachung.
Verglichen wird mit dem Firmenprofil und den Prioritäten aus Kevins Präferenzen. Das Ergebnis ist
eine KI-Einschätzung (so gekennzeichnet) und wird an der Ausschreibung gespeichert.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.bewerbung import checkliste_aus_bewertung
from app.config import settings
from app.models import AssistantPreferences, Referenz, Tender

logger = logging.getLogger("ausschreibungscrawler.bewertung")

MAX_UNTERLAGEN_ZEICHEN = 9000
MAX_SEITEN_ZEICHEN = 6000
# Lokale Modelle: kürzere Eingabe (ein Test mit 8B-Modell auf einem Rechner ohne Grafikchip lief mit
# ~10.000 Zeichen in die Zeitgrenze); auf einem Mac mit M-Chip ist das ohnehin um ein Vielfaches schneller.
MAX_GESAMT_ZEICHEN_LOKAL = 6000
_EMPFEHLUNGEN = ("bewerben", "pruefen", "nicht_bewerben")
_LISTEN = (
    "ausschlusskriterien", "pflichtnachweise", "zuschlagskriterien", "fristen",
    "fehlende_nachweise", "risiken", "naechste_schritte",
)
# Diese Listen geben angeblich Inhalte der Ausschreibung wieder - der Prüfer-Schritt verwirft
# Punkte, die sich im Quelltext nicht wiederfinden (gegen erfundene Kriterien kleiner Modelle).
_ZU_BELEGEN = ("ausschlusskriterien", "pflichtnachweise", "zuschlagskriterien", "fristen")
_WORT = re.compile(r"[a-zäöüß0-9]{4,}")


def _verfahrensseite_text(url: str | None) -> str | None:
    if not url:
        return None
    try:
        antwort = httpx.get(
            url, follow_redirects=True, timeout=20,
            headers={"User-Agent": settings.http_user_agent},
        )
        if antwort.status_code >= 400 or "html" not in antwort.headers.get("content-type", ""):
            return None
        soup = BeautifulSoup(antwort.text, "lxml")
        for element in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            element.decompose()
        text = " ".join(soup.get_text(" ").split())
        return text[:MAX_SEITEN_ZEICHEN] if len(text) > 200 else None
    except Exception as exc:  # Seite nicht erreichbar - Bewertung geht mit der Bekanntmachung weiter
        logger.info("Verfahrensseite für Bewertung nicht lesbar (%s): %s", url, exc)
        return None


def _profil_text(praeferenzen: AssistantPreferences | None) -> tuple[str, bool]:
    if praeferenzen is None:
        return "(kein Firmenprofil hinterlegt)", True
    teile = []
    if praeferenzen.firmenprofil:
        teile.append(f"Firmenprofil: {praeferenzen.firmenprofil}")
    if praeferenzen.prioritaeten_text:
        teile.append(f"Prioritäten: {praeferenzen.prioritaeten_text}")
    if praeferenzen.bevorzugte_regionen:
        teile.append(f"Bevorzugte Regionen: {', '.join(praeferenzen.bevorzugte_regionen)}")
    if praeferenzen.mindestwert is not None:
        teile.append(f"Mindestauftragswert: {praeferenzen.mindestwert:,.0f} €")
    return ("\n".join(teile) or "(kein Firmenprofil hinterlegt)"), not praeferenzen.firmenprofil


def _referenzen_text(db: Session) -> tuple[str, list[str]]:
    referenzen = list(db.scalars(select(Referenz).order_by(Referenz.jahr.desc().nulls_last()).limit(15)))
    if not referenzen:
        return "(keine Referenzprojekte hinterlegt)", []
    zeilen = [
        f"- {r.titel} ({', '.join(str(x) for x in (r.auftraggeber, r.jahr) if x)})"
        + (f": {r.beschreibung[:200]}" if r.beschreibung else "")
        for r in referenzen
    ]
    return "\n".join(zeilen), [r.titel for r in referenzen]


def ist_belegt(punkt: str, quelltext: str) -> bool:
    """Prüfer: stehen die tragenden Wörter eines Punkts (mind. die Hälfte, mind. eins) im Quelltext?"""
    woerter = set(_WORT.findall(punkt.lower()))
    if not woerter:
        return True
    text = quelltext.lower()
    treffer = sum(1 for w in woerter if w in text or w[:-1] in text)  # einfache Endungs-Toleranz
    return treffer >= max(1, (len(woerter) + 1) // 2)


def _textgrundlage(tender: Tender) -> tuple[str, list[str]]:
    quellen = ["Bekanntmachung"]
    teile = [
        f"Titel: {tender.titel}",
        f"Vergabestelle: {tender.vergabestelle or '-'}",
        f"Ort: {tender.ort_region or '-'}",
        f"Angebotsfrist: {tender.angebotsfrist.isoformat() if tender.angebotsfrist else 'unbekannt'}",
        f"Verfahrensart: {tender.verfahrensart or '-'}",
        f"Geschätzter Wert: {f'{tender.geschaetzter_wert:,.0f} €' if tender.geschaetzter_wert else 'unbekannt'}",
        f"Beschreibung: {(tender.volltext or tender.kurzbeschreibung or '')[:2500]}",
    ]
    unterlagen = "\n\n".join(d.volltext for d in tender.dokumente if d.volltext)[:MAX_UNTERLAGEN_ZEICHEN]
    if unterlagen:
        quellen.append("Vergabeunterlagen (PDF)")
        teile.append(f"Auszug aus den Vergabeunterlagen:\n{unterlagen}")
    else:
        seite = _verfahrensseite_text(tender.direktlink)
        if seite:
            quellen.append("Verfahrensseite")
            teile.append(f"Text der Verfahrensseite:\n{seite}")
    return "\n".join(teile), quellen


def _liste(wert) -> list[str]:
    if isinstance(wert, str):
        wert = [wert] if wert.strip() else []
    if not isinstance(wert, list):
        return []
    return [str(e).strip() for e in wert if str(e).strip()][:6]


def bewerte(db: Session, tender: Tender) -> dict | None:
    """Bewertet und speichert. None = kein Sprachmodell erreichbar oder unbrauchbare Antwort."""
    grundlage, quellen = _textgrundlage(tender)
    if prompts.llm_anbieter() == "ollama":
        grundlage = grundlage[:MAX_GESAMT_ZEICHEN_LOKAL]
    profil, profil_fehlt = _profil_text(db.get(AssistantPreferences, "singleton"))
    referenzen, referenz_titel = _referenzen_text(db)
    ergebnis = prompts.call_llm_json(
        prompts.GO_NOGO_SYSTEM,
        f"UNTERNEHMEN\n{profil}\n\nREFERENZPROJEKTE\n{referenzen}\n\nAUSSCHREIBUNG\n{grundlage}",
        lokal_erlaubt=True,
    )
    if not ergebnis or ergebnis.get("empfehlung") not in _EMPFEHLUNGEN:
        return None
    try:
        passwert = max(0, min(100, int(float(ergebnis.get("passwert", 0)))))
    except (TypeError, ValueError):
        passwert = 0
    listen = {feld: _liste(ergebnis.get(feld)) for feld in _LISTEN}
    entfernt = 0
    for feld in _ZU_BELEGEN:
        belegt = [p for p in listen[feld] if ist_belegt(p, grundlage)]
        entfernt += len(listen[feld]) - len(belegt)
        listen[feld] = belegt
    passende = [r for r in _liste(ergebnis.get("passende_referenzen")) if r in referenz_titel]
    bewertung = {
        "empfehlung": ergebnis["empfehlung"],
        "passwert": passwert,
        "zusammenfassung": str(ergebnis.get("zusammenfassung") or "").strip(),
        "begruendung": str(ergebnis.get("begruendung") or "").strip(),
        **listen,
        "passende_referenzen": passende,
        "entfernt_ohne_beleg": entfernt,
        "quellen": quellen,
        "modell": prompts.llm_bezeichnung(),
        "firmenprofil_fehlte": profil_fehlt,
    }
    tender.bewertung_json = bewertung
    tender.bewertet_am = datetime.utcnow()
    checkliste_aus_bewertung(tender)
    db.commit()
    return bewertung
