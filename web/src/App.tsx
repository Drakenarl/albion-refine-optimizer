import { useEffect, useState, type FC } from 'react'
import { AxiosError } from 'axios'
import { Loader2 } from 'lucide-react'

import OptimizeForm from './components/OptimizeForm'
import { fetchConfig, postOptimize } from './api/optimize'
import type {
  ConfigResponse,
  OptimizationResult,
  OptimizeRequest,
} from './types/optimizer'

// Session 1 : la page ne fait que valider le tuyau. Le rendu détaillé des
// routes (RouteCard, badges, warnings) arrive en Session 2. Ici on affiche le
// JSON brut renvoyé par le backend pour prouver le bout-en-bout.
const App: FC = () => {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [result, setResult] = useState<OptimizationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch((err: unknown) => setError(describeError(err, 'Chargement config')))
  }, [])

  const handleOptimize = async (payload: OptimizeRequest): Promise<void> => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await postOptimize(payload)
      setResult(data)
    } catch (err: unknown) {
      setError(describeError(err, 'Optimisation'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="border-b border-surface-border">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <h1 className="text-2xl font-semibold tracking-tight">Albion Refine Optimizer</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Optimisation de raffinage bois — Fort Sterling · V2
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8 space-y-6">
        {!config && !error && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Chargement de la configuration…
          </div>
        )}

        {config && (
          <OptimizeForm config={config} loading={loading} onSubmit={handleOptimize} />
        )}

        {error && (
          <div className="rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            L'optimiseur interroge l'AODP…
          </div>
        )}

        {result && !loading && (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">
              Réponse brute — {result.routes.length} route(s) rentable(s),{' '}
              {result.discarded_top.length} alternative(s) écartée(s)
            </h2>
            <pre className="max-h-[70vh] overflow-auto rounded-lg border border-surface-border bg-surface-sunken p-4 text-xs num">
              {JSON.stringify(result, null, 2)}
            </pre>
            <p className="text-xs text-ink-faint">
              Session 1 : rendu brut pour valider le tuyau. Session 2 remplace ce JSON par
              des cards structurées (RouteCard, badges de fraîcheur, warnings).
            </p>
          </section>
        )}
      </main>
    </div>
  )
}

function describeError(err: unknown, prefix: string): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail as string | undefined
    return `${prefix} — ${err.response?.status ?? '?'} : ${detail ?? err.message}`
  }
  if (err instanceof Error) return `${prefix} — ${err.message}`
  return `${prefix} — erreur inconnue`
}

export default App
