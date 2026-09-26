"""Kevin-Prüfsatz (26.09.2026, Empfehlung aus Anthropics "Building Effective Agents": Werkzeuge
und Prompts mit echten Beispielen testen und messen, statt nach Gefühl zu verbessern).

Stellt Kevin eine feste Reihe typischer Fragen gegen das gerade eingestellte Sprachmodell und die
vorhandene Datenbank und prüft, ob er das richtige Werkzeug wählt (bzw. die richtige Aktion
vorschlägt). Aufruf im Ordner backend (Crawler muss nicht laufen, Ollama schon):

    .venv/bin/python -m app.kevin_pruefsatz

Nützlich nach jeder Änderung an Kevin oder um Modelle zu vergleichen, z. B.
CRAWLER_OLLAMA_MODEL=qwen3:4b .venv/bin/python -m app.kevin_pruefsatz
"""
from __future__ import annotations

import sys
import time

from app.agents import assistant
from app.db import SessionLocal, init_db
from app.prompts import llm_bezeichnung

PRUEFFRAGEN: list[tuple[str, str]] = [
    ("Welche KI-Ausschreibungen gibt es gerade?", "suche_ausschreibungen"),
    ("Gibt es Ausschreibungen zu Chatbots oder Sprachassistenten?", "suche_ausschreibungen"),
    ("Welche Fristen stehen in den nächsten zwei Wochen an?", "fristen_uebersicht"),
    ("Funktionieren gerade alle Portale?", "quellstatus"),
    ("Starte bitte eine Aktualisierung aller Portale.", "aktualisieren_starten"),
    ("Merk dir als Wunsch: Die Übersicht soll nach Bundesland filtern können.", "verbesserungswunsch_notieren"),
    ("Lege ein Suchprofil 'KI Berlin' für KI-Ausschreibungen in Berlin an.", "suchprofil_anlegen"),
    ("Suche die wichtigste KI-Ausschreibung und sag mir, ob ich mich darauf bewerben soll.", "bewerbung_bewerten"),
]


def fuehre_aus() -> int:
    init_db()
    db = SessionLocal()
    genutzt: list[str] = []
    original = assistant._execute_tool

    def mitschreiben(db_, name, tool_input, gefundene):
        genutzt.append(name)
        return original(db_, name, tool_input, gefundene)

    assistant._execute_tool = mitschreiben
    print(f"Kevin-Prüfsatz mit {llm_bezeichnung()} - {len(PRUEFFRAGEN)} Fragen\n")
    bestanden = 0
    try:
        for frage, erwartet in PRUEFFRAGEN:
            genutzt.clear()
            start = time.time()
            ergebnis = assistant.run_assistant_chat(db, frage)
            werkzeuge = list(genutzt) + ([ergebnis.vorschlag.name] if ergebnis.vorschlag else [])
            ok = erwartet in werkzeuge
            bestanden += ok
            print(f"{'✓' if ok else '✗'} {frage}")
            print(f"    erwartet: {erwartet} | genutzt: {', '.join(werkzeuge) or '-'} | {time.time() - start:.0f} s")
            if not ok:
                print(f"    Antwort: {ergebnis.antwort[:160]}")
    finally:
        assistant._execute_tool = original
        db.close()
    print(f"\nErgebnis: {bestanden}/{len(PRUEFFRAGEN)} richtig")
    return 0 if bestanden == len(PRUEFFRAGEN) else 1


if __name__ == "__main__":
    sys.exit(fuehre_aus())
