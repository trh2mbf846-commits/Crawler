"""Hilfsfunktionen zur robusten Abbildung unterschiedlicher Portal-Rohformate auf das

einheitliche Datenmodell (Kapitel 6, 9.1: "Unterschiedliche Datums-, Zahlen- und Textformate
der Portale robust auf das einheitliche Datenmodell abbilden").
"""
from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateutil_parser


def parse_date_de(value: str | None) -> datetime | None:
    """Parst deutsche (TT.MM.JJJJ) und ISO-Datumsformate robust; gibt None statt zu werfen."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return dateutil_parser.parse(value, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None


_NUMBER_RE = re.compile(r"[-+]?\d[\d.,]*")


def parse_currency_de(value: str | None) -> float | None:
    """Parst deutsche Zahlenformate (1.234.567,89 EUR) sowie einfache englische Notation."""
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    if not match:
        return None
    raw = match.group(0)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def make_kurzbeschreibung(volltext: str | None, max_len: int = 320) -> str | None:
    if not volltext:
        return None
    text = re.sub(r"\s+", " ", volltext).strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len].rsplit(" ", 1)[0]
    return truncated + "…"
