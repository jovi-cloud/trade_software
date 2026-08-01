/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = process.env.BACKEND_PORT || env.BACKEND_PORT || '8001'
  const frontendPort = Number(process.env.FRONTEND_PORT || env.FRONTEND_PORT || '5174')

  return {
    plugins: [react(), tailwindcss()],
    // Vitest covers lib/ and the pure logic behind features (ARCHITECTURE.md 9);
    // presentational components are not chased for coverage.
    test: {
      include: ['src/**/*.test.ts'],
      environment: 'node',
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: frontendPort,
      strictPort: true,
      // The API is proxied so the browser only ever talks to one origin in
      // development. Frontend code always calls relative "/api/v1/..." paths.
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
