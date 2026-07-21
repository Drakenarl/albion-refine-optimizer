import type { FC } from 'react'
import { motion } from 'framer-motion'
import { Info, Lightbulb } from 'lucide-react'

import { cn } from '../lib/cn'
import { fmtPct } from '../lib/format'
import { fadeUp, staggerContainer } from '../lib/motion'
import type { DiscardedRoute } from '../types/optimizer'

interface Props {
  alternatives: DiscardedRoute[]
  seuil: number
}

const AlternativesList: FC<Props> = ({ alternatives, seuil }) => {
  if (alternatives.length === 0) {
    return (
      <div className="rounded-xl border border-surface-border bg-surface-raised p-6 text-center text-sm text-ink-muted shadow-card">
        Aucun candidat exploitable trouve — donnees AODP absentes ou trop vieilles pour ce tier.
      </div>
    )
  }

  const suggestions = alternatives[0]?.suggestions ?? []

  return (
    <motion.section
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="space-y-4"
    >
      <div className="flex items-start gap-3 rounded-lg border border-caution/40 bg-caution/10 px-4 py-3">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-caution" />
        <p className="text-sm text-ink">
          Aucune route ne passe le seuil de{' '}
          <span className="num font-semibold">{seuil.toFixed(0)}%</span> de ROI capital.
          Voici les {alternatives.length} meilleures alternatives — toutes deficitaires
          ou sous le seuil.
        </p>
      </div>

      <div className="grid gap-3">
        {alternatives.map((alt, idx) => {
          const roi = alt.marge_pct ?? 0
          const negative = roi < 0
          return (
            <motion.div
              key={`${alt.description}-${idx}`}
              variants={fadeUp}
              className={cn(
                'rounded-lg border border-surface-border bg-surface-raised/70 p-4 opacity-90',
                negative && 'border-negative/30',
              )}
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-surface px-1.5 py-0.5 text-xs font-bold text-ink-muted">
                    #{idx + 1}
                  </span>
                  <p className="text-sm text-ink">{alt.description}</p>
                </div>
                <div
                  className={cn(
                    'shrink-0 text-sm font-semibold num',
                    negative ? 'text-negative' : 'text-caution',
                  )}
                >
                  {fmtPct(alt.marge_pct)}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-xs text-ink-muted sm:grid-cols-3">
                <MetricLabelValue label="ROI (instant sell)" value={fmtPct(alt.marge_pct)} />
                <MetricLabelValue label="ROI (sell order)" value={fmtPct(alt.marge_pct_b)} />
                <MetricLabelValue
                  label="Marge efficacite (V1)"
                  value={fmtPct(alt.marge_efficacite_pct)}
                  dim
                />
              </div>
            </motion.div>
          )
        })}
      </div>

      {suggestions.length > 0 && (
        <motion.div
          variants={fadeUp}
          className="rounded-lg border border-surface-border bg-surface-raised/70 p-4"
        >
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
            <Lightbulb className="h-4 w-4 text-primary-400" />
            Suggestions
          </div>
          <ul className="space-y-1 text-sm text-ink-muted">
            {suggestions.map((s) => (
              <li key={s} className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ink-faint" />
                {s}
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </motion.section>
  )
}

interface MetricLVProps {
  label: string
  value: string
  dim?: boolean
}

const MetricLabelValue: FC<MetricLVProps> = ({ label, value, dim }) => (
  <div className={cn('flex flex-col', dim && 'opacity-70')}>
    <span className="text-[10px] uppercase tracking-wider text-ink-faint">{label}</span>
    <span className="num text-ink">{value}</span>
  </div>
)

export default AlternativesList
