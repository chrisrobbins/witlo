/**
 * Post-payment status.
 *
 * The wording here is the whole job. "Submitted to the mailing provider" and
 * "delivered" are different facts and this page never blurs them: it reports
 * only what the server has actually been told, and says plainly when it does
 * not know something yet.
 */
import { useEffect, useState } from 'react';
import { Link, useRouter } from '../lib/router';
import { Callout, SectionHead, StatusBadge } from '../components/Ui';
import { ApiError, getStatus, type DraftStatus } from '../lib/api';
import { CONTACT_EMAIL, IS_DEMO, formatUsd } from '../lib/config';

type Tone = 'ok' | 'pending' | 'stop' | 'neutral';

const COPY: Record<DraftStatus['status'], { tone: Tone; headline: string; detail: string }> = {
  draft: {
    tone: 'neutral',
    headline: 'Not sent',
    detail: 'This letter was written but never paid for, so nothing was printed or mailed.',
  },
  pending_payment: {
    tone: 'pending',
    headline: 'Waiting on payment',
    detail:
      'The payment has not completed yet. Nothing has been printed. If you closed the payment page, you can start again — you will not be charged twice.',
  },
  paid: {
    tone: 'pending',
    headline: 'Paid — queued for printing',
    detail:
      'Payment confirmed. The letter is queued to be sent to our printing and mailing provider. It has not been submitted yet.',
  },
  submitting: {
    tone: 'pending',
    headline: 'Being submitted',
    detail: 'We are handing this letter to the mailing provider now.',
  },
  submitted: {
    tone: 'ok',
    headline: 'Submitted to the mailing provider',
    detail:
      'The mailing provider has accepted this letter for printing and posting. That is not the same as delivered — the postal service has it from here, and we will update this page as they report progress.',
  },
  in_transit: {
    tone: 'ok',
    headline: 'In transit',
    detail:
      'The postal service has reported this letter as moving through their network. Delivery dates are estimates, not guarantees.',
  },
  in_local_area: {
    tone: 'ok',
    headline: 'In the destination area',
    detail: 'The postal service has reported this letter as having reached the destination area.',
  },
  processed_for_delivery: {
    tone: 'ok',
    headline: 'Processed for delivery',
    detail:
      'The postal service has processed this letter at the destination facility. This is the last update we receive; there is no confirmation that it reached a particular mailbox.',
  },
  returned_to_sender: {
    tone: 'stop',
    headline: 'Returned to sender',
    detail:
      'The postal service returned this letter. That usually means the address does not receive mail. Write to us and we will refund the postage.',
  },
  failed: {
    tone: 'stop',
    headline: 'Not mailed',
    detail:
      'We could not hand this letter to the mailing provider. You have not been charged, or you have been refunded in full — the amount below reflects what actually happened.',
  },
  canceled: {
    tone: 'neutral',
    headline: 'Canceled',
    detail: 'This letter was canceled before it was submitted. Nothing was mailed.',
  },
};

export function Receipt() {
  const { query } = useRouter();
  const draftId = query.get('letter') ?? '';
  const [status, setStatus] = useState<DraftStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      if (IS_DEMO || !draftId) {
        setLoading(false);
        return;
      }
      try {
        const next = await getStatus(draftId);
        if (cancelled) return;
        setStatus(next);
        setError(null);
        setLoading(false);
        // Keep checking only while the outcome can still change.
        if (['pending_payment', 'paid', 'submitting'].includes(next.status)) {
          timer = window.setTimeout(poll, 4000);
        }
      } catch (e) {
        if (cancelled) return;
        setLoading(false);
        setError(e instanceof ApiError ? e.message : 'We could not load this letter’s status.');
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [draftId]);

  if (IS_DEMO) {
    return (
      <div className="section">
        <div className="wrap-narrow">
          <SectionHead level={1} eyebrow="Receipt" title="Nothing was mailed" />
          <Callout tone="warm" title="This is the demo.">
            <p style={{ marginBottom: 0 }}>
              No payment was taken and no letter exists. On the live site this page shows what the
              mailing provider has actually reported, and distinguishes “submitted” from
              “delivered”.
            </p>
          </Callout>
          <p style={{ marginTop: 'var(--space-5)' }}>
            <Link to="/create" className="btn btn--secondary">Back to the letter</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="section">
      <div className="wrap-narrow">
        <SectionHead level={1} eyebrow="Receipt" title="Where your letter is" />

        {loading && <p aria-live="polite">Checking…</p>}

        {error && (
          <Callout tone="warm" title="We could not load this.">
            <p>{error}</p>
            <p style={{ marginBottom: 0 }}>
              Your receipt email has the same reference. If something looks wrong, write to{' '}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          </Callout>
        )}

        {status && (
          <>
            <div className="panel">
              <StatusBadge tone={COPY[status.status].tone}>{COPY[status.status].headline}</StatusBadge>
              <p style={{ marginTop: 'var(--space-4)' }}>{COPY[status.status].detail}</p>
              {status.statusDetail && <p className="muted">{status.statusDetail}</p>}

              <dl className="summary" style={{ marginTop: 'var(--space-5)' }}>
                <div>
                  <dt>Reference</dt>
                  <dd style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>{status.id}</dd>
                </div>
                {status.amountPaidCents !== null && (
                  <div>
                    <dt>Paid</dt>
                    <dd>{formatUsd(status.amountPaidCents)}</dd>
                  </div>
                )}
                {status.submittedAt && (
                  <div>
                    <dt>Submitted to the mailing provider</dt>
                    <dd>{status.submittedAt}</dd>
                  </div>
                )}
                {status.expectedDeliveryDate && (
                  <div>
                    <dt>Provider’s delivery estimate</dt>
                    <dd>{status.expectedDeliveryDate}</dd>
                  </div>
                )}
                {status.providerReference && (
                  <div>
                    <dt>Provider reference</dt>
                    <dd style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                      {status.providerReference}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            <Callout tone="gold" title="A note on what “delivered” means">
              <p style={{ marginBottom: 0 }}>
                No first-class letter service confirms that a specific envelope reached a specific
                mailbox. The furthest this page will ever go is reporting what the postal service
                told our mailing provider. Anything stronger would be a guess dressed up as a fact.
              </p>
            </Callout>
          </>
        )}

        <p style={{ marginTop: 'var(--space-6)' }}>
          <Link to="/" className="btn btn--ghost">Back to the start</Link>
        </p>
      </div>
    </div>
  );
}

export function NotFound() {
  return (
    <div className="section">
      <div className="wrap-narrow center">
        <p className="eyebrow">404</p>
        <h1>Nothing here but sky</h1>
        <p className="lede">
          That page does not exist. Which is, admittedly, the ideal state for most things at night.
        </p>
        <p>
          <Link to="/" className="btn btn--primary">Back to the start</Link>
        </p>
      </div>
    </div>
  );
}
