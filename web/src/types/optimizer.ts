// Types miroirs des modèles Pydantic exposés par POST /api/optimize.
// À maintenir en cohérence manuelle avec src/albion_refine/models.py.
// Un futur build step pourrait générer ces types depuis le schema OpenAPI
// (fastapi expose /openapi.json), c'est le bon moment pour ça côté V2.

export type QuantityMode = 'capital' | 'fixed' | 'focus'
export type SellStrategy = 'instant_sell' | 'sell_order'
export type FreshnessLevel = 'fresh' | 'warning' | 'critical' | 'unknown'
export type SourcingMode = 'market' | 'production'
export type ResourceKind = 'wood' | 'hide' | 'fiber' | 'ore' | 'stone'

export interface ResourceOption {
  kind: ResourceKind
  display_raw: string
  display_refined: string
  refining_city: string
}

export type WarningCode =
  | 'ROUTE_ZONE_ROUGE'
  | 'PROFONDEUR_INCERTAINE'
  | 'DATA_JAUNE'
  | 'RECUP_PARTIELLE'
  | 'RECUP_SATURATION'
  | 'BUY_SLIPPAGE_ELEVE'
  | 'MARCHE_INACTIF'

export interface SourcingAllocation {
  city: string
  quantite: number
  prix_ref: number
  prix_unitaire: number
  cout_total: number
  slippage_pct: number
  slippage_qty_pct: number
  slippage_age_pct: number
  data_age_hours: number | null
  freshness: FreshnessLevel
}

export interface SourcingLeg {
  kind: 'wood' | 'plank'
  item_id: string
  tier: number
  city: string
  prix_unitaire: number
  prix_ref: number | null
  slippage_pct: number | null
  slippage_qty_pct: number | null
  slippage_age_pct: number | null
  quantite: number
  cout_total: number
  data_age_hours: number | null
  freshness: FreshnessLevel
  source: SourcingMode
  allocations: SourcingAllocation[]
}

export interface RefiningResult {
  planks_produits: number
  wood_utilise: number
  plank_moins_1_utilise: number
  wood_retour: number
  plank_moins_1_retour: number
  cout_station: number
  rrr_effectif: number
  focus_utilise: number
}

export interface SalesScenario {
  strategy: SellStrategy
  city: string
  planks: number
  prix_unitaire_ref: number
  revenu_brut: number
  revenu_net: number
  freshness_factor: number
  revenu_net_pondere: number
  fill_proba: number
  expected_revenu: number
  stack_suffisant: boolean
  data_age_hours: number | null
  certitude: string
  marge_pct: number | null
  marge_efficacite_pct: number | null
  benefice: number | null
  gain_marginal_vs_a: number | null
  gain_marginal_pct: number | null
}

export interface VenteBlock {
  ville: string
  scenario_a_instant_sell: SalesScenario | null
  scenario_b_sell_order: SalesScenario | null
  recommandation: string
}

export interface Route {
  rank: number
  tier: number
  resource_kind: ResourceKind
  enchant: number
  quantite: number
  achat_wood: SourcingLeg
  achat_plank: SourcingLeg | null
  raffinage: RefiningResult
  vente: VenteBlock
  recup_wood: number
  recup_plank: number
  recup_wood_absorbe: number
  recup_wood_demande: number
  recup_plank_absorbe: number
  recup_plank_demande: number
  recup_totale: number
  recup_city: string
  cout_total: number
  cout_net: number
  revenu_effectif: number
  benefice: number
  marge_pct: number
  marge_efficacite_pct: number
  benefice_b: number | null
  marge_pct_b: number | null
  marge_efficacite_pct_b: number | null
  silver_par_focus: number | null
  warnings: WarningCode[]
}

export interface RefreshChecklistItem {
  city: string
  item_id: string
  age_hours: number | null
  freshness: FreshnessLevel
  role: string
}

export interface DiscardedRoute {
  description: string
  marge_pct: number | null
  marge_pct_b: number | null
  marge_efficacite_pct: number | null
  raison: string
  suggestions: string[]
}

export interface RunMetadata {
  timestamp: string
  tier: number
  mode: QuantityMode
  params: Record<string, unknown>
}

export interface OptimizationResult {
  run_metadata: RunMetadata
  routes: Route[]
  refresh_checklist: RefreshChecklistItem[]
  discarded_best: DiscardedRoute | null
  discarded_top: DiscardedRoute[]
}

export interface OptimizeRequest {
  tier: number
  station_rate: number
  mode: QuantityMode
  capital?: number | null
  quantite?: number | null
  focus_available?: number | null
  focus?: boolean
  daily_bonus_pct?: number
  cost_per_focus?: number
  seuil_marge_min_pct?: number
  excluded_buy_cities?: string[]
  excluded_sell_cities?: string[]
  resource?: ResourceKind
  enchant?: number
  top_n?: number
  server?: string
  use_cache?: boolean
}

export interface ConfigResponse {
  tiers: number[]
  cities: string[]
  default_excluded: string[]
  seuil_marge_default: number
  servers: string[]
  resources: ResourceOption[]
  enchants: number[]
}
