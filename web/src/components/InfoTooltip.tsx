import type { FC, ReactNode } from 'react'
import { HelpCircle } from 'lucide-react'

import { cn } from '../lib/cn'

type Side = 'top' | 'bottom' | 'left' | 'right'

interface Props {
  children: ReactNode
  side?: Side
  /** Largeur max de la bulle (Tailwind width class). */
  width?: 'sm' | 'md' | 'lg'
  /** Taille de l'icone en px (tailwind h-X w-X). */
  size?: 3 | 3.5 | 4
}

const SIDE_CLASS: Record<Side, string> = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
}

const WIDTH_CLASS: Record<NonNullable<Props['width']>, string> = {
  sm: 'w-52',
  md: 'w-64',
  lg: 'w-80',
}

// Pop-over pedagogique declenche par hover ou focus clavier. Volontairement
// CSS-only (pas de portal ni de state) : les info-bulles restent legeres et
// n'impactent pas le poids du bundle.
const InfoTooltip: FC<Props> = ({ children, side = 'top', width = 'md', size = 3.5 }) => {
  const iconSize = size === 3 ? 'h-3 w-3' : size === 4 ? 'h-4 w-4' : 'h-3.5 w-3.5'

  return (
    <span className="group relative inline-flex items-center align-middle">
      <button
        type="button"
        aria-label="Plus d'informations"
        className={cn(
          iconSize,
          'inline-flex items-center justify-center rounded-full text-ink-faint outline-none transition',
          'hover:text-primary-400 focus-visible:text-primary-400',
        )}
        // Le clic n'a rien a faire : le hover/focus suffit. On evite juste que
        // le bouton submit un form parent par accident.
        onClick={(e) => e.preventDefault()}
      >
        <HelpCircle className={iconSize} />
      </button>
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-50 hidden rounded-md border border-surface-border',
          'bg-surface-raised px-3 py-2 text-xs font-normal normal-case leading-relaxed text-ink shadow-lg',
          'group-hover:block group-focus-within:block',
          SIDE_CLASS[side],
          WIDTH_CLASS[width],
        )}
      >
        {children}
      </span>
    </span>
  )
}

export default InfoTooltip
