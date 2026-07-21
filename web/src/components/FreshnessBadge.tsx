import { Check, AlertTriangle, X, HelpCircle } from 'lucide-react'
import type { FC, ReactElement } from 'react'

import { cn } from '../lib/cn'
import { fmtAge } from '../lib/format'
import type { FreshnessLevel } from '../types/optimizer'

interface Props {
  level: FreshnessLevel
  ageHours: number | null | undefined
  /** Affichage inline compact (icone + age) ou avec libelle. */
  compact?: boolean
}

const CONFIG: Record<
  FreshnessLevel,
  { icon: ReactElement; label: string; classes: string }
> = {
  fresh: {
    icon: <Check className="h-3 w-3" />,
    label: 'frais',
    classes: 'text-fresh bg-fresh/10 border-fresh/30',
  },
  warning: {
    icon: <AlertTriangle className="h-3 w-3" />,
    label: 'attention',
    classes: 'text-caution bg-caution/10 border-caution/30',
  },
  critical: {
    icon: <X className="h-3 w-3" />,
    label: 'perime',
    classes: 'text-critical bg-critical/10 border-critical/30',
  },
  unknown: {
    icon: <HelpCircle className="h-3 w-3" />,
    label: '?',
    classes: 'text-ink-faint bg-surface border-surface-border',
  },
}

const FreshnessBadge: FC<Props> = ({ level, ageHours, compact = false }) => {
  const config = CONFIG[level]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs num',
        config.classes,
      )}
      title={`Donnee ${config.label} — ${fmtAge(ageHours)}`}
    >
      {config.icon}
      <span>{fmtAge(ageHours)}</span>
      {!compact && <span className="hidden sm:inline">{config.label}</span>}
    </span>
  )
}

export default FreshnessBadge
