import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8081',
      '/catalog': 'http://localhost:8081',
      '/candles': 'http://localhost:8081',
      '/watchlist': 'http://localhost:8081',
      '/settings': 'http://localhost:8081',
      '/backfill': 'http://localhost:8081',
      '/ingest': 'http://localhost:8081',
    }
  },
  build: {
    outDir: '../vinu_stock/server/static',
    emptyOutDir: true,
  },
})
