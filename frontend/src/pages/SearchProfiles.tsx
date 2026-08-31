import { useCallback, useState } from 'react'
import {
  ApiError,
  createSearchProfile,
  deleteSearchProfile,
  fetchCategories,
  fetchPortals,
  fetchSearchProfileHits,
  fetchSearchProfiles,
  updateSearchProfile,
} from '../api/client'
import { ProfileForm } from '../components/ProfileForm'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { TenderCard } from '../components/TenderCard'
import { useAsync } from '../hooks/useAsync'
import type { SearchProfile, SearchProfileInput } from '../api/types'

function ProfileHits({ profileId }: { profileId: string }) {
  const fetcher = useCallback(() => fetchSearchProfileHits(profileId), [profileId])
  const { data, loading, error, reload } = useAsync(fetcher, [fetcher])

  if (loading) return <LoadingView label="Lade Treffer…" />
  if (error) return <ErrorView title="Treffer konnten nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />
  if (!data || data.items.length === 0) return <EmptyView title="Noch keine Treffer" description="Für dieses Profil wurden bisher keine passenden Ausschreibungen gefunden." />

  return (
    <div className="flex flex-col gap-3">
      {data.items.map((tender) => (
        <TenderCard key={tender.id} tender={tender} />
      ))}
    </div>
  )
}

function ProfileCard({
  profile,
  onEdit,
  onDelete,
  onToggleHits,
  hitsOpen,
}: {
  profile: SearchProfile
  onEdit: () => void
  onDelete: () => void
  onToggleHits: () => void
  hitsOpen: boolean
}) {
  const [deleting, setDeleting] = useState(false)

  return (
    <div className="rounded-lg border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-ink">{profile.name}</h3>
            {!profile.aktiv ? (
              <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-ink-faint">Inaktiv</span>
            ) : null}
            {profile.neue_treffer_anzahl ? (
              <span className="rounded-full bg-urgent-redBg px-2 py-0.5 text-xs font-semibold text-urgent-red">
                {profile.neue_treffer_anzahl} neu
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-ink-faint">
            {profile.portale.length ? `${profile.portale.length} Portal(e)` : 'Alle Portale'}
            {profile.keywords.length ? ` · ${profile.keywords.join(', ')}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onEdit} className="focus-ring rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken">
            Bearbeiten
          </button>
          <button
            type="button"
            disabled={deleting}
            onClick={() => {
              setDeleting(true)
              onDelete()
            }}
            className="focus-ring rounded-md border border-line px-3 py-1.5 text-xs font-medium text-urgent-red hover:bg-urgent-redBg disabled:opacity-50"
          >
            Löschen
          </button>
        </div>
      </div>

      <button type="button" onClick={onToggleHits} className="focus-ring mt-3 text-xs font-medium text-brand hover:underline">
        {hitsOpen ? 'Treffer ausblenden' : 'Treffer anzeigen'}
      </button>

      {hitsOpen ? (
        <div className="mt-3 border-t border-line pt-3">
          <ProfileHits profileId={profile.id} />
        </div>
      ) : null}
    </div>
  )
}

export function SearchProfiles() {
  const { data: profiles, loading, error, reload } = useAsync(fetchSearchProfiles, [])
  const { data: portals } = useAsync(fetchPortals, [])
  const { data: categories } = useAsync(fetchCategories, [])

  const [formMode, setFormMode] = useState<'closed' | 'create' | string>('closed')
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [openHitsId, setOpenHitsId] = useState<string | null>(null)

  const editingProfile = formMode !== 'closed' && formMode !== 'create' ? (profiles ?? []).find((p) => p.id === formMode) : undefined

  const handleCreate = useCallback(
    async (input: SearchProfileInput) => {
      setSubmitting(true)
      setFormError(null)
      try {
        await createSearchProfile(input)
        setFormMode('closed')
        reload()
      } catch (err) {
        setFormError(err instanceof ApiError ? err.message : 'Profil konnte nicht angelegt werden.')
      } finally {
        setSubmitting(false)
      }
    },
    [reload],
  )

  const handleUpdate = useCallback(
    async (id: string, input: SearchProfileInput) => {
      setSubmitting(true)
      setFormError(null)
      try {
        await updateSearchProfile(id, input)
        setFormMode('closed')
        reload()
      } catch (err) {
        setFormError(err instanceof ApiError ? err.message : 'Profil konnte nicht gespeichert werden.')
      } finally {
        setSubmitting(false)
      }
    },
    [reload],
  )

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm('Dieses Suchprofil wirklich löschen?')) return
      try {
        await deleteSearchProfile(id)
        reload()
      } catch {
        window.alert('Profil konnte nicht gelöscht werden.')
      }
    },
    [reload],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Suchprofile</h1>
          <p className="mt-0.5 text-sm text-ink-muted">Gespeicherte Filterkombinationen mit eigenem Treffer-Feed.</p>
        </div>
        {formMode === 'closed' ? (
          <button
            type="button"
            onClick={() => setFormMode('create')}
            className="focus-ring rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90"
          >
            + Neues Profil
          </button>
        ) : null}
      </div>

      {formMode === 'create' ? (
        <>
          {formError ? <p className="text-sm text-urgent-red">{formError}</p> : null}
          <ProfileForm
            portals={portals ?? []}
            categories={categories ?? []}
            submitting={submitting}
            onSubmit={handleCreate}
            onCancel={() => setFormMode('closed')}
          />
        </>
      ) : null}

      {editingProfile ? (
        <>
          {formError ? <p className="text-sm text-urgent-red">{formError}</p> : null}
          <ProfileForm
            portals={portals ?? []}
            categories={categories ?? []}
            initial={{
              name: editingProfile.name,
              portale: editingProfile.portale,
              keywords: editingProfile.keywords,
              aktiv: editingProfile.aktiv,
              filter_json: editingProfile.filter_json,
            }}
            submitting={submitting}
            onSubmit={(input) => handleUpdate(editingProfile.id, input)}
            onCancel={() => setFormMode('closed')}
          />
        </>
      ) : null}

      {loading ? <LoadingView label="Lade Suchprofile…" /> : null}
      {!loading && error ? (
        <ErrorView title="Suchprofile konnten nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />
      ) : null}
      {!loading && !error && profiles && profiles.length === 0 ? (
        <EmptyView title="Noch keine Suchprofile" description="Lege ein Profil an, um automatisch nach passenden Ausschreibungen zu filtern." />
      ) : null}

      {!loading && !error && profiles && profiles.length > 0 ? (
        <div className="flex flex-col gap-4">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              onEdit={() => setFormMode(profile.id)}
              onDelete={() => void handleDelete(profile.id)}
              onToggleHits={() => setOpenHitsId(openHitsId === profile.id ? null : profile.id)}
              hitsOpen={openHitsId === profile.id}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}
