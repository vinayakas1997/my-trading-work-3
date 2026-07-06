import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8083',
      '/correlation': 'http://localhost:8083',
      '/impact': 'http://localhost:8083',
      '/events': 'http://localhost:8083',
      '/drawdown': 'http://localhost:8083',
      '/baseline': 'http://localhost:8083',
      '/settings': 'http://localhost:8083',
    }
  },
  build: {
    outDir: '../vinu_correlation/server/static',
    emptyOutDir: true,
  },
})
