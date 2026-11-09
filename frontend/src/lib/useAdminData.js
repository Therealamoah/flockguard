import { useCallback, useEffect, useState } from 'react'

// Loads one admin endpoint: `fetcher` must be a stable function (an
// api.admin.* method or a module-level wrapper) and `arg` a primitive, so
// the effect only re-runs when the request actually changes. `reload()`
// re-fetches after a write; the previous data stays on screen meanwhile.
export function useAdminData(fetcher, arg) {
  const [version, setVersion] = useState(0)
  const [result, setResult] = useState({ key: null, data: null, error: '' })
  const key = `${arg ?? ''}|${version}`

  useEffect(() => {
    let cancelled = false
    fetcher(arg).then(
      (data) => {
        if (!cancelled) setResult({ key, data, error: '' })
      },
      (err) => {
        if (!cancelled) {
          setResult((prev) => ({
            key,
            data: prev.data,
            error: err.detail || 'Could not load this data. Please try again.',
          }))
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [fetcher, arg, key])

  const reload = useCallback(() => setVersion((v) => v + 1), [])

  return { data: result.data, error: result.error, isLoading: result.key !== key, reload }
}
