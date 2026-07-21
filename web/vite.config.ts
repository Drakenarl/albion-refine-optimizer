import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api → backend FastAPI en dev. En prod on passera par VITE_API_URL
// et un client axios dédié qui préfixe les URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
