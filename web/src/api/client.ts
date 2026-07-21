import axios from 'axios'

// Client axios central. En dev, l'URL de base est vide : Vite proxy /api → :8000.
// En prod on injecte VITE_API_URL au build (ex. https://albion-api.railway.app).
const baseURL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})
