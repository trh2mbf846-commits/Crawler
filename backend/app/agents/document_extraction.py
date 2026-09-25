"""PDF-Vergabeunterlagen auswerten statt nur verlinken.

Nutzerrecherche 25.09.2026 ("was können gute Agenten fürs Crawling/Durchsuchen noch"): laut
vergleichbaren Tender-Monitoring-Systemen ist das Auswerten der angehängten Dokumente (statt nur
den Link zu speichern) einer der konkretesten Mehrwerte - Details wie genaue Anforderungen stehen
oft nur im PDF, nicht in der HTML-Kurzbeschreibung.

Bewusst nur reine Text-Extraktion (kein LLM nötig, funktioniert also auch ohne
ANTHROPIC_API_KEY) - Crawler Kevin bekommt darüber ein neues Werkzeug (`dokumente_lesen`,
app/agents/assistant.py), um auf Nachfrage Auszüge aus den Anhängen zu lesen und zusammenzufassen.

Bewusst konservativ: nur PDF (der weit überwiegende Vergabeunterlagen-Dateityp), begrenzte
Downloadgröße/-zeit/-anzahl. Ein fehlgeschlagener Download/Parse darf niemals den
Duplicate-Agenten (und damit die ganze Ausschreibung) zum Scheitern bringen - siehe
app/agents/duplicate.py, wo das best-effort aufgerufen wird.
"""
from __future__ import annotations

import logging
import warnings
from io import BytesIO

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadWarning

logger = logging.getLogger("ausschreibungscrawler.document_extraction")

# pypdf warnt bei jedem PDF ohne eingebettete fontTools-kompatible Font-Metadaten (z. B. fehlende
# CFF-Font-Parsing-Unterstützung) - live verifiziert 25.09.2026: harmlos, die Textextraktion
# funktioniert trotzdem einwandfrei, die Warnung würde nur bei jedem Vergabeunterlagen-PDF unnötig
# das Log fluten. pypdf sendet diese konkrete Meldung nicht über `warnings.warn`, sondern über eine
# eigene `logger_warning`-Hilfsfunktion (siehe pypdf/_utils.py), die intern `logging.getLogger(...)`
# nutzt - `warnings.filterwarnings` allein wirkt darauf nicht, deshalb zusätzlich der Logger-Level.
warnings.filterwarnings("ignore", category=PdfReadWarning)
warnings.filterwarnings("ignore", message=".*fontTools is required.*")
logging.getLogger("pypdf").setLevel(logging.ERROR)

_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB - genug für die meisten Vergabeunterlagen-PDFs
_MAX_SEITEN = 40  # Deckelt Rechenzeit bei sehr langen Dokumenten
_MAX_TEXT_ZEICHEN = 20000  # Deckelt Speicher-/Prompt-Größe
_TIMEOUT_SEKUNDEN = 15.0
MAX_DOKUMENTE_PRO_AUSSCHREIBUNG = 3  # begrenzt Laufzeit eines Aktualisieren-Laufs


def extract_pdf_text(url: str) -> str | None:
    """Lädt eine URL herunter und extrahiert Text, falls es sich um ein PDF handelt.

    Liefert None bei jedem Fehlschlag (kein PDF, Downloadfehler, zu groß, Parse-Fehler) - reine
    Bereicherung, niemals ein harter Fehler für die aufrufende Stelle.
    """
    try:
        with httpx.Client(timeout=_TIMEOUT_SEKUNDEN, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    return None
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and not url.lower().split("?")[0].endswith(".pdf"):
                    return None
                inhalt = bytearray()
                for chunk in response.iter_bytes():
                    inhalt.extend(chunk)
                    if len(inhalt) > _MAX_DOWNLOAD_BYTES:
                        logger.info("Dokument zu groß, übersprungen (%s)", url)
                        return None
    except httpx.HTTPError as exc:
        logger.info("Dokument-Download fehlgeschlagen (%s): %s", url, exc)
        return None

    try:
        reader = PdfReader(BytesIO(bytes(inhalt)))
        text = "\n".join((seite.extract_text() or "") for seite in reader.pages[:_MAX_SEITEN]).strip()
    except Exception as exc:  # pypdf wirft diverse, teils undokumentierte Fehlerklassen bei kaputten PDFs
        logger.info("PDF-Parsing fehlgeschlagen (%s): %s", url, exc)
        return None

    return text[:_MAX_TEXT_ZEICHEN] or None
