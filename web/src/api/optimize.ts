import { apiClient } from './client'
import type {
  ConfigResponse,
  OptimizationResult,
  OptimizeRequest,
} from '../types/optimizer'

// Récupère les constantes UI-friendly (tiers, villes, défauts).
export async function fetchConfig(): Promise<ConfigResponse> {
  const { data } = await apiClient.get<ConfigResponse>('/api/config')
  return data
}

// Lance une optimisation. Le backend fait les appels AODP et applique la
// logique métier ; on ne fait ici que passer le JSON.
export async function postOptimize(
  payload: OptimizeRequest,
): Promise<OptimizationResult> {
  const { data } = await apiClient.post<OptimizationResult>('/api/optimize', payload)
  return data
}
