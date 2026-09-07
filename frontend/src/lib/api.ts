/**
 * Backend client.
 *
 * Every function here throws `DemoModeError` before doing anything when the app
 * is running without a configured API. That guard is the single reason demo
 * mode cannot mail a letter or take a payment: there is no code path from the
 * demo build to a network call that sends anything. `tests/demo-mode.test.ts`
 * asserts it.
 */
import { API_BASE_URL, IS_DEMO, apiUrl } from './config';
import type { UsAddress } from './address';
import type { ObservationKey, SuggestionKey } from './letterContent';

export class DemoModeError extends Error {
  constructor() {
    super('This is the demo. No letter will be mailed and no payment will be taken.');
    this.name = 'DemoModeError';
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export interface AddressVerification {
  status: 'deliverable' | 'deliverable_with_changes' | 'needs_unit' | 'undeliverable';
  message: string;
  standardized: UsAddress | null;
  suppressed: boolean;
  cooldownUntil: string | null;
}

export interface Quote {
  currency: string;
  totalCents: number;
  lines: Array<{ label: string; cents: number }>;
  deliveryEstimate: string;
  disclaimer: string;
}

export interface DraftPayload {
  address: UsAddress;
  observations: ObservationKey[];
  note: string;
  suggestions: SuggestionKey[];
  letterFingerprint: string;
  senderEmail?: string;
  botToken?: string;
}

export interface Draft {
  id: string;
  status: string;
  letterText: string;
  letterFingerprint: string;
  address: UsAddress;
  quote: Quote;
}

export interface CheckoutSession {
  checkoutUrl: string;
  draftId: string;
}

export interface DraftStatus {
  id: string;
  status:
    | 'draft'
    | 'pending_payment'
    | 'paid'
    | 'submitting'
    | 'submitted'
    | 'failed'
    | 'canceled'
    | 'in_transit'
    | 'in_local_area'
    | 'processed_for_delivery'
    | 'returned_to_sender';
  statusLabel: string;
  statusDetail: string;
  submittedAt: string | null;
  expectedDeliveryDate: string | null;
  providerReference: string | null;
  amountPaidCents: number | null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (IS_DEMO) throw new DemoModeError();

  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    const detail = (body as { code?: string; detail?: string } | null) ?? null;
    throw new ApiError(
      response.status,
      detail?.code ?? 'error',
      detail?.detail ?? `The server responded with ${response.status}.`,
    );
  }

  return body as T;
}

export function isConfigured(): boolean {
  return API_BASE_URL.length > 0;
}

export function verifyAddress(address: UsAddress): Promise<AddressVerification> {
  return request<AddressVerification>('/api/v1/addresses/verify', {
    method: 'POST',
    body: JSON.stringify({ address }),
  });
}

export function createDraft(payload: DraftPayload): Promise<Draft> {
  return request<Draft>('/api/v1/letters', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * `idempotencyKey` is generated once per confirmation attempt and reused on
 * retry, so a double-click or a flaky connection can never create a second
 * charge for the same letter.
 */
export function startCheckout(draftId: string, idempotencyKey: string): Promise<CheckoutSession> {
  return request<CheckoutSession>(`/api/v1/letters/${encodeURIComponent(draftId)}/checkout`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({}),
  });
}

export function getStatus(draftId: string): Promise<DraftStatus> {
  return request<DraftStatus>(`/api/v1/letters/${encodeURIComponent(draftId)}/status`);
}

export function requestSuppression(address: UsAddress, reason: string): Promise<{ ok: true }> {
  return request<{ ok: true }>('/api/v1/suppressions', {
    method: 'POST',
    body: JSON.stringify({ address, reason }),
  });
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `k_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}
