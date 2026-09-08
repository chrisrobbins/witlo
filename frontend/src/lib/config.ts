/**
 * Runtime configuration, all of it public.
 *
 * Nothing secret belongs in this file or anywhere else under `src/`. Vite
 * inlines every `VITE_*` value into the JavaScript bundle that ships to the
 * browser, so API keys, mailing credentials and Stripe secret keys live only in
 * the backend's environment. The only Stripe value the browser ever sees is the
 * hosted Checkout URL the server hands back.
 */

const rawApiBase = (import.meta.env.VITE_API_BASE_URL ?? '').trim();

/**
 * `VITE_API_BASE_URL="/"` (or ".") means the API is served from this same
 * origin — the single-project Vercel deployment, where requests go to
 * `/api/v1/...` with no host. Any other non-empty value is an absolute origin.
 */
const sameOrigin = rawApiBase === '/' || rawApiBase === '.';

export const API_BASE_URL: string = sameOrigin ? '' : rawApiBase.replace(/\/+$/, '');

/**
 * Demo mode is the default and the safe state: no backend is configured, so the
 * app composes letters entirely in the browser and cannot mail or charge
 * anything. This is what a build with no `VITE_API_BASE_URL` serves.
 */
export const IS_DEMO: boolean = !sameOrigin && API_BASE_URL.length === 0;

export const SITE_NAME = 'Why Is This Light On?';
export const SITE_URL = 'https://witlo.info';

/** Set by Vite from `VITE_BASE_PATH`; used for asset URLs, never for routing. */
export const BASE_URL: string = import.meta.env.BASE_URL || '/';

/**
 * Display-only price hint for demo mode. In live mode the server is the sole
 * authority on price and the UI shows whatever the quote endpoint returns.
 */
export const DEMO_PRICE_CENTS = 0;

export const CONTACT_EMAIL = (import.meta.env.VITE_CONTACT_EMAIL ?? 'hello@witlo.info').trim();

export function apiUrl(path: string): string {
  if (IS_DEMO) throw new Error('apiUrl called in demo mode');
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

export function formatUsd(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
