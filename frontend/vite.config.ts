import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // GitHub Pages serves the app from /<repo-name>/.
  base: process.env.VITE_BASE_PATH ?? '/',
  server: {
    // Local Django dev server; override with API_PROXY.
    // In production nginx proxies /api instead (frontend/nginx.conf).
    proxy: { '/api': process.env.API_PROXY ?? 'http://127.0.0.1:3000' },
  },
})
