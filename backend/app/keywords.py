"""KI-Relevanz Stufe 1: Keyword- und CPV-Filterung (Kapitel 4.1, 4.2).

Die Listen sind laut Handlungsanweisung ein Ausgangspunkt, der laufend erweitert und bei
Bedarf mit Vincent abgestimmt wird (Kapitel 4.1). Neue Begriffe/Codes können hier ergänzt
werden, ohne die übrige Klassifikationslogik anzufassen.
"""
from __future__ import annotations

import re

# Kapitel 4.1 - Ausgangsliste an Suchbegriffen (deutsch/englisch).
KI_KEYWORDS: list[str] = [
    "künstliche intelligenz", "kuenstliche intelligenz", " ki ", "ki-", "artificial intelligence", " ai ", "ai-",
    "maschinelles lernen", "machine learning", " ml ",
    "deep learning", "neuronale netze", "neuronales netz", "neural network",
    "generative ki", "generative ai", "large language model", "llm", "sprachmodell",
    "chatbot", "virtueller assistent", "sprachassistent", "conversational ai",
    "computer vision", "bilderkennung", "bildverarbeitung",
    "natural language processing", "nlp", "textanalyse", "sprachverarbeitung",
    "predictive analytics", "prognosemodell", "data science", "datenanalyse",
    "prozessautomatisierung", "robotic process automation", "rpa", "intelligente automatisierung",
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

_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(k.strip()) for k in KI_KEYWORDS if k.strip()), re.IGNORECASE
)


def find_keyword_hits(*texts: str | None) -> list[str]:
    """Liefert die tatsächlich gefundenen Suchbegriffe (nachvollziehbarer Treffer, Kapitel 24)."""
    joined = " ".join(f" {t.lower()} " for t in texts if t)
    hits: list[str] = []
    for keyword in KI_KEYWORDS:
        k = keyword.strip()
        if k and k in joined and k not in hits:
            hits.append(k)
    return hits


def find_cpv_hits(cpv_codes: list[str]) -> list[str]:
    hits = []
    for code in cpv_codes or []:
        normalized = code.replace("-", "").strip()
        for prefix in KI_RELEVANTE_CPV_PRAEFIXE:
            if normalized.startswith(prefix[:6]) and code not in hits:
                hits.append(code)
    return hits
