import type { Config } from 'tailwindcss'

// Palette sobre data-dashboard : tons slate/bleu pour la structure, accents
// franc pour les états business (positif/négatif/attention/fraîcheur AODP).
// À étendre — ne jamais remplacer — pour rester compatible avec les classes
// Tailwind standard.
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Fond et surfaces
        surface: {
          DEFAULT: '#0f172a', // slate-900 : fond app
          raised: '#1e293b',  // slate-800 : cards
          sunken: '#020617',  // slate-950 : creux (tableaux zebrés)
          border: '#334155',  // slate-700 : bordures discrètes
        },
        // Texte
        ink: {
          DEFAULT: '#f1f5f9', // slate-100 : texte primaire
          muted: '#94a3b8',   // slate-400 : labels, hints
          faint: '#64748b',   // slate-500 : texte secondaire dim
        },
        // Accents primaires (bleu data-dashboard, brand-neutral)
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // États business : marges, warnings, fraîcheur
        positive: '#10b981', // emerald-500 : ROI positive
        negative: '#f43f5e', // rose-500 : ROI négative
        caution: '#f59e0b',  // amber-500 : warning, données jaunes
        critical: '#dc2626', // red-600 : zone rouge, données périmées
        fresh: '#22c55e',    // green-500 : données fraîches ✓
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(0 0 0 / 0.4), 0 4px 12px -4px rgb(0 0 0 / 0.3)',
      },
    },
  },
  plugins: [],
}

export default config
