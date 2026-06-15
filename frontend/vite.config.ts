import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const shouldAnalyze = mode === 'analyze'
  const apiProxyTarget = process.env.E2E_API_PROXY_TARGET || 'http://127.0.0.1:31800'

  return {
    plugins: [react()],
    define: {
      __API_BASE__: JSON.stringify(process.env.VITE_API_BASE || '/api/v1'),
    },
    build: {
      sourcemap: shouldAnalyze,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              if (id.includes('/src/features/email/')) return 'feature-email'
              if (id.includes('/src/features/products/')) return 'feature-products'
              if (id.includes('/src/features/assets/')) return 'feature-assets'
              if (id.includes('/src/features/content/')) return 'feature-content'
              if (id.includes('/src/features/operations/')) return 'feature-operations'
              return undefined
            }

            if (id.includes('react-router-dom')) return 'react'
            if (id.includes('@tanstack/react-query')) return 'query'
            if (
              id.includes('react-hook-form') ||
              id.includes('@hookform/resolvers') ||
              id.includes('zod')
            )
              return 'forms'
            if (id.includes('react') || id.includes('scheduler')) return 'react'
            return 'vendor'
          },
        },
      },
    },
    server: {
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.ts',
      css: true,
      include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
      exclude: ['e2e/**', 'node_modules/**'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'lcov'],
        thresholds: {
          lines: 70,
          functions: 70,
          branches: 60,
          statements: 70,
        },
      },
    },
  }
})
