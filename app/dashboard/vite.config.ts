import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

const srcDir = fileURLToPath(new URL('./src', import.meta.url))

/** Dev proxy target for ShieldAI API. Default 8888 — Windows often blocks 8010 (WinError 10013). */
const DEFAULT_SHIELD_API = 'http://127.0.0.1:8888'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const shieldApi = env.VITE_SHIELD_API_URL?.trim() || DEFAULT_SHIELD_API

  return {
    base: mode === 'production' ? '/dashboard/' : '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': srcDir,
      },
    },
    server: {
      proxy: {
        '/internal': shieldApi,
        '/v1': shieldApi,
      },
    },
  }
})
