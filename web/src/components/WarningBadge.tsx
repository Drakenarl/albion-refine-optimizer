import { AlertOctagon, AlertTriangle, PackageMinus, Waves } from 'lucide-react'
import type { FC, ReactElement } from 'react'

import { cn } from '../lib/cn'
import type { WarningCode } from '../types/optimizer'

interface Props {
  code: WarningCode
  /** Contexte optionnel (chiffres precis a affiches en tooltip). */
  detail?: string
}

const CONFIG: Record<
  WarningCode,
  { icon: ReactElement; label: string; description: string; classes: string }
> = {
  ROUTE_ZONE_ROUGE: {
    icon: <AlertOctagon className="h-3.5 w-3.5" />,
    label: 'Zone rouge',
    description: 'La route traverse Caerleon. Risque PvP.',
    classes: 'text-critical bg-critical/10 border-critical/40',
  },
  PROFONDEUR_INCERTAINE: {
    icon: <Waves className="h-3.5 w-3.5" />,
    label: 'Profondeur incertaine',
    description: 'Le volume echange 24h est inferieur a ta quantite.',
    classes: 'text-caution bg-caution/10 border-caution/40',
  },
  DATA_JAUNE: {
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
    label: 'Donnees jaunes',
    description: 'Au moins une leg utilise une donnee entre 3h et 6h.',
    classes: 'text-caution bg-caution/10 border-caution/40',
  },
  RECUP_PARTIELLE: {
    icon: <PackageMinus className="h-3.5 w-3.5" />,
    label: 'Recup partielle',
    description: 'Le carnet acheteur n\'absorbe pas toute la recup RRR.',
    classes: 'text-caution bg-caution/10 border-caution/40',
  },
  RECUP_SATURATION: {
    icon: <Waves className="h-3.5 w-3.5" />,
    label: 'Risque saturation',
    description: 'La recup a ecouler depasse 50% du volume 24h. Risque d\'ecraser le carnet.',
    classes: 'text-caution bg-caution/10 border-caution/40',
  },
  BUY_SLIPPAGE_ELEVE: {
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
    label: 'Prix d\'achat incertain',
    description:
      'Slippage combine (profondeur + fraicheur) > 8% : le sell_price_min AODP est probablement loin de la realite. Verifie le carnet en jeu avant de committer.',
    classes: 'text-caution bg-caution/10 border-caution/40',
  },
}

const WarningBadge: FC<Props> = ({ code, detail }) => {
  const config = CONFIG[code]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium',
        config.classes,
      )}
      title={detail ?? config.description}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  )
}

export default WarningBadge
