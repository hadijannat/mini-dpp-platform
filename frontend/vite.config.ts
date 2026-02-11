import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';
// SHARED_DIR env var allows Docker builds to specify the absolute path to the
// shared/ directory.  Falls back to the sibling directory for local dev / CI.
const sharedDir = process.env.SHARED_DIR
  ? path.resolve(process.env.SHARED_DIR)
  : path.resolve(__dirname, '../shared');

export default defineConfig({
  plugins: [
    react(),
    // Explicit @shared resolver — resolve.alias alone fails under the
    // docker-container BuildKit driver used in CI.
    {
      name: 'resolve-shared',
      enforce: 'pre' as const,
      resolveId(source) {
        if (source.startsWith('@shared/')) {
          const resolved = source.replace('@shared', sharedDir);
          return resolved;
        }
        return null;
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': sharedDir,
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['dpp-frontend'],
    fs: {
      allow: [path.resolve(__dirname, '.'), sharedDir],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    // Accessibility and component interaction suites require a DOM runtime.
    environmentMatchGlobs: [
      ['src/features/submodels/__tests__/accessibility.audit.test.tsx', 'jsdom'],
      ['src/features/editor/pages/__tests__/SubmodelEditorPage.progress.test.tsx', 'jsdom'],
    ],
    passWithNoTests: true,
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
  },
});
