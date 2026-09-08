/**
 * Demo mode must not be able to mail a letter or take a payment.
 *
 * This is the single most important guarantee of a build with no
 * `VITE_API_BASE_URL`, so it is asserted three ways: every API function refuses
 * before doing anything; `fetch` is never called; and the shipped source
 * contains no payment or mailing endpoint that could be reached without a
 * configured API.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  DemoModeError,
  createDraft,
  getStatus,
  isConfigured,
  newIdempotencyKey,
  requestSuppression,
  startCheckout,
  verifyAddress,
} from '../src/lib/api';
import { IS_DEMO } from '../src/lib/config';
import { letterToHtml } from '../src/lib/download';
import { composeLetter } from '../src/lib/letter';

const ADDRESS = { line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' };

describe('demo mode', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('is the default when no API base URL is configured', () => {
    // Vitest runs without VITE_API_BASE_URL set — the demo-build default.
    expect(IS_DEMO).toBe(true);
    expect(isConfigured()).toBe(false);
  });

  it('refuses every network operation before touching the network', async () => {
    const calls: Array<Promise<unknown>> = [
      verifyAddress(ADDRESS),
      createDraft({
        address: ADDRESS,
        observations: [],
        note: '',
        suggestions: [],
        letterFingerprint: 'abc',
      }),
      startCheckout('ltr_1', newIdempotencyKey()),
      getStatus('ltr_1'),
      requestSuppression(ADDRESS, 'no thanks'),
    ];

    for (const call of calls) {
      await expect(call).rejects.toBeInstanceOf(DemoModeError);
    }
    expect(fetch).not.toHaveBeenCalled();
  });

  it('says plainly that nothing will be mailed', async () => {
    await expect(getStatus('ltr_1')).rejects.toThrow(/no letter will be mailed/i);
  });

  it('still produces a complete, printable letter with no backend', () => {
    const doc = composeLetter({
      address: ADDRESS,
      observations: ['all_night'],
      note: '',
      suggestions: ['shield'],
      dateIso: '2026-09-07',
    });
    const html = letterToHtml(doc);

    expect(html).toContain('<!doctype html>');
    expect(html).toContain('414 W San Antonio St');
    expect(html).toContain('Hello from a neighbor,');
    expect(html).toContain('@page');
    // Self-contained: nothing to fetch when it is opened offline.
    expect(html).not.toMatch(/<script/);
    expect(html).not.toMatch(/<link/);
    expect(html).not.toMatch(/src=/);
  });

  it('escapes anything a person typed into the downloadable file', () => {
    const doc = composeLetter({
      address: { ...ADDRESS, line1: '414 "W" St & Co' },
      observations: ['other'],
      note: 'It <script>alert(1)</script> shines',
      suggestions: [],
      dateIso: '2026-09-07',
    });
    const html = letterToHtml(doc);
    expect(html).not.toContain('<script>alert');
    expect(html).toContain('&amp;');
  });
});

describe('the shipped source', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const src = (name: string) => readFileSync(join(here, '..', 'src', name), 'utf8');

  it('never hard-codes a key or a secret', () => {
    for (const file of ['lib/config.ts', 'lib/api.ts', 'routes/LiveSend.tsx']) {
      const contents = src(file);
      expect(contents).not.toMatch(/sk_live_|sk_test_|whsec_|live_[a-z0-9]{20}/i);
      expect(contents).not.toMatch(/api[_-]?key\s*[:=]\s*['"][^'"]{8,}/i);
    }
  });

  it('routes every network call through the guarded client', () => {
    // A stray fetch() outside lib/api.ts would bypass the demo-mode guard.
    for (const file of ['routes/LiveSend.tsx', 'routes/Create.tsx', 'routes/Legal.tsx', 'routes/Receipt.tsx']) {
      expect(src(file), file).not.toMatch(/\bfetch\s*\(/);
      expect(src(file), file).not.toMatch(/XMLHttpRequest/);
    }
  });
});
