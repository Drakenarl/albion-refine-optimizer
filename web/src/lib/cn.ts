import clsx, { type ClassValue } from 'clsx'

// Wrapper trivial autour de clsx. Évite d'importer clsx partout et documente
// l'intention (classes conditionnelles Tailwind).
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}
