from app.agents.connector.base import BaseConnector
from app.agents.connector.db_bieterportal import DbBieterportalConnector
from app.agents.connector.dtvp import DtvpConnector
from app.agents.connector.evergabe_bund import EvergabeBundConnector
from app.agents.connector.itdz_berlin import ItdzBerlinConnector
from app.agents.connector.oeffentlichevergabe import OeffentlicheVergabeConnector
from app.agents.connector.pending import make_pending_connector
from app.agents.connector.ted import TedConnector
from app.agents.connector.vergabe_bayern import VergabeBayernConnector
from app.agents.connector.vergabekooperation_berlin import VergabekooperationBerlinConnector

CONNECTORS: dict[str, type[BaseConnector]] = {
    ItdzBerlinConnector.slug: ItdzBerlinConnector,
    DbBieterportalConnector.slug: DbBieterportalConnector,
    VergabekooperationBerlinConnector.slug: VergabekooperationBerlinConnector,
}

# Von Claude Code als sinnvolle Ergänzung identifizierte bzw. vom Nutzer (01.09.2026) explizit
# angeforderte Zusatzportale (Kapitel 3/16.3 der Handlungsanweisung + Nutzeranfrage). Als Quelle
# bereits sichtbar (Quellstatus-Dashboard zeigt "in Vorbereitung"), Connector-Logik folgt
# schrittweise nach echter Portalanalyse (siehe docs/portal-notes.md).
ZUSATZPORTALE: list[dict] = [
    dict(
        slug="ted",
        robots_status="geprueft_ok",
        name="TED – Tenders Electronic Daily",
        base_url="https://api.ted.europa.eu/v3/notices/search",
        betreiber="Amt für Veröffentlichungen der Europäischen Union",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 04.09.2026: ted.europa.eu selbst läuft hinter AWS-WAF-Bot-Challenge, aber die "
            "offizielle REST Search API unter api.ted.europa.eu ist ohne Key/Login frei nutzbar - "
            "kein HTML-Scraping nötig. Connector implementiert."
        ),
    ),
    dict(
        slug="dtvp",
        robots_status="geprueft_ok",
        name="DTVP – Deutsches Vergabeportal",
        base_url="https://dtvp.de/ausschreibungen/",
        betreiber="cosinex GmbH im Auftrag zahlreicher öffentlicher Vergabestellen",
        intervall_minuten=180,
        hinweis=(
            "Geprüft 04.09.2026: robots.txt (Standard-WordPress) erlaubt automatisierten Zugriff auf "
            "die öffentliche Sektion /ausschreibungen/ (kein Login, CPV-Kategorie-Filterung per URL, "
            "Detailseiten vollständig öffentlich). Die ältere Center/...search.do-Anwendung ist NICHT "
            "einfach automatisierbar (JWT-CSRF-Token) und wird bewusst nicht verwendet. Connector "
            "implementiert."
        ),
    ),
    dict(
        slug="evergabe-bund",
        robots_status="geprueft_ok",
        name="e-Vergabe des Bundes",
        base_url="https://www.evergabe-online.de/",
        betreiber="Beschaffungsamt des Bundesministeriums des Innern (BMI)",
        intervall_minuten=180,
        hinweis=(
            "Geprüft 04.09.2026: robots.txt erlaubt /search.html und /tenderdetails.html; nur wenige "
            "Pfade gesperrt (u. a. /ws-suche/, wird respektiert). Suche funktioniert ohne Login (nur "
            "Cookie-Consent). Serverseitige Volltextfilterung per URL funktioniert nicht - lokal "
            "nachfiltern. Connector implementiert."
        ),
    ),
    dict(
        slug="vergabe24",
        robots_status="ungeprueft",
        name="Vergabe24",
        base_url="https://www.vergabe24.de/",
        betreiber="Bundesanzeiger Verlag",
        intervall_minuten=180,
        hinweis=(
            "Geprüft 04.09.2026: kein öffentlicher Such-/Listing-Bereich auffindbar - Startseite "
            "verweist nur auf Tarife und ein separates Login-System (login.vergabe24.de). Starke "
            "Indizien für Login-/Abo-Pflicht bereits für die Suche. Nicht weiterverfolgt (Kapitel 9.2), "
            "vor Umsetzung mit Vincent abstimmen."
        ),
    ),
    dict(
        slug="vergabemarktplatz-brandenburg",
        robots_status="geprueft_einschraenkung",
        name="Vergabemarktplatz Brandenburg",
        base_url="https://vergabemarktplatz.brandenburg.de/",
        betreiber="Land Brandenburg (cosinex-Whitelabel-Instanz)",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 04.09.2026: robots.txt sperrt explizit ALLE Bots vollständig "
            "(\"User-agent: * / Disallow: /\"). Automatisierter Zugriff daher nicht zulässig - "
            "bewusst nicht implementiert (Kapitel 9.2/9.3)."
        ),
    ),
    dict(
        slug="subreport-elvis",
        robots_status="geprueft_einschraenkung",
        name="subreport ELViS",
        base_url="https://www.subreport.de/ausschreibungen/subreport-classic/",
        betreiber="subreport Verlag Schawe GmbH",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 04.09.2026: subreport.de bietet laut eigener Aussage kostenlose Trefferlisten-"
            "Recherche, verlangt aber Pay-per-View (ca. 6 €/Ausschreibung) für die vollständige "
            "Bekanntmachung. ELViS selbst (subreport-elvis.de) ist reine Abwicklungssoftware hinter "
            "Login, keine eigene Suche. Vor Umsetzung mit Vincent abstimmen (kostenpflichtiger Umfang)."
        ),
    ),
    dict(
        slug="cosinex-vergabemarktplaetze",
        robots_status="ungeprueft",
        name="cosinex Vergabemarktplätze",
        base_url="https://www.cosinex.de/produkte/vergabemarktplatz/",
        betreiber="cosinex GmbH",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 04.09.2026: cosinex ist reiner Software-Anbieter für White-Label-"
            "Vergabeplattformen (u. a. DTVP, Vergabemarktplatz Brandenburg) - keine zentrale eigene "
            "Ausschreibungssuche. Jede Kunden-Instanz müsste einzeln mit eigener robots.txt-Prüfung "
            "ergänzt werden."
        ),
    ),
    dict(
        slug="deutsche-evergabe",
        robots_status="geprueft_einschraenkung",
        name="Deutsche eVergabe",
        base_url="https://portal.deutsche-evergabe.de/",
        betreiber="Deutsche eVergabe (privater Anbieter, eigenständig - nicht zu verwechseln mit e-Vergabe des Bundes)",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 04.09.2026: eigenständiges Portal (Verwechslungsgefahr mit evergabe-online.de). "
            "Laut Portal ist \"Recherche\" ausdrücklich Teil des registrierungspflichtigen Bereichs - "
            "keine Möglichkeit gefunden, ohne (kostenlose) Registrierung zu suchen. Nicht umgangen "
            "(Kapitel 9.2); vor Umsetzung klären, ob eine kostenlose Registrierung vertretbar ist."
        ),
    ),
    dict(
        slug="oeffentlichevergabe",
        robots_status="geprueft_ok",
        name="Bekanntmachungsservice (Bund/Länder/Kommunen)",
        base_url="https://www.oeffentlichevergabe.de/api/notice-exports",
        betreiber="Beschaffungsamt des Bundesministeriums des Innern (BMI) - Datenservice Öffentlicher Einkauf",
        intervall_minuten=720,
        hinweis=(
            "Geprüft 05.09.2026: offizielle OpenData-REST-API (kein Scraping, kein Login), liefert "
            "täglich alle Bekanntmachungen aus Bund/Ländern/Kommunen (seit 25.09.2026 im vollständigen "
            "eForms-Format: nur offene Ausschreibungen, Direktlink zur Verfahrensseite, Angebotsfrist). "
            "Deckt auch Vergabestellen ab, die intern Brandenburg/Deutsche eVergabe nutzen; "
            "Überschneidungen mit TED/DTVP erkennt die portalübergreifende Duplikaterkennung. "
            "Connector implementiert."
        ),
    ),
    dict(
        slug="vergabe-bayern",
        robots_status="geprueft_ok",
        name="RIB/iTWO-Vergabeplattform (Bayern + weitere Bundesländer)",
        base_url="https://www.vergabe.bayern.de/veroeffentlichungen/auftragsbekanntmachungen/index.html",
        betreiber="RIB Software (iTWO tender) - Vergabestellen aus Bayern (vergabe.bayern.de) und weiteren Ländern",
        intervall_minuten=360,
        hinweis=(
            "Geprüft 25.09.2026 (Nutzeranfrage \"können wir mehr Portale dazu fügen?\"): "
            "vergabe.bayern.de bettet seine Bekanntmachungen aus der RIB/iTWO-Plattform "
            "(meinauftrag.rib.de) ein - derselben Software-Familie, auf die ITDZ Berlin nur extern "
            "verlinkt. robots.txt dort erlaubt automatisierten Zugriff vollständig (\"Allow: /\"), "
            "Liste und Detailseiten sind ohne Login öffentlich (nur die Angebotsabgabe selbst "
            "verlangt ein Bieterkonto). Connector implementiert. Seit 25.09.2026 ohne Bayern-Filter: "
            "alle Vergabestellen der RIB-Plattform bundesweit (ca. 1170 statt 400 Bekanntmachungen)."
        ),
    ),
    dict(
        slug="foerderdatenbank-ki",
        robots_status="geprueft_einschraenkung",
        name="AI-Förderprogramme (Förderdatenbank BMWK/BMBF)",
        base_url="https://www.foerderdatenbank.de/",
        betreiber="Bundesministerium für Wirtschaft und Klimaschutz / Bundesministerium für Bildung und Forschung",
        intervall_minuten=1440,
        hinweis=(
            "Geprüft 04.09.2026: robots.txt erlaubt Zugriff (Crawl-delay: 30), die Website selbst "
            "läuft aber hinter Radware Bot Manager (JS-Verifikationsseite statt echtem Inhalt bei "
            "automatisiertem Abruf) - CAPTCHA-artiger Bot-Schutz erkannt, nicht umgangen (Kapitel 9.2). "
            "Empfehlung: nach offiziellem Datenexport/OpenData-Angebot des Bundes suchen."
        ),
    ),
]

# Für Zusatzportale mit echtem, fertigem Connector wird der Pending-Platzhalter unten
# übersprungen - diese Zuordnung muss VOR der Pending-Schleife stehen, damit die Schleife sie
# nicht überschreibt.
_ECHTE_ZUSATZ_CONNECTOREN: dict[str, type[BaseConnector]] = {
    TedConnector.slug: TedConnector,
    DtvpConnector.slug: DtvpConnector,
    EvergabeBundConnector.slug: EvergabeBundConnector,
    OeffentlicheVergabeConnector.slug: OeffentlicheVergabeConnector,
    VergabeBayernConnector.slug: VergabeBayernConnector,
}
CONNECTORS.update(_ECHTE_ZUSATZ_CONNECTOREN)

for _p in ZUSATZPORTALE:
    if _p["slug"] not in _ECHTE_ZUSATZ_CONNECTOREN:
        CONNECTORS[_p["slug"]] = make_pending_connector(_p["slug"], _p["name"], _p["base_url"], _p["hinweis"])

__all__ = ["BaseConnector", "CONNECTORS", "ZUSATZPORTALE"]
