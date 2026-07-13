import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8080',
      '/latest': 'http://localhost:8080',
      '/ticker': 'http://localhost:8080',
      '/watchlist': 'http://localhost:8080',
      '/search': 'http://localhost:8080',
      '/high-impact': 'http://localhost:8080',
      '/threads': 'http://localhost:8080',
      '/stats': 'http://localhost:8080',
      '/articles': 'http://localhost:8080',
      '/news': 'http://localhost:8080',
      '/settings': 'http://localhost:8080',
      '/feeds': 'http://localhost:8080',
      '/providers': 'http://localhost:8080',
      '/poll': 'http://localhost:8080',
      '/ingest': 'http://localhost:8080',
      '/backfill': 'http://localhost:8080',
    }
  },
  build: {
    outDir: '../vinu_news/server/static',
    emptyOutDir: true,
  },
})
