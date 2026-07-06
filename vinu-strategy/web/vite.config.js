import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: {
      '/strategies': 'http://localhost:8084',
      '/weights': 'http://localhost:8084',
      '/runs': 'http://localhost:8084',
      '/settings': 'http://localhost:8084',
    },
  },
  build: {
    outDir: '../vinu_strategy/server/static',
    emptyOutDir: true,
  },
})
