/**
 * Live mailing panel — only rendered when an API is configured.
 *
 * The sequence is deliberate:
 *   verify address -> show the standardized address the printer will use ->
 *   show the full price and the delivery caveats -> one explicit confirmation ->
 *   hand off to Stripe Checkout.
 *
 * The browser never decides that mail should be sent. It only creates a draft
 * and opens a payment page; the server mails a letter when, and only when, a
 * signed payment webhook says the money arrived.
 */
import { useState } from 'react';
import { Callout } from '../components/Ui';
import { ArrowRightIcon, MailIcon } from '../components/Icons';
import { TextField } from '../components/Form';
import { formatUsd } from '../lib/config';
import { isValidEmail } from '../lib/validation';
import {
  ApiError,
  createDraft,
  newIdempotencyKey,
  startCheckout,
  verifyAddress,
  type AddressVerification,
  type Draft,
} from '../lib/api';
import { formatAddressLines, type UsAddress } from '../lib/address';
import type { ObservationKey, SuggestionKey } from '../lib/letterContent';

type Phase = 'idle' | 'verifying' | 'verified' | 'creating' | 'ready' | 'redirecting' | 'error';

interface Props {
  address: UsAddress;
  observations: ObservationKey[];
  note: string;
  suggestions: SuggestionKey[];
  fingerprint: string;
  dateIso: string;
}

export function LiveSendPanel({
  address,
  observations,
  note,
  suggestions,
  fingerprint,
  dateIso,
}: Props) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [verification, setVerification] = useState<AddressVerification | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState<string | undefined>();
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Generated once per panel mount and reused on every retry, so a double
  // submit or a refresh mid-redirect cannot produce a second charge.
  const [idempotencyKey] = useState(() => newIdempotencyKey());

  async function handleVerify() {
    setPhase('verifying');
    setError(null);
    try {
      const result = await verifyAddress(address);
      setVerification(result);
      setPhase(result.status === 'undeliverable' || result.suppressed ? 'error' : 'verified');
      if (result.suppressed) {
        setError(
          'This address has asked not to receive letters from this service. We will not mail to it.',
        );
      } else if (result.status === 'undeliverable') {
        setError(result.message);
      }
    } catch (e) {
      setPhase('error');
      setError(e instanceof ApiError ? e.message : 'We could not reach the mailing service.');
    }
  }

  async function handlePrepare() {
    if (!isValidEmail(email)) {
      setEmailError('We need an email address to send you a receipt and the mailing status.');
      return;
    }
    setEmailError(undefined);
    setPhase('creating');
    setError(null);
    try {
      const created = await createDraft({
        address: verification?.standardized ?? address,
        observations,
        note,
        suggestions,
        letterFingerprint: fingerprint,
        dateIso,
        senderEmail: email.trim(),
      });
      setDraft(created);
      setPhase('ready');
    } catch (e) {
      setPhase('error');
      setError(e instanceof ApiError ? e.message : 'We could not prepare this letter.');
    }
  }

  async function handleCheckout() {
    if (!draft || !confirmed) return;
    setPhase('redirecting');
    setError(null);
    try {
      const session = await startCheckout(draft.id, idempotencyKey);
      window.location.assign(session.checkoutUrl);
    } catch (e) {
      setPhase('ready');
      setError(e instanceof ApiError ? e.message : 'We could not open the payment page.');
    }
  }

  const standardized = verification?.standardized;

  return (
    <div className="panel">
      <h3>Have us mail it</h3>
      <p className="muted">
        We print the letter, fold it, stamp it and hand it to the postal service. You can also
        print it yourself for free using the buttons above — that path is always open.
      </p>

      {phase === 'idle' && (
        <button type="button" className="btn btn--primary" onClick={handleVerify}>
          Check this address <ArrowRightIcon />
        </button>
      )}

      {phase === 'verifying' && <p aria-live="polite">Checking the address…</p>}

      {error && (
        <Callout tone="warm" title="We cannot continue with this one.">
          <p style={{ marginBottom: 0 }}>{error}</p>
        </Callout>
      )}

      {(phase === 'verified' || phase === 'creating' || phase === 'ready' || phase === 'redirecting') &&
        verification && (
          <>
            <Callout tone={verification.status === 'deliverable' ? 'ok' : 'gold'} title="Address as the post office reads it">
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', lineHeight: 1.6 }}>
                {formatAddressLines(standardized ?? address).map((l, i) => (
                  <div key={i}>{l}</div>
                ))}
              </div>
              <p style={{ marginTop: 'var(--space-3)', marginBottom: 0 }}>{verification.message}</p>
            </Callout>

            {verification.cooldownUntil && (
              <Callout tone="warm" title="A letter has already gone to this address recently.">
                <p style={{ marginBottom: 0 }}>
                  To keep this from becoming a nuisance, we wait before writing to the same address
                  again. The next letter here can go out on {verification.cooldownUntil}.
                </p>
              </Callout>
            )}
          </>
        )}

      {phase === 'verified' && !verification?.cooldownUntil && (
        <div style={{ marginTop: 'var(--space-5)' }}>
          <TextField
            label="Your email"
            required
            type="email"
            inputMode="email"
            autoComplete="email"
            value={email}
            onChange={setEmail}
            error={emailError}
            hint="For the receipt and mailing status only. It is never printed on the letter and never shared with the recipient."
          />
          <button type="button" className="btn btn--primary" onClick={handlePrepare}>
            See the price <ArrowRightIcon />
          </button>
        </div>
      )}

      {phase === 'creating' && <p aria-live="polite">Preparing your letter…</p>}

      {(phase === 'ready' || phase === 'redirecting') && draft && (
        <div style={{ marginTop: 'var(--space-5)' }}>
          <dl className="summary">
            {draft.quote.lines.map((line) => (
              <div key={line.label}>
                <dt>{line.label}</dt>
                <dd>{formatUsd(line.cents)}</dd>
              </div>
            ))}
            <div className="summary--total">
              <dt>Total, all in</dt>
              <dd>{formatUsd(draft.quote.totalCents)}</dd>
            </div>
          </dl>

          <Callout tone="gold" title="What we can and cannot promise">
            <p>{draft.quote.deliveryEstimate}</p>
            <p style={{ marginBottom: 0 }}>{draft.quote.disclaimer}</p>
          </Callout>

          <label className="choice" style={{ marginTop: 'var(--space-5)' }}>
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span className="choice__box" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 12.5l5 5 11-11" />
              </svg>
            </span>
            <span className="choice__body">
              <strong>I have read the letter above and I want it mailed to this address.</strong>
              <span>
                I understand this is a real paper letter to a real household, that it cannot be
                recalled once it is handed to the postal service, and that {formatUsd(draft.quote.totalCents)} will be charged.
              </span>
            </span>
          </label>

          <button
            type="button"
            className="btn btn--primary btn--block"
            style={{ marginTop: 'var(--space-4)' }}
            disabled={!confirmed || phase === 'redirecting'}
            onClick={handleCheckout}
          >
            <MailIcon size={18} />
            {phase === 'redirecting'
              ? 'Opening secure payment…'
              : `Pay ${formatUsd(draft.quote.totalCents)} and mail it`}
          </button>
          <p className="muted" style={{ fontSize: 'var(--step--1)', marginTop: 'var(--space-3)', marginBottom: 0 }}>
            Payment is handled by Stripe on their own page. We never see your card details, and
            your letter is only printed after Stripe confirms the payment to our server directly.
          </p>
        </div>
      )}
    </div>
  );
}
