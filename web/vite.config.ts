import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Console talks only to the local FastAPI (architecture.md §4.6, threats T13/T15).
export default defineConfig({
  plugins: [react()],
  envPrefix: 'VITE_',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
