import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Must match the origin allowed by the backend's CORSMiddleware
    // (settings.CORS_ORIGINS -> "http://localhost:5173").
    host: 'localhost',
    port: 5173,
    // Fail loudly instead of silently falling back to 5174, which the
    // backend would reject as an unlisted CORS origin.
    strictPort: true,
  },
})
