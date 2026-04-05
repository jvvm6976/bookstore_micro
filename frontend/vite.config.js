import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all network interfaces for Docker mapping
    port: 5173,
    watch: {
      usePolling: true, // Needed for hot-reloading on Windows via Docker volume mapping
    }
  }
})
