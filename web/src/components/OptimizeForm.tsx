import { useState, type FC, type FormEvent } from 'react'

import InfoTooltip from './InfoTooltip'
import { cn } from '../lib/cn'
import { GLOSSARY } from '../lib/glossary'
import type {
  ConfigResponse,
  OptimizeRequest,
  QuantityMode,
  RecupMode,
  ResourceKind,
} from '../types/optimizer'

interface Props {
  config: ConfigResponse
  loading: boolean
  onSubmit: (payload: OptimizeRequest) => void
}

interface FormState {
  tier: number
  mode: QuantityMode
  capital: string
  quantite: string
  focusAvailable: string
  focus: boolean
  stationRate: string
  seuilMarge: string
  recupMode: RecupMode
  server: string
  resource: ResourceKind
  enchant: number
}

const OptimizeForm: FC<Props> = ({ config, loading, onSubmit }) => {
  const [state, setState] = useState<FormState>({
    tier: 7,
    mode: 'capital',
    capital: '3000000',
    quantite: '',
    focusAvailable: '',
    focus: true,
    stationRate: '50',
    seuilMarge: String(config.seuil_marge_default),
    recupMode: 'with-planks',
    server: 'europe',
    resource: 'wood',
    enchant: 0,
  })

  const currentResource =
    config.resources.find((r) => r.kind === state.resource) ?? config.resources[0]

  const patch = <K extends keyof FormState>(key: K, value: FormState[K]): void => {
    setState((prev) => ({ ...prev, [key]: value }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault()
    const payload: OptimizeRequest = {
      tier: state.tier,
      mode: state.mode,
      station_rate: Number(state.stationRate),
      focus: state.focus,
      seuil_marge_min_pct: Number(state.seuilMarge),
      recup_mode: state.recupMode,
      server: state.server,
      resource: state.resource,
      enchant: state.enchant,
    }
    if (state.mode === 'capital') payload.capital = Number(state.capital)
    if (state.mode === 'fixed') payload.quantite = Number(state.quantite)
    if (state.mode === 'focus') payload.focus_available = Number(state.focusAvailable)
    onSubmit(payload)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-surface-raised border border-surface-border p-6 shadow-card"
    >
      <div className="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2 lg:grid-cols-3">
        <Field
          label="Ressource"
          hint={
            currentResource
              ? `Raffinage a ${currentResource.refining_city}`
              : undefined
          }
        >
          <select
            value={state.resource}
            onChange={(e) => patch('resource', e.target.value as ResourceKind)}
            className={selectClass}
          >
            {config.resources.map((r) => (
              <option key={r.kind} value={r.kind}>
                {capitalize(r.display_raw)} → {r.display_refined}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label={
            <span className="inline-flex items-center gap-1">
              Enchantement
              <InfoTooltip>{GLOSSARY.enchant}</InfoTooltip>
            </span>
          }
          hint={state.enchant === 0 ? undefined : 'Marché moins liquide, marges souvent meilleures'}
        >
          <select
            value={state.enchant}
            onChange={(e) => patch('enchant', Number(e.target.value))}
            className={selectClass}
          >
            {(config.enchants ?? [0, 1, 2, 3, 4]).map((n) => (
              <option key={n} value={n}>
                {n === 0 ? '.0 (base)' : `.${n}`}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Tier">
          <select
            value={state.tier}
            onChange={(e) => patch('tier', Number(e.target.value))}
            className={selectClass}
          >
            {config.tiers.map((t) => (
              <option key={t} value={t}>
                T{t}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Mode de dimensionnement">
          <select
            value={state.mode}
            onChange={(e) => patch('mode', e.target.value as QuantityMode)}
            className={selectClass}
          >
            <option value="capital">Capital (silver disponible)</option>
            <option value="fixed">Quantité fixe</option>
            <option value="focus">Focus (budget focus)</option>
          </select>
        </Field>

        <Field
          label={
            <span className="inline-flex items-center gap-1">
              Station rate (silver / 100 nutrition)
              <InfoTooltip>{GLOSSARY.station_rate}</InfoTooltip>
            </span>
          }
        >
          <input
            type="number"
            value={state.stationRate}
            onChange={(e) => patch('stationRate', e.target.value)}
            className={inputClass}
            min={1}
            required
          />
        </Field>

        {state.mode === 'capital' && (
          <Field label="Capital disponible (silver)">
            <input
              type="number"
              value={state.capital}
              onChange={(e) => patch('capital', e.target.value)}
              className={inputClass}
              min={1}
              required
            />
          </Field>
        )}
        {state.mode === 'fixed' && (
          <Field label={`Quantité de ${currentResource?.display_raw ?? 'brut'} brut`}>
            <input
              type="number"
              value={state.quantite}
              onChange={(e) => patch('quantite', e.target.value)}
              className={inputClass}
              min={1}
              required
            />
          </Field>
        )}
        {state.mode === 'focus' && (
          <Field label="Focus disponible">
            <input
              type="number"
              value={state.focusAvailable}
              onChange={(e) => patch('focusAvailable', e.target.value)}
              className={inputClass}
              min={1}
              required
            />
          </Field>
        )}

        <Field
          label={
            <span className="inline-flex items-center gap-1">
              Seuil ROI min (%)
              <InfoTooltip>{GLOSSARY.seuil_roi}</InfoTooltip>
            </span>
          }
          hint="0 = toute route rentable retenue"
        >
          <input
            type="number"
            value={state.seuilMarge}
            onChange={(e) => patch('seuilMarge', e.target.value)}
            className={inputClass}
            step={1}
          />
        </Field>

        <Field
          label={
            <span className="inline-flex items-center gap-1">
              Mode récup RRR
              <InfoTooltip width="lg">{GLOSSARY.mode_recup}</InfoTooltip>
            </span>
          }
        >
          <select
            value={state.recupMode}
            onChange={(e) => patch('recupMode', e.target.value as RecupMode)}
            className={selectClass}
          >
            <option value="with-planks">with-planks (recommandé)</option>
            <option value="local">
              local (vente forcée à {currentResource?.refining_city ?? 'la ville de raffinage'})
            </option>
          </select>
        </Field>

        <Field label="Serveur AODP">
          <select
            value={state.server}
            onChange={(e) => patch('server', e.target.value)}
            className={selectClass}
          >
            {config.servers.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Focus actif">
          <label className="flex h-10 items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={state.focus}
              onChange={(e) => patch('focus', e.target.checked)}
              className="h-4 w-4 rounded border-surface-border bg-surface accent-primary-500"
              disabled={state.mode === 'focus'}
            />
            <span>{state.mode === 'focus' ? 'toujours actif en mode focus' : '+59% RRR'}</span>
          </label>
        </Field>
      </div>

      <div className="mt-6 flex items-center justify-end gap-3">
        <button
          type="submit"
          disabled={loading}
          className={cn(
            'rounded-lg bg-primary-500 px-5 py-2.5 text-sm font-semibold text-white',
            'transition hover:bg-primary-400 active:bg-primary-600',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {loading ? 'Analyse en cours…' : 'Analyser'}
        </button>
      </div>
    </form>
  )
}

interface FieldProps {
  label: React.ReactNode
  hint?: string
  children: React.ReactNode
}

const Field: FC<FieldProps> = ({ label, hint, children }) => (
  <label className="flex flex-col gap-1.5">
    <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</span>
    {children}
    {hint && <span className="text-xs text-ink-faint">{hint}</span>}
  </label>
)

const inputClass =
  'h-10 rounded-lg border border-surface-border bg-surface px-3 text-sm text-ink placeholder:text-ink-faint transition hover:border-slate-500'
const selectClass = inputClass

function capitalize(s: string): string {
  return s.length === 0 ? s : s.charAt(0).toUpperCase() + s.slice(1)
}

export default OptimizeForm
