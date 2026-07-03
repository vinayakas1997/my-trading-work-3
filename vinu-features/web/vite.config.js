import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8082',
      '/requests': 'http://localhost:8082',
      '/presets': 'http://localhost:8082',
      '/features': 'http://localhost:8082',
    }
  },
  build: {
    outDir: '../vinu_features/server/static',
    emptyOutDir: true,
  },
})
