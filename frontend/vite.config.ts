import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        proxy: {
            '/api': {
                target: env.VITE_BACKEND_URL || 'http://localhost:5050',
                changeOrigin: true,
                secure: false
            }
        }
      },
      plugins: [react()],
      define: {
        // Secure: Do NOT expose full process.env
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
