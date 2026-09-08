import { loadEnv } from 'vite';
// `defineConfig` from vitest/config is Vite's, widened with the `test` block below.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Base path notes (GitHub Pages):
 *
 *  - Custom domain (witlo.info) or a user/org page:  VITE_BASE_PATH=/
 *  - Project page (https://<user>.github.io/<repo>/):              VITE_BASE_PATH=/<repo>/
 *
 * The deploy workflow sets this automatically. Everything in the app that
 * builds a URL uses `import.meta.env.BASE_URL`, and routing is hash-based, so
 * no server rewrite rules are ever required.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const base = env.VITE_BASE_PATH || '/';

  return {
    base,
    plugins: [react()],
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
      target: 'es2020',
    },
    server: {
      port: 5173,
      strictPort: false,
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    },
  };
});
