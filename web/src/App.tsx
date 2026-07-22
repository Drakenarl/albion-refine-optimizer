import { useEffect, useState, type FC } from 'react'
import { AxiosError } from 'axios'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, HelpCircle, Loader2, PackageSearch, RefreshCw } from 'lucide-react'

import AlternativesList from './components/AlternativesList'
import ChecklistPanel from './components/ChecklistPanel'
import HowItWorksModal from './components/HowItWorksModal'
import OptimizeForm from './components/OptimizeForm'
import RouteCard from './components/RouteCard'
import { fetchConfig, postOptimize } from './api/optimize'
import { fadeIn, staggerContainer } from './lib/motion'
import type {
  ConfigResponse,
  OptimizationResult,
  OptimizeRequest,
} from './types/optimizer'

const App: FC = () => {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [result, setResult] = useState<OptimizationResult | null>(null)
  const [lastPayload, setLastPayload] = useState<OptimizeRequest | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [guideOpen, setGuideOpen] = useState(false)

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch((err: unknown) => setError(describeError(err, 'Chargement config')))
  }, [])

  const handleOptimize = async (payload: OptimizeRequest): Promise<void> => {
    setLoading(true)
    setError(null)
    setResult(null)
    setLastPayload(payload)
    try {
      const data = await postOptimize(payload)
      setResult(data)
    } catch (err: unknown) {
      setError(describeError(err, 'Optimisation'))
    } finally {
      setLoading(false)
    }
  }

  // Re-lance la derniere requete en forcant le refresh du cache AODP cote back.
  // Utile quand l'utilisateur vient d'ouvrir un carnet en jeu (avec le client
  // AODP actif) et veut que les nouveaux prix remontent immediatement.
  const handleRefresh = async (): Promise<void> => {
    if (!lastPayload) return
    await handleOptimize({ ...lastPayload, use_cache: false })
  }

  const seuil = lastPayload?.seuil_marge_min_pct ?? config?.seuil_marge_default ?? 0

  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="border-b border-surface-border bg-surface-sunken/60 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Albion Refine Optimizer</h1>
            <p className="mt-0.5 text-xs text-ink-muted">
              5 filières · bois · peau · fibre · minerai · pierre · V2.4
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setGuideOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-muted transition hover:border-primary-500/50 hover:bg-primary-500/5 hover:text-ink"
            >
              <HelpCircle className="h-3.5 w-3.5" />
              Comment ça marche
            </button>
            <a
              href="https://github.com/Drakenarl/albion-refine-optimizer"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-ink-faint transition hover:text-ink"
            >
              GitHub ↗
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {!config && !error && <BootLoading />}

        {config && (
          <div className="space-y-6">
            <OptimizeForm config={config} loading={loading} onSubmit={handleOptimize} />

            {error && (
              <div className="rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">
                {error}
              </div>
            )}

            <AnimatePresence mode="wait">
              {loading && (
                <motion.div
                  key="loading"
                  variants={fadeIn}
                  initial="hidden"
                  animate="show"
                  exit="hidden"
                  className="flex items-center gap-2 text-sm text-ink-muted"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
                  L'optimiseur interroge l'AODP…
                </motion.div>
              )}

              {!loading && result && (
                <motion.div
                  key={result.run_metadata.timestamp}
                  variants={fadeIn}
                  initial="hidden"
                  animate="show"
                  exit="hidden"
                  className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]"
                >
                  <ResultSection result={result} seuil={seuil} onRefresh={handleRefresh} />
                  <ChecklistPanel checklist={result.refresh_checklist} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </main>

      <footer className="mt-16 border-t border-surface-border/60 py-6 text-center text-xs text-ink-faint">
        Donnees fournies par le Albion Online Data Project. Non affilie a Sandbox Interactive.
      </footer>

      <HowItWorksModal open={guideOpen} onClose={() => setGuideOpen(false)} />
    </div>
  )
}

interface ResultProps {
  result: OptimizationResult
  seuil: number
  onRefresh: () => void
}

const ResultSection: FC<ResultProps> = ({ result, seuil, onRefresh }) => {
  const { routes, discarded_top } = result
  const hasRoutes = routes.length > 0
  const profitable = routes.filter((r) => r.marge_pct > 0).length
  const losing = routes.length - profitable
  const allLosing = losing > 0 && profitable === 0

  const heading = (() => {
    if (!hasRoutes) return 'Aucune route retenue'
    if (allLosing) {
      return `${routes.length} route${routes.length > 1 ? 's' : ''} au-dessus du seuil — toutes deficitaires`
    }
    if (losing === 0) {
      return `${routes.length} route${routes.length > 1 ? 's' : ''} rentable${routes.length > 1 ? 's' : ''}`
    }
    return `${routes.length} routes retenues (${profitable} rentable${profitable > 1 ? 's' : ''}, ${losing} deficitaire${losing > 1 ? 's' : ''})`
  })()

  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <PackageSearch className="h-5 w-5 text-primary-400" />
          <div>
            <h2 className="text-lg font-semibold">{heading}</h2>
            <p className="text-xs text-ink-muted">
              Tier {result.run_metadata.tier} — analysees a{' '}
              {new Date(result.run_metadata.timestamp).toLocaleTimeString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-2.5 py-1.5 text-xs text-ink-muted transition hover:border-primary-500/50 hover:bg-primary-500/5 hover:text-ink"
          title="Force un rafraichissement AODP en ignorant le cache local (5 min)"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Rafraîchir
        </button>
      </header>

      {allLosing && (
        <div className="flex items-start gap-3 rounded-lg border border-caution/40 bg-caution/10 px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-caution" />
          <div className="text-ink">
            Ton seuil est de{' '}
            <span className="num font-semibold">
              {seuil >= 0 ? '+' : ''}
              {seuil}%
            </span>{' '}
            — c'est un plancher, pas un objectif. Les routes affichees passent ce plancher mais
            ont toutes une ROI capital{' '}
            <span className="text-negative">negative</span> : elles te feront perdre du silver.
            Remonter le seuil a <span className="num">0%</span> pour ne voir que du rentable.
          </div>
        </div>
      )}

      {hasRoutes ? (
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="grid gap-4"
        >
          {routes.map((route) => (
            <RouteCard key={route.rank} route={route} />
          ))}
        </motion.div>
      ) : (
        <AlternativesList alternatives={discarded_top} seuil={seuil} />
      )}
    </section>
  )
}

const BootLoading: FC = () => (
  <div className="flex items-center gap-2 text-sm text-ink-muted">
    <Loader2 className="h-4 w-4 animate-spin" />
    Chargement de la configuration…
  </div>
)

function describeError(err: unknown, prefix: string): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail as string | undefined
    return `${prefix} — ${err.response?.status ?? '?'} : ${detail ?? err.message}`
  }
  if (err instanceof Error) return `${prefix} — ${err.message}`
  return `${prefix} — erreur inconnue`
}

export default App
