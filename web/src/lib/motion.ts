import type { Variants } from 'framer-motion'

// Variants partagées. Respect systématique de prefers-reduced-motion : Framer
// le fait nativement quand on le déclare via `useReducedMotion`, mais on garde
// des durées courtes pour rester agréable même sans la préférence.

// Container à décaler les enfants (cards en entrée en cascade).
export const staggerContainer: Variants = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.05,
    },
  },
}

// Item enfant : léger fade + translation verticale, easeOut, 0.4s.
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: 'easeOut' },
  },
}

// Apparition d'un bloc secondaire (alternatives, checklist).
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.3, ease: 'easeOut' } },
}
