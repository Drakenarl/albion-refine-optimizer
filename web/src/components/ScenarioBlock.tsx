import type { FC } from 'react'
import { Clock, Zap } from 'lucide-react'

import FreshnessBadge from './FreshnessBadge'
import InfoTooltip from './InfoTooltip'
import { cn } from '../lib/cn'
import { fmtPct, fmtSilver } from '../lib/format'
import { GLOSSARY } from '../lib/glossary'
import type { FreshnessLevel, SalesScenario } from '../types/optimizer'

interface Props {
  scenario: SalesScenario | null
  /** ``a`` : instant sell (safe). ``b`` : sell order (attente). */
  slot: 'a' | 'b'
}

function classifyAge(ageHours: number | null | undefined): FreshnessLevel {
  if (ageHours === null || ageHours === undefined) return 'unknown'
  if (ageHours >= 6) return 'critical'
  if (ageHours >= 3) return 'warning'
  return 'fresh'
}

const ScenarioBlock: FC<Props> = ({ scenario, slot }) => {
  const isInstant = slot === 'a'
  const title = isInstant ? 'Instant sell (safe)' : 'Sell order (attente)'
  const icon = isInstant ? (
    <Zap className="h-4 w-4 text-fresh" />
  ) : (
    <Clock className="h-4 w-4 text-primary-400" />
  )

  if (scenario === null || !scenario.stack_suffisant) {
    return (
      <div className="rounded-lg border border-surface-border bg-surface/60 p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-muted">
          {icon}
          {title}
        </div>
        <p className="text-xs text-ink-faint">
          Indisponible — {isInstant ? 'aucun buy order exploitable' : 'aucun sell order de reference'}.
        </p>
      </div>
    )
  }

  const roiColor =
    scenario.marge_pct !== null && scenario.marge_pct >= 0 ? 'text-positive' : 'text-negative'
  const dim = !isInstant && scenario.fill_proba < 0.4

  return (
    <div
      className={cn(
        'rounded-lg border p-3 transition',
        isInstant
          ? 'border-fresh/30 bg-fresh/5'
          : 'border-primary-500/30 bg-primary-500/5',
        dim && 'opacity-60',
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {icon}
          <span className="inline-flex items-center gap-1">
            {title}
            <InfoTooltip>
              {isInstant ? GLOSSARY.instant_sell : GLOSSARY.sell_order}
            </InfoTooltip>
          </span>
        </div>
        <FreshnessBadge
          level={classifyAge(scenario.data_age_hours)}
          ageHours={scenario.data_age_hours}
          compact
        />
      </div>

      <dl className="space-y-1.5 text-xs text-ink-muted">
        <Row
          label={isInstant ? 'Top buy' : `Undercut ${scenario.prix_unitaire_ref.toFixed(0)} s`}
          value={
            isInstant ? (
              `${scenario.prix_unitaire_ref.toFixed(0)} s x ${scenario.planks}`
            ) : (
              <span className="inline-flex items-center gap-1">
                fill proba {(scenario.fill_proba * 100).toFixed(0)}%
                <InfoTooltip size={3}>{GLOSSARY.fill_proba}</InfoTooltip>
              </span>
            )
          }
        />
        <Row
          label={isInstant ? 'Revenu net' : 'Revenu si rempli'}
          value={fmtSilver(scenario.revenu_net)}
        />
        <Row
          label={
            <span className="inline-flex items-center gap-1">
              Confiance <InfoTooltip size={3}>{GLOSSARY.freshness_factor}</InfoTooltip>
            </span>
          }
          value={`x${scenario.freshness_factor.toFixed(2)}`}
          dim
        />
        {!isInstant && (
          <Row
            label="Esperance ponderee"
            value={fmtSilver(scenario.expected_revenu)}
          />
        )}
        {scenario.marge_pct !== null && (
          <Row
            label={isInstant ? 'ROI capital' : 'ROI esperee'}
            value={
              <span className={cn('num font-semibold', roiColor)}>
                {fmtPct(scenario.marge_pct)}
              </span>
            }
            emphasis
          />
        )}
        {scenario.marge_efficacite_pct !== null && (
          <Row
            label="Marge efficacite"
            value={fmtPct(scenario.marge_efficacite_pct)}
            dim
          />
        )}
        {!isInstant && scenario.gain_marginal_vs_a !== null && (
          <Row
            label="Gain vs instant"
            value={
              <span
                className={cn(
                  scenario.gain_marginal_vs_a >= 0 ? 'text-positive' : 'text-negative',
                )}
              >
                {fmtSilver(scenario.gain_marginal_vs_a)}
                {scenario.gain_marginal_pct !== null && (
                  <span className="ml-1 text-ink-faint">
                    ({fmtPct(scenario.gain_marginal_pct)})
                  </span>
                )}
              </span>
            }
          />
        )}
      </dl>
    </div>
  )
}

interface RowProps {
  label: React.ReactNode
  value: React.ReactNode
  emphasis?: boolean
  dim?: boolean
}

const Row: FC<RowProps> = ({ label, value, emphasis, dim }) => (
  <div
    className={cn(
      'flex items-baseline justify-between gap-3',
      emphasis && 'pt-1',
      dim && 'text-ink-faint',
    )}
  >
    <dt className="shrink-0 text-[11px] uppercase tracking-wide">{label}</dt>
    <dd className={cn('num text-right text-xs', emphasis && 'text-sm text-ink')}>
      {value}
    </dd>
  </div>
)

export default ScenarioBlock
