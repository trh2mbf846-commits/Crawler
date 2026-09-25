// Dauerhafter Chat-Verlauf für Crawler Kevin (Nutzerwunsch 25.09.2026: Nachrichten sollen beim
// Tab-Wechsel erhalten bleiben, gelöscht wird nur auf ausdrücklichen Wunsch).
//
// Gespeichert im localStorage des Browsers - bleibt damit auch über Neustarts des Crawlers
// erhalten. Eine noch laufende Anfrage wird modulweit gemerkt: wechselt man den Tab, während
// Kevin antwortet, landet die Antwort trotzdem im Verlauf und wird beim Zurückkehren angezeigt.

import type { AssistantActionProposal, AssistantMessage, Tender } from '../api/types'

export interface ChatEntry extends AssistantMessage {
  id: string
  tenders?: Tender[]
  vorschlag?: AssistantActionProposal | null
}

export type AktionStatus = { status: 'ausgefuehrt' | 'abgelehnt' | 'fehler'; meldung?: string }

export interface GespeicherterChat {
  verlauf: ChatEntry[]
  aktionStatus: Record<string, AktionStatus>
}

const SCHLUESSEL = 'crawler-kevin-chat-v1'
// Sehr lange Verläufe begrenzen (localStorage hat nur wenige MB, jede Antwort kann Trefferlisten enthalten).
const MAX_EINTRAEGE = 200

const LEER: GespeicherterChat = { verlauf: [], aktionStatus: {} }

export function ladeChat(): GespeicherterChat {
  try {
    const roh = localStorage.getItem(SCHLUESSEL)
    if (!roh) return LEER
    const daten = JSON.parse(roh) as Partial<GespeicherterChat>
    return {
      verlauf: Array.isArray(daten.verlauf) ? daten.verlauf : [],
      aktionStatus: daten.aktionStatus && typeof daten.aktionStatus === 'object' ? daten.aktionStatus : {},
    }
  } catch {
    return LEER
  }
}

export function speichereChat(chat: GespeicherterChat): void {
  try {
    const verlauf = chat.verlauf.slice(-MAX_EINTRAEGE)
    const ids = new Set(verlauf.map((e) => e.id))
    const aktionStatus = Object.fromEntries(Object.entries(chat.aktionStatus).filter(([id]) => ids.has(id)))
    localStorage.setItem(SCHLUESSEL, JSON.stringify({ verlauf, aktionStatus }))
  } catch {
    // Speicher voll oder gesperrt (z. B. privater Modus) - der Chat funktioniert dann nur ohne Erinnerung.
  }
}

export function loescheChat(): void {
  try {
    localStorage.removeItem(SCHLUESSEL)
  } catch {
    // siehe speichereChat
  }
}

export function haengeAn(eintrag: ChatEntry): GespeicherterChat {
  const chat = ladeChat()
  const neu = { ...chat, verlauf: [...chat.verlauf, eintrag] }
  speichereChat(neu)
  return neu
}

let laufendeAnfrage: Promise<void> | null = null

export function laufendeKevinAnfrage(): Promise<void> | null {
  return laufendeAnfrage
}

export function merkeLaufendeAnfrage(anfrage: Promise<void>): void {
  laufendeAnfrage = anfrage
  anfrage.finally(() => {
    if (laufendeAnfrage === anfrage) laufendeAnfrage = null
  })
}
