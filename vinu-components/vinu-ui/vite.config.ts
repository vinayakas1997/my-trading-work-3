import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Isolated frontend: own port 5173. Dev-only proxy to the FastAPI services
// (all on 127.0.0.1 per vinu-components/docker-compose.yml). No backend edits.
// Each service mounts its routes under its own prefix (route_prefix=...),
// except screener + quant-core whose route paths are already full.
// So /api/<name>/rest → /<prefix>/rest (or /rest for screener/quant).
const proxy: Record<string, { target: string; prefix: string }> = {
  '/api/stock': { target: 'http://127.0.0.1:8081', prefix: '/stock' },
  '/api/analysis': { target: 'http://127.0.0.1:8083', prefix: '/analysis' },
  '/api/research': { target: 'http://127.0.0.1:8087', prefix: '/research' },
  '/api/live': { target: 'http://127.0.0.1:8091', prefix: '/live' },
  '/api/portfolio': { target: 'http://127.0.0.1:8090', prefix: '/portfolio' },
  '/api/screener': { target: 'http://127.0.0.1:8095', prefix: '/screener' },
  '/api/agent': { target: 'http://127.0.0.1:8086', prefix: '/agent' },
  '/api/news': { target: 'http://127.0.0.1:8080', prefix: '/news' },
  '/api/quant': { target: 'http://127.0.0.1:8084', prefix: '' },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      Object.entries(proxy).map(([apiPrefix, { target, prefix }]) => [
        apiPrefix,
        { target, changeOrigin: true, rewrite: (p: string) => prefix + p.slice(apiPrefix.length) },
      ]),
    ),
  },
  preview: { port: 5174, strictPort: true },
})
