import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        host: '0.0.0.0',
        port: 5173,
        allowedHosts: ['dpp-frontend'],
        proxy: {
            '/api': {
                target: process.env.VITE_PROXY_TARGET || 'http://backend:8000',
                changeOrigin: true,
            },
        },
    },
    test: {
        environment: 'node',
        passWithNoTests: true,
        exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
    },
});
