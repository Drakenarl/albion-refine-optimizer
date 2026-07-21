import { useState, type FC } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronUp, ClipboardList, MessagesSquare } from 'lucide-react'

import FreshnessBadge from './FreshnessBadge'
import { cn } from '../lib/cn'
import type { RefreshChecklistItem } from '../types/optimizer'

interface Props {
  checklist: RefreshChecklistItem[]
}

const CONSEILS: readonly string[] = [
  'Ouvre en jeu les pages listees ci-dessus pour rafraichir la data AODP.',
  "Relance l'outil 30-60 secondes apres pour recuperer les vrais prix.",
  'Confirme le top buy order en jeu avant de committer sur instant sell.',
  'Ne place jamais un sell order sans verifier la profondeur du carnet.',
]

const ChecklistPanel: FC<Props> = ({ checklist }) => {
  const [open, setOpen] = useState(true)

  if (checklist.length === 0) return null

  return (
    <aside className="rounded-xl border border-surface-border bg-surface-raised shadow-card">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ClipboardList className="h-4 w-4 text-primary-400" />
          Check-list fraicheur ({checklist.length})
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-ink-muted" />
        ) : (
          <ChevronDown className="h-4 w-4 text-ink-muted" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-surface-border/60 px-4 py-3">
              <p className="mb-3 text-xs text-ink-faint">
                Pages marche a ouvrir en jeu pour ameliorer la fraicheur des prix.
              </p>
              <ul className="space-y-2">
                {checklist.map((item) => (
                  <li
                    key={`${item.city}-${item.item_id}`}
                    className="flex flex-col gap-1 rounded-md border border-surface-border/60 bg-surface/40 p-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm text-ink">
                        <span className="text-ink-faint">{item.city}</span> — {item.item_id}
                      </span>
                      <FreshnessBadge
                        level={item.freshness}
                        ageHours={item.age_hours}
                        compact
                      />
                    </div>
                    {item.role && (
                      <span className="text-[11px] text-ink-muted">{item.role}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className={cn('border-t border-surface-border/60 px-4 py-3')}>
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <MessagesSquare className="h-4 w-4 text-primary-400" />
                Conseils trading
              </div>
              <ul className="space-y-1.5 text-xs text-ink-muted">
                {CONSEILS.map((tip) => (
                  <li key={tip} className="flex items-start gap-2">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ink-faint" />
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </aside>
  )
}

export default ChecklistPanel
