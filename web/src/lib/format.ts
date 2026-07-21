// Formatteurs partagés. Cohérents avec la CLI (séparateur espace, notation FR).

export function fmtSilver(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value).toLocaleString('fr-FR').replace(/ /g, ' ')} s`
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

export function fmtAge(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return 'n/a'
  if (hours < 1) return `${Math.round(hours * 60)} min`
  return `${hours.toFixed(1)}h`
}
