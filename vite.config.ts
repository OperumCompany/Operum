import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      ignored: ['**/.venv/**', '**/.venv.broken-*/**', '**/.worktrees/**', '**/data/**'],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
});
