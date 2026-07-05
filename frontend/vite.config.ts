import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/unlock': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/setup': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
