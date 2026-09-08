/**
 * `VITE_API_BASE_URL` decides demo vs live, and "/" means the API is on this
 * same origin (the single Vercel deployment).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

async function loadConfig(value: string | undefined) {
  vi.resetModules();
  if (value === undefined) vi.stubEnv('VITE_API_BASE_URL', '');
  else vi.stubEnv('VITE_API_BASE_URL', value);
  return import('../src/lib/config');
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('API base URL', () => {
  it('is demo mode when unset', async () => {
    const c = await loadConfig(undefined);
    expect(c.IS_DEMO).toBe(true);
  });

  it('treats "/" as same-origin live mode with relative URLs', async () => {
    const c = await loadConfig('/');
    expect(c.IS_DEMO).toBe(false);
    expect(c.API_BASE_URL).toBe('');
    expect(c.apiUrl('/api/v1/health')).toBe('/api/v1/health');
  });

  it('uses an absolute origin verbatim, without a trailing slash', async () => {
    const c = await loadConfig('https://api.example.com/');
    expect(c.IS_DEMO).toBe(false);
    expect(c.apiUrl('/api/v1/health')).toBe('https://api.example.com/api/v1/health');
  });
});
