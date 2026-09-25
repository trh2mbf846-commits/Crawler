"""Auswahl des Direktlinks zu einem konkreten Vergabeverfahren (Nutzeranfrage 25.09.2026).

Befund: Viele Treffer verlinkten nur auf die Homepage der Vergabestelle, auf eine allgemeine
Suchseite oder direkt auf ein PDF zum Download. Gewünscht ist die Verfahrensseite auf der
Vergabeplattform, auf der man sich über genau diese Ausschreibung informieren und sich bewerben
kann.

Die eForms-Bekanntmachungen (Bekanntmachungsservice und TED) enthalten dafür zwei Felder:
- BT-18 "Submission URL" (TenderRecipientParty/EndpointID): Adresse für die Angebotsabgabe, bei
  DTVP/Vergabemarktplätzen z. B. die Verfahrensübersicht `.../notice/CX...`, bei anderen
  Plattformen oft nur deren Startseite.
- BT-15 "Documents URL" (CallForTendersDocumentReference/.../URI): Seite mit den
  Vergabeunterlagen, meist verfahrensspezifisch, gelegentlich aber ein direkter PDF-Download.

Live-Auswertung eines Tages-Exports (733 offene Ausschreibungen): einer der beiden Links ist in
93 % der Fälle eine verfahrensspezifische Seite; der Rest sind fast ausschließlich
subreport-ELViS-PDFs, deren Verfahrens-ID sich auf die offizielle Kurz-URL
`https://www.subreport.de/E<ID>` abbilden lässt (leitet live auf die Verfahrensseite weiter).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_DATEI_ENDUNG = re.compile(r"\.(pdf|zip|docx?|xlsx?|rtf|odt|ods|txt|xml)$", re.IGNORECASE)
_DOWNLOAD_PFAD = re.compile(r"/(download|downloads)/", re.IGNORECASE)
_SUBREPORT_ID = re.compile(r"subreport(?:-elvis)?\.de/.*?\b(E\d{6,})\b", re.IGNORECASE)
# Verfahrens-IDs der Plattformen: CXP4YLPMVFX (DTVP/Vergabemarktplätze), 890720 (evergabe-online),
# E93246569 (subreport), UUIDs, 54321-Tender-19f... (NetServer): ein Token mit Ziffer und
# mindestens 5 Zeichen, oder (DTVP-IDs wie CXVHYDPYTWTKMJPL haben oft gar keine Ziffer) mindestens
# 8 Großbuchstaben/Ziffern am Stück. Allgemeine Einstiegsseiten (".../NetServer/",
# ".../ParticipationControllerServlet") haben keins.
_VERFAHRENS_ID = re.compile(r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{5,}|\b[A-Z0-9]{8,}\b")


def ist_dateidownload(url: str) -> bool:
    pfad = urlparse(url).path
    return bool(_DATEI_ENDUNG.search(pfad) or _DOWNLOAD_PFAD.search(pfad))


def ist_verfahrensspezifisch(url: str) -> bool:
    """Echte http(s)-Adresse, die eine Verfahrens-ID enthält (nicht bloß Start-/Einstiegsseite)
    und kein Datei-Download ist."""
    teile = urlparse(url)
    if teile.scheme not in ("http", "https") or not teile.netloc:
        return False
    if ist_dateidownload(url):
        return False
    return bool(_VERFAHRENS_ID.search(f"{teile.path}?{teile.query}"))


def _umgeschrieben(url: str) -> str | None:
    """Bekannte Download-Links auf die zugehörige Verfahrensseite abbilden."""
    treffer = _SUBREPORT_ID.search(url)
    if treffer:
        return f"https://www.subreport.de/{treffer.group(1)}"
    return None


def waehle_verfahrenslink(*kandidaten_gruppen: list[str] | None) -> str | None:
    """Erster verfahrensspezifischer Link aus den Gruppen in Prioritätsreihenfolge.

    Aufruf z. B. `waehle_verfahrenslink(abgabe_urls, unterlagen_urls)`. Findet sich keiner, werden
    Download-Links bekannter Plattformen auf ihre Verfahrensseite umgeschrieben. Liefert None, wenn
    es keine Seite zu genau diesem Verfahren gibt - der Aufrufer entscheidet dann (auslassen oder
    eine eigene Detailseite wie die TED-Bekanntmachung verwenden).
    """
    alle = [u.strip() for gruppe in kandidaten_gruppen for u in (gruppe or []) if u and u.strip()]
    for url in alle:
        if ist_verfahrensspezifisch(url):
            return url
    for url in alle:
        umgeschrieben = _umgeschrieben(url)
        if umgeschrieben:
            return umgeschrieben
    return None
