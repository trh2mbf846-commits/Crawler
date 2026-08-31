import { useState, type FormEvent } from 'react'
import type { PortalHealth, SearchProfileInput } from '../api/types'

interface ProfileFormProps {
  portals: PortalHealth[]
  categories: string[]
  initial?: SearchProfileInput
  submitting: boolean
  onSubmit: (input: SearchProfileInput) => void
  onCancel: () => void
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((entry) => entry !== value) : [...list, value]
}

export function ProfileForm({ portals, categories, initial, submitting, onSubmit, onCancel }: ProfileFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [portale, setPortale] = useState<string[]>(initial?.portale ?? [])
  const [keywords, setKeywords] = useState<string[]>(initial?.keywords ?? [])
  const [keywordDraft, setKeywordDraft] = useState('')
  const [aktiv, setAktiv] = useState(initial?.aktiv ?? true)
  const [kategorie, setKategorie] = useState<string[]>(
    Array.isArray(initial?.filter_json.kategorie) ? (initial.filter_json.kategorie as string[]) : [],
  )

  const addKeyword = () => {
    const value = keywordDraft.trim()
    if (value && !keywords.includes(value)) {
      setKeywords([...keywords, value])
    }
    setKeywordDraft('')
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    onSubmit({
      name: name.trim(),
      portale,
      keywords,
      aktiv,
      filter_json: kategorie.length ? { kategorie } : {},
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5 shadow-card">
      <div>
        <label className="mb-1 block text-xs font-medium text-ink-faint" htmlFor="profile-name">
          Name
        </label>
        <input
          id="profile-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="z. B. KI-Projekte Berlin"
          required
          className="focus-ring w-full rounded-md border border-line bg-surface px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-ink-faint" htmlFor="profile-keywords">
          Keywords
        </label>
        <div className="flex flex-wrap gap-1.5">
          {keywords.map((keyword) => (
            <span key={keyword} className="inline-flex items-center gap-1 rounded-full bg-brand-light px-2.5 py-1 text-xs font-medium text-brand">
              {keyword}
              <button
                type="button"
                onClick={() => setKeywords(keywords.filter((entry) => entry !== keyword))}
                className="focus-ring rounded-full text-brand/70 hover:text-brand"
                aria-label={`${keyword} entfernen`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <input
          id="profile-keywords"
          value={keywordDraft}
          onChange={(event) => setKeywordDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault()
              addKeyword()
            }
          }}
          onBlur={addKeyword}
          placeholder="Keyword eingeben, mit Enter bestätigen…"
          className="focus-ring mt-2 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm"
        />
      </div>

      {portals.length > 0 ? (
        <div>
          <p className="mb-1.5 text-xs font-medium text-ink-faint">Portale</p>
          <div className="flex flex-wrap gap-1.5">
            {portals.map((portal) => (
              <button
                key={portal.id}
                type="button"
                onClick={() => setPortale(toggle(portale, portal.id))}
                className={`focus-ring rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                  portale.includes(portal.id) ? 'border-brand bg-brand-light text-brand' : 'border-line text-ink-muted hover:bg-surface-sunken'
                }`}
              >
                {portal.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {categories.length > 0 ? (
        <div>
          <p className="mb-1.5 text-xs font-medium text-ink-faint">Kategorien-Filter</p>
          <div className="flex flex-wrap gap-1.5">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => setKategorie(toggle(kategorie, category))}
                className={`focus-ring rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                  kategorie.includes(category) ? 'border-brand bg-brand-light text-brand' : 'border-line text-ink-muted hover:bg-surface-sunken'
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <label className="flex items-center gap-2 text-sm text-ink-muted">
        <input type="checkbox" checked={aktiv} onChange={(event) => setAktiv(event.target.checked)} className="focus-ring h-4 w-4 rounded border-line" />
        Profil aktiv
      </label>

      <div className="flex items-center gap-2 border-t border-line pt-4">
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="focus-ring rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Speichert…' : 'Speichern'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="focus-ring rounded-md border border-line px-4 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken"
        >
          Abbrechen
        </button>
      </div>
    </form>
  )
}
