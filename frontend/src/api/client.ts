import type {
  AssistantActionResult,
  AssistantChatResult,
  AssistantDigest,
  AssistantMessage,
  AssistantPreferences,
  Escalation,
  EscalationStatus,
  HistoryEntry,
  PortalHealth,
  RunAllStatus,
  SearchProfile,
  SearchProfileInput,
  Tender,
  TenderDetail,
  TenderQuery,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api'
// Nutzeranfrage 25.09.2026: Backend akzeptiert optional einen X-API-Key-Header (app/security.py).
// Ohne CRAWLER_API_KEY auf dem Server ignoriert er diesen Header einfach - lokal ohne
// VITE_API_KEY bleibt alles wie bisher.
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      },
      ...init,
    })
  } catch {
    throw new ApiError('Server nicht erreichbar. Läuft das Backend?', 0)
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string; message?: string }
      detail = body.detail ?? body.message ?? detail
    } catch {
      // Antwort ohne JSON-Body ignorieren
    }
    throw new ApiError(detail || `Anfrage fehlgeschlagen (${response.status})`, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function buildQuery(params: Record<string, string | number | string[] | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    if (Array.isArray(value)) {
      value.forEach((entry) => search.append(key, entry))
    } else {
      search.append(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export interface TendersResult {
  items: Tender[]
  total: number
  page: number
  page_size: number
}

export interface HitsResult {
  items: Tender[]
  total: number
}

export function fetchTenders(query: TenderQuery = {}): Promise<TendersResult> {
  const qs = buildQuery({
    q: query.q,
    portal: query.portal,
    kategorie: query.kategorie,
    ki_relevanz_min: query.ki_relevanz_min,
    frist_bis: query.frist_bis,
    status: query.status,
    sort: query.sort,
    page: query.page,
    page_size: query.page_size,
  })
  return request<TendersResult>(`/tenders${qs}`)
}

export function fetchTender(id: string): Promise<TenderDetail> {
  return request<TenderDetail>(`/tenders/${encodeURIComponent(id)}`)
}

export function fetchTenderHistory(id: string): Promise<HistoryEntry[]> {
  return request<HistoryEntry[]>(`/tenders/${encodeURIComponent(id)}/history`)
}

export function fetchPortals(): Promise<PortalHealth[]> {
  return request<PortalHealth[]>('/portals')
}

export function runPortalTest(id: string): Promise<{ started: true }> {
  return request<{ started: true }>(`/portals/${encodeURIComponent(id)}/run`, { method: 'POST' })
}

export function runAllPortals(): Promise<RunAllStatus> {
  return request<RunAllStatus>('/run-all', { method: 'POST' })
}

export function fetchRunAllStatus(): Promise<RunAllStatus> {
  return request<RunAllStatus>('/run-all/status')
}

export function fetchSearchProfiles(): Promise<SearchProfile[]> {
  return request<SearchProfile[]>('/search-profiles')
}

export function createSearchProfile(input: SearchProfileInput): Promise<SearchProfile> {
  return request<SearchProfile>('/search-profiles', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateSearchProfile(id: string, input: SearchProfileInput): Promise<SearchProfile> {
  return request<SearchProfile>(`/search-profiles/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteSearchProfile(id: string): Promise<void> {
  return request<void>(`/search-profiles/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function fetchSearchProfileHits(id: string, page = 1): Promise<HitsResult> {
  const qs = buildQuery({ page })
  return request<HitsResult>(`/search-profiles/${encodeURIComponent(id)}/hits${qs}`)
}

export function fetchEscalations(status?: EscalationStatus): Promise<Escalation[]> {
  const qs = buildQuery({ status })
  return request<Escalation[]>(`/escalations${qs}`)
}

export function resolveEscalation(id: string, entscheidung: string): Promise<Escalation> {
  return request<Escalation>(`/escalations/${encodeURIComponent(id)}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ entscheidung }),
  })
}

export function fetchCategories(): Promise<string[]> {
  return request<string[]>('/categories')
}

export function sendAssistantMessage(nachricht: string, verlauf: AssistantMessage[] = []): Promise<AssistantChatResult> {
  return request<AssistantChatResult>('/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ nachricht, verlauf }),
  })
}

export function executeAssistantAction(name: string, input: Record<string, unknown>): Promise<AssistantActionResult> {
  return request<AssistantActionResult>('/assistant/actions/execute', {
    method: 'POST',
    body: JSON.stringify({ name, input }),
  })
}

export function fetchAssistantDigest(): Promise<AssistantDigest> {
  return request<AssistantDigest>('/assistant/digest')
}

export function fetchAssistantPreferences(): Promise<AssistantPreferences> {
  return request<AssistantPreferences>('/assistant/preferences')
}

export function updateAssistantPreferences(preferences: AssistantPreferences): Promise<AssistantPreferences> {
  return request<AssistantPreferences>('/assistant/preferences', {
    method: 'PUT',
    body: JSON.stringify(preferences),
  })
}
