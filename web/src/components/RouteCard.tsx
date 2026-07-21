import type { FC } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Factory, Package, ShoppingCart, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'

import FreshnessBadge from './FreshnessBadge'
import ScenarioBlock from './ScenarioBlock'
import WarningBadge from './WarningBadge'
import { cn } from '../lib/cn'
import { fmtPct, fmtSilver } from '../lib/format'
import { fadeUp } from '../lib/motion'
import type { Route, SourcingLeg } from '../types/optimizer'

interface Props {
  route: Route
}

const RECO_LABEL: Record<string, string> = {
  instant_sell: 'INSTANT SELL — gain marginal du sell order insuffisant',
  sell_order: 'SELL ORDER — gain marginal significatif',
  au_choix: 'AU CHOIX — les deux scenarios se valent',
}

const RouteCard: FC<Props> = ({ route }) => {
  const positive = route.benefice >= 0
  const borderColor = positive ? 'border-positive/40' : 'border-negative/40'
  const roiTone = positive ? 'text-positive' : 'text-negative'
  const TrendIcon = positive ? TrendingUp : TrendingDown

  return (
    <motion.article
      variants={fadeUp}
      className={cn(
        'rounded-xl border bg-surface-raised shadow-card overflow-hidden',
        borderColor,
      )}
    >
      {/* Header : TOP N + narratif Capital -> Benefice (ROI) */}
      <header className="border-b border-surface-border/60 bg-surface-sunken/40 px-5 py-4">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <span className="rounded-md bg-primary-500/15 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-primary-300">
              TOP {route.rank}
            </span>
            <span className="text-sm text-ink-muted">
              Tier {route.tier} — {route.quantite} planks
            </span>
          </div>
          <div className={cn('flex items-center gap-2 text-sm font-semibold', roiTone)}>
            <TrendIcon className="h-4 w-4" />
            ROI capital {fmtPct(route.marge_pct)}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          <Metric label="Capital depense" value={fmtSilver(route.cout_total)} />
          <Metric
            label="Benefice safe"
            value={
              <span className={cn('num font-semibold', roiTone)}>
                {route.benefice >= 0 ? '+' : ''}
                {fmtSilver(route.benefice)}
              </span>
            }
          />
          <Metric
            label="Cout net (apres recup)"
            value={fmtSilver(route.cout_net)}
            dim
          />
        </div>
      </header>

      <div className="grid gap-5 p-5 lg:grid-cols-2">
        {/* Colonne gauche : achat + raffinage + recup */}
        <section className="space-y-4">
          <SourcingRow leg={route.achat_wood} icon={<ShoppingCart className="h-4 w-4" />} label="Achat bois" />
          {route.achat_plank && (
            <SourcingRow
              leg={route.achat_plank}
              icon={<Package className="h-4 w-4" />}
              label={`Achat plank T${route.achat_plank.tier}`}
            />
          )}

          <div className="rounded-lg border border-surface-border/60 bg-surface/60 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
              <Factory className="h-4 w-4 text-primary-400" />
              Raffinage — Fort Sterling
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted">
              <RowKV label="RRR effectif" value={`${(route.raffinage.rrr_effectif * 100).toFixed(1)}%`} />
              <RowKV label="Cout station" value={fmtSilver(route.raffinage.cout_station)} />
              <RowKV label="Produits" value={`${route.raffinage.planks_produits} planks`} />
              <RowKV
                label="Retours RRR"
                value={`${route.raffinage.wood_retour.toFixed(0)} bois + ${route.raffinage.plank_moins_1_retour.toFixed(0)} plank T-1`}
              />
              {route.raffinage.focus_utilise > 0 && (
                <RowKV label="Focus" value={route.raffinage.focus_utilise.toFixed(0)} />
              )}
            </dl>
          </div>

          {(route.recup_totale > 0 || route.recup_wood_demande > 0) && (
            <div className="rounded-lg border border-positive/20 bg-positive/5 p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-positive">
                <Sparkles className="h-4 w-4" />
                Recup @ {route.recup_city}
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted">
                <RowKV label="Valeur nette" value={<span className="text-positive num">{fmtSilver(route.recup_totale)}</span>} />
                <RowKV
                  label="Absorption bois"
                  value={`${route.recup_wood_absorbe} / ${route.recup_wood_demande}`}
                />
                {route.achat_plank && (
                  <RowKV
                    label="Absorption planks T-1"
                    value={`${route.recup_plank_absorbe} / ${route.recup_plank_demande}`}
                  />
                )}
              </dl>
            </div>
          )}
        </section>

        {/* Colonne droite : vente A/B */}
        <section className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ArrowRight className="h-4 w-4 text-primary-400" />
            Vente @ {route.vente.ville}
          </div>
          <ScenarioBlock scenario={route.vente.scenario_a_instant_sell} slot="a" />
          <ScenarioBlock scenario={route.vente.scenario_b_sell_order} slot="b" />
          {route.silver_par_focus !== null && (
            <div className="rounded-md border border-surface-border/60 bg-surface/40 px-3 py-2 text-xs text-ink-muted">
              <span className="text-ink-faint">Silver / focus : </span>
              <span className="num text-ink">{route.silver_par_focus.toFixed(2)} s</span>
            </div>
          )}
        </section>
      </div>

      {/* Recommandation + marge efficacite en pied */}
      <footer className="border-t border-surface-border/60 bg-surface-sunken/40 px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs">
            <span className="text-ink-faint">Reco : </span>
            <span className="font-semibold text-ink">
              {RECO_LABEL[route.vente.recommandation] ?? route.vente.recommandation}
            </span>
          </div>
          <div className="text-xs text-ink-faint">
            marge efficacite (V1 secondaire) :{' '}
            <span className="num text-ink-muted">{fmtPct(route.marge_efficacite_pct)}</span>
          </div>
        </div>
        {route.warnings.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {route.warnings.map((code) => (
              <WarningBadge key={code} code={code} />
            ))}
          </div>
        )}
      </footer>
    </motion.article>
  )
}

interface SourcingRowProps {
  leg: SourcingLeg
  icon: React.ReactNode
  label: string
}

const SourcingRow: FC<SourcingRowProps> = ({ leg, icon, label }) => (
  <div className="rounded-lg border border-surface-border/60 bg-surface/60 p-3">
    <div className="mb-2 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        {icon}
        {label}
      </div>
      <FreshnessBadge level={leg.freshness} ageHours={leg.data_age_hours} compact />
    </div>
    <div className="flex items-baseline justify-between gap-3 text-xs">
      <span className="text-ink-muted">
        {leg.city} —{' '}
        <span className="num text-ink">{leg.prix_unitaire.toFixed(0)} s</span> ×{' '}
        <span className="num text-ink">{leg.quantite}</span>
      </span>
      <span className="num text-sm font-semibold text-ink">{fmtSilver(leg.cout_total)}</span>
    </div>
  </div>
)

interface MetricProps {
  label: string
  value: React.ReactNode
  dim?: boolean
}

const Metric: FC<MetricProps> = ({ label, value, dim }) => (
  <div className={cn('flex flex-col', dim && 'opacity-70')}>
    <span className="text-[10px] uppercase tracking-wider text-ink-faint">{label}</span>
    <span className="num text-sm text-ink">{value}</span>
  </div>
)

interface RowKVProps {
  label: string
  value: React.ReactNode
}

const RowKV: FC<RowKVProps> = ({ label, value }) => (
  <>
    <dt className="text-ink-faint">{label}</dt>
    <dd className="text-right text-ink num">{value}</dd>
  </>
)

export default RouteCard
