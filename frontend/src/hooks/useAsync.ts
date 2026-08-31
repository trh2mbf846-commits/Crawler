import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useAsync<T>(fetcher: () => Promise<T>, deps: React.DependencyList): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof ApiError ? err.message : 'Unerwarteter Fehler beim Laden der Daten.'
          setError(message)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  return { data, loading, error, reload }
}
