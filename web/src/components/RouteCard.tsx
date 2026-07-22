import type { FC } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Factory, Package, ShoppingCart, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'

import FreshnessBadge from './FreshnessBadge'
import InfoTooltip from './InfoTooltip'
import ScenarioBlock from './ScenarioBlock'
import WarningBadge from './WarningBadge'
import { cn } from '../lib/cn'
import { fmtPct, fmtSilver } from '../lib/format'
import { GLOSSARY } from '../lib/glossary'
import { fadeUp } from '../lib/motion'
import type { ResourceKind, Route, SourcingLeg } from '../types/optimizer'

interface Props {
  route: Route
}

// Libelles FR par ressource, cales sur config.RESOURCES cote backend. Duplique
// ici pour eviter un round-trip API supplementaire ; a garder en sync.
const RESOURCE_LABELS: Record<
  ResourceKind,
  { raw: string; refined: string; refiningCity: string }
> = {
  wood: { raw: 'bois', refined: 'plank', refiningCity: 'Fort Sterling' },
  hide: { raw: 'peau', refined: 'cuir', refiningCity: 'Martlock' },
  fiber: { raw: 'fibre', refined: 'tissu', refiningCity: 'Lymhurst' },
  ore: { raw: 'minerai', refined: 'lingot', refiningCity: 'Thetford' },
  stone: { raw: 'pierre', refined: 'bloc', refiningCity: 'Bridgewatch' },
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
  const labels = RESOURCE_LABELS[route.resource_kind] ?? RESOURCE_LABELS.wood

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
              Tier {route.tier}
              {route.enchant > 0 && (
                <span className="ml-1 rounded bg-primary-500/15 px-1.5 py-0.5 text-[10px] font-bold text-primary-300">
                  .{route.enchant}
                </span>
              )}
              {' '}— {route.quantite} {labels.refined}s
            </span>
          </div>
          <div className={cn('flex items-center gap-2 text-sm font-semibold', roiTone)}>
            <TrendIcon className="h-4 w-4" />
            <span className="inline-flex items-center gap-1">
              ROI capital <InfoTooltip>{GLOSSARY.roi_capital}</InfoTooltip>
            </span>
            {fmtPct(route.marge_pct)}
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
          <SourcingRow
            leg={route.achat_wood}
            icon={<ShoppingCart className="h-4 w-4" />}
            label={`Achat ${labels.raw}`}
          />
          {route.achat_plank && (
            <SourcingRow
              leg={route.achat_plank}
              icon={<Package className="h-4 w-4" />}
              label={`Achat ${labels.refined} T${route.achat_plank.tier}`}
            />
          )}

          <div className="rounded-lg border border-surface-border/60 bg-surface/60 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
              <Factory className="h-4 w-4 text-primary-400" />
              Raffinage — {labels.refiningCity}
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted">
              <RowKV
                label={
                  <span className="inline-flex items-center gap-1">
                    RRR effectif <InfoTooltip>{GLOSSARY.rrr_effectif}</InfoTooltip>
                  </span>
                }
                value={`${(route.raffinage.rrr_effectif * 100).toFixed(1)}%`}
              />
              <RowKV label="Cout station" value={fmtSilver(route.raffinage.cout_station)} />
              <RowKV label="Produits" value={`${route.raffinage.planks_produits} ${labels.refined}s`} />
              <RowKV
                label="Retours RRR"
                value={`${route.raffinage.wood_retour.toFixed(0)} ${labels.raw} + ${route.raffinage.plank_moins_1_retour.toFixed(0)} ${labels.refined} T-1`}
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
                <span className="inline-flex items-center gap-1">
                  Recup @ {route.recup_city}
                  <InfoTooltip>{GLOSSARY.recup_rrr}</InfoTooltip>
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted">
                <RowKV label="Valeur nette" value={<span className="text-positive num">{fmtSilver(route.recup_totale)}</span>} />
                <RowKV
                  label={`Absorption ${labels.raw}`}
                  value={`${route.recup_wood_absorbe} / ${route.recup_wood_demande}`}
                />
                {route.achat_plank && (
                  <RowKV
                    label={`Absorption ${labels.refined}s T-1`}
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
              <span className="text-ink-faint inline-flex items-center gap-1">
                Silver / focus <InfoTooltip>{GLOSSARY.silver_par_focus}</InfoTooltip> :
              </span>{' '}
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
          <div className="text-xs text-ink-faint inline-flex items-center gap-1">
            marge efficacite (V1 secondaire)
            <InfoTooltip>{GLOSSARY.marge_efficacite}</InfoTooltip> :{' '}
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

const SourcingRow: FC<SourcingRowProps> = ({ leg, icon, label }) => {
  const allocations = leg.allocations ?? []
  const isMulti = allocations.length > 1
  const avgSlippage = leg.slippage_pct ?? 0
  const legSlippageTone =
    avgSlippage >= 15 ? 'text-negative' : avgSlippage >= 8 ? 'text-caution' : 'text-ink-muted'

  return (
    <div className="rounded-lg border border-surface-border/60 bg-surface/60 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          {icon}
          <span>{label}</span>
          <span className="text-xs font-normal text-ink-muted">— {leg.quantite} unités</span>
        </div>
        <div className="flex items-center gap-2">
          {isMulti && (
            <span
              className="inline-flex items-center gap-1 rounded-md border border-primary-500/40 bg-primary-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary-300"
              title={`Split réparti sur ${allocations.length} villes pour éviter la saturation du carnet`}
            >
              {allocations.length} villes
            </span>
          )}
          <FreshnessBadge level={leg.freshness} ageHours={leg.data_age_hours} compact />
        </div>
      </div>

      {/* Allocations verticales : 1 ligne par ville visitee */}
      <ul className="space-y-1 text-xs">
        {allocations.map((alloc) => (
          <AllocationRow key={alloc.city} alloc={alloc} isMulti={isMulti} />
        ))}
      </ul>

      {/* Bandeau resume : moyenne + total */}
      {isMulti && (
        <div className="mt-2 flex items-baseline justify-between gap-3 border-t border-surface-border/60 pt-2 text-xs">
          <span className="text-ink-muted">
            moyenne <span className="num text-ink">{leg.prix_unitaire.toFixed(0)} s/u</span>
            {avgSlippage > 0.1 && (
              <>
                {' '}
                <span className={cn('num text-[10px]', legSlippageTone)}>
                  (+{avgSlippage.toFixed(1)}%)
                </span>
              </>
            )}
          </span>
          <span className="num text-sm font-semibold text-ink">{fmtSilver(leg.cout_total)}</span>
        </div>
      )}
      {!isMulti && (
        <div className="mt-1 flex items-baseline justify-end text-xs">
          <span className="num text-sm font-semibold text-ink">{fmtSilver(leg.cout_total)}</span>
        </div>
      )}
    </div>
  )
}

interface AllocationRowProps {
  alloc: import('../types/optimizer').SourcingAllocation
  isMulti: boolean
}

const AllocationRow: FC<AllocationRowProps> = ({ alloc, isMulti }) => {
  const hasInflation = alloc.slippage_pct > 0.1
  const tone =
    alloc.slippage_pct >= 15
      ? 'text-negative'
      : alloc.slippage_pct >= 8
        ? 'text-caution'
        : 'text-ink-muted'
  const tooltip = hasInflation
    ? `Prix ref AODP ${alloc.prix_ref.toFixed(0)} s → effectif ${alloc.prix_unitaire.toFixed(0)} s (+${alloc.slippage_pct.toFixed(1)}%). ` +
      `Profondeur : +${alloc.slippage_qty_pct.toFixed(1)}% · Fraîcheur : +${alloc.slippage_age_pct.toFixed(1)}%.`
    : undefined

  return (
    <li className="flex items-baseline justify-between gap-3">
      <span className="text-ink-muted">
        {isMulti && <span className="text-ink-faint">└─ </span>}
        {alloc.city} —{' '}
        <span className="num text-ink" title={tooltip}>
          {alloc.prix_unitaire.toFixed(0)} s
        </span>
        {hasInflation && (
          <>
            {' '}
            <span
              className={cn('num text-[10px] font-semibold', tone)}
              title={tooltip}
            >
              +{alloc.slippage_pct.toFixed(1)}%
            </span>
          </>
        )}{' '}
        × <span className="num text-ink">{alloc.quantite}</span>
      </span>
      <span className="num text-ink">{fmtSilver(alloc.cout_total)}</span>
    </li>
  )
}

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
  label: React.ReactNode
  value: React.ReactNode
}

const RowKV: FC<RowKVProps> = ({ label, value }) => (
  <>
    <dt className="text-ink-faint">{label}</dt>
    <dd className="text-right text-ink num">{value}</dd>
  </>
)

export default RouteCard
