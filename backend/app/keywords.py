"""KI-Relevanz Stufe 1: Keyword- und CPV-Filterung (Kapitel 4.1, 4.2).

Die Listen sind laut Handlungsanweisung ein Ausgangspunkt, der laufend erweitert und bei
Bedarf mit Vincent abgestimmt wird (Kapitel 4.1). Neue Begriffe/Codes können hier ergänzt
werden, ohne die übrige Klassifikationslogik anzufassen.
"""
from __future__ import annotations

# Kapitel 4.1 - Ausgangsliste an Suchbegriffen (deutsch/englisch).
#
# WICHTIG: Kurze Akronyme (ki, ai, ml, llm, rpa, nlp) sind bewusst mit einem führenden UND
# einem folgenden Leerzeichen gepolstert (" ki ") bzw. mit Leerzeichen+Bindestrich, damit sie
# nur als eigenständiges Wort/Wortbestandteil treffen, nicht als Teilstring irgendwo mitten in
# einem unrelated deutschen Wort. Ohne diesen Schutz matcht z. B. "llm" in "bevollmächtigt",
# "ml" in "nichtförmliches [Verfahren]", "rpa" in "Fuhrparkmanagement" und "ai" in "E-Mail" -
# das wurde am 31.08.2026 an echten Vergabekooperation-Berlin-Daten nachgewiesen (89 von 139
# Ausschreibungen fälschlich als "stark KI-relevant" markiert, u. a. Bauleistungen). Beim
# Ergänzen neuer Kurz-Akronyme IMMER mit Leerzeichen/Bindestrich-Grenzen versehen, siehe
# find_keyword_hits() unten, die diese Polsterung beim Abgleich bewusst NICHT entfernt.
KI_KEYWORDS: list[str] = [
    "künstliche intelligenz", "kuenstliche intelligenz", " ki ", " ki-", "artificial intelligence", " ai ", " ai-",
    "maschinelles lernen", "machine learning", " ml ",
    "deep learning", "neuronale netze", "neuronales netz", "neural network",
    "generative ki", "generative ai", "large language model", " llm ", "sprachmodell",
    "chatbot", "virtueller assistent", "sprachassistent", "conversational ai",
    "computer vision", "bilderkennung", "bildverarbeitung",
    "natural language processing", " nlp ", "textanalyse", "sprachverarbeitung",
    "predictive analytics", "prognosemodell", "data science", "datenanalyse",
    "prozessautomatisierung", "robotic process automation", " rpa ", "intelligente automatisierung",
    "ki-strategie", "ki-plattform", "ki-beratung", "algorithmisches entscheidungssystem",
]

# Kapitel 4.2 - Startliste CPV-Codegruppen (IT-Dienstleistungen, Softwareentwicklung,
# Beratung, Forschung & Entwicklung). Vor Produktivbetrieb gegen die aktuelle offizielle
# CPV-Liste abgleichen und Vincent zur Kontrolle vorlegen (siehe Kapitel 4.2 - hier als
# TODO/Eskalationsanlass dokumentiert statt stillschweigend final zu setzen).
KI_RELEVANTE_CPV_PRAEFIXE: list[str] = [
    "72000000",  # IT-Dienste: Beratung, Software, Internet u. Hilfestellung
    "72200000",  # Softwareprogrammierung und -beratung
    "72210000",  # Programmierung von Softwarepaketen
    "72220000",  # Systemberatung und technische Beratung
    "72240000",  # Systemanalyse und Programmierung
    "72260000",  # Softwarebezogene Dienstleistungen
    "72300000",  # Datendienste
    "72310000",  # Datenverarbeitung
    "72316000",  # Datenanalyse
    "73000000",  # Forschung, Entwicklung und zugehörige Beratung
    "73100000",  # Forschungs- und Entwicklungsdienstleistungen
]

# Bekannte, portalspezifische Fehltreffer: "AI" ist auf der Vergabekooperation-Berlin-Plattform
# (u. a. auf jeder Detailseite) die Kurzform von "Administration Intelligence AG", dem
# Plattformbetreiber (Produktnamen "AI-Bietercockpit"/"AI-Leistungsverzeichnis"), NICHT von
# "Artificial Intelligence" - nachgewiesen am 31.08.2026 an echten Daten (jeder einzelne der 139
# getesteten Datensätze enthielt einen dieser Treffer, ausnahmslos falsch-positiv). Werden vor
# dem Keyword-Abgleich entfernt, damit " ai "/" ai-" nur noch bei echten Treffern greift.
_BEKANNTE_FEHLTREFFER_PHRASEN = [
    "ai-bietercockpit", "ai bietercockpit", "ai-leistungsverzeichnis", "vergabemanager ai",
]


def find_keyword_hits(*texts: str | None) -> list[str]:
    """Liefert die tatsächlich gefundenen Suchbegriffe (nachvollziehbarer Treffer, Kapitel 24).

    Der Abgleich erfolgt gegen den UNGEKÜRZTEN Suchbegriff aus KI_KEYWORDS (inkl. der bewusst
    gesetzten Leerzeichen-/Bindestrich-Wortgrenzen) - nur die Anzeige im Rückgabewert wird
    getrimmt. Ein `.strip()` vor dem Abgleich würde den Wortgrenzen-Schutz wirkungslos machen
    (siehe Kommentar bei KI_KEYWORDS).
    """
    joined = " ".join(f" {t.lower()} " for t in texts if t)
    for phrase in _BEKANNTE_FEHLTREFFER_PHRASEN:
        joined = joined.replace(phrase, " ")
    hits: list[str] = []
    for keyword in KI_KEYWORDS:
        if keyword and keyword in joined:
            display = keyword.strip()
            if display not in hits:
                hits.append(display)
    return hits


def find_cpv_hits(cpv_codes: list[str]) -> list[str]:
    hits = []
    for code in cpv_codes or []:
        normalized = code.replace("-", "").strip()
        for prefix in KI_RELEVANTE_CPV_PRAEFIXE:
            if normalized.startswith(prefix[:6]) and code not in hits:
                hits.append(code)
    return hits
