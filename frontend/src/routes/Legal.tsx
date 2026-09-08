import { useState, type FormEvent } from 'react';
import { Link } from '../lib/router';
import { Callout, SectionHead } from '../components/Ui';
import { TextField, SelectField } from '../components/Form';
import { CONTACT_EMAIL, IS_DEMO } from '../lib/config';
import { EMPTY_ADDRESS, US_STATES, type UsAddress } from '../lib/address';
import { hasErrors, validateAddress } from '../lib/validation';
import { ApiError, requestSuppression } from '../lib/api';

/**
 * Owner-supplied details are marked with <Todo> so they are impossible to miss
 * before launch. They render visibly on the page rather than as an HTML comment
 * — a placeholder you cannot see is a placeholder that ships.
 */
function Todo({ children }: { children: string }) {
  return (
    <mark
      style={{
        background: 'rgba(233,196,106,0.2)',
        color: 'var(--gold-300)',
        padding: '0.1em 0.4em',
        borderRadius: 4,
        fontFamily: 'var(--font-mono)',
        fontSize: '0.85em',
      }}
    >
      [ {children} ]
    </mark>
  );
}

export function Privacy() {
  return (
    <div className="section">
      <div className="wrap-narrow">
        <p className="eyebrow">Privacy</p>
        <h1>What we collect, and what we don’t</h1>
        <p className="lede">
          This describes what the software actually does. If something here does not match the
          behavior you see, the page is wrong and we want to know.
        </p>

        <Callout tone="gold" title="Before launch">
          <p style={{ marginBottom: 0 }}>
            The operator must complete: <Todo>legal entity name</Todo>{' '}
            <Todo>business mailing address</Todo> <Todo>data controller contact</Todo>{' '}
            <Todo>governing jurisdiction</Todo>. Everything else on this page is a description of
            the shipped code and does not need editing.
          </p>
        </Callout>

        <hr />

        <h2>If you only print your letter</h2>
        <p>
          Nothing leaves your browser. The letter is composed on your own device from a template
          that shipped with the page. We receive no address, no note and no email. There is no
          account, and there is no analytics script on this site.
        </p>
        <p>
          While you are working, your draft is kept in your browser’s session storage so a
          refresh does not lose it. It is gone when you close the tab, and you can clear it at any
          time with “Start a new letter”.
        </p>

        <h2>If you ask us to mail your letter</h2>
        <p>Then we need, and store:</p>
        <ul>
          <li><strong>The recipient’s postal address</strong> — we cannot print an envelope without it.</li>
          <li><strong>Your selections and your optional note</strong> — these are the letter.</li>
          <li><strong>Your email address</strong> — for the receipt and the mailing status. Nothing else, ever.</li>
          <li>
            <strong>Payment records from Stripe</strong> — an identifier and an amount. Card
            numbers are never sent to our servers.
          </li>
          <li>
            <strong>A one-way hash of the recipient address</strong> — this is what enforces the
            repeat-letter cooldown and the do-not-mail list.
          </li>
        </ul>
        <p>
          We do not ask for your name or your home address, and the letter does not carry them.
        </p>

        <h2>What we deliberately do not have</h2>
        <ul>
          <li>No public map, no address feed, no directory of recipients, no public complaints.</li>
          <li>No way for anyone — including a recipient — to look up who sent a letter.</li>
          <li>No advertising, no third-party analytics, no tracking pixels, no data sales.</li>
          <li>No recipient addresses or letter text in routine application logs.</li>
        </ul>

        <h2>How long we keep things</h2>
        <p>
          Letter text, the recipient address and your email are deleted{' '}
          <strong>90 days</strong> after the letter reaches a final state, which is long enough to
          answer a “what did you send?” question and settle a refund. After that we keep only the
          one-way address hash, the date and the outcome — enough to honor a cooldown and a
          do-not-mail request, and not enough to reconstruct the letter. Stripe keeps its own
          payment records under its own retention rules.
        </p>

        <h2>Recipients</h2>
        <p>
          Any recipient can put their address on the do-not-mail list at{' '}
          <Link to="/no-more-letters">witlo.info/#/no-more-letters</Link>, or by writing
          to the return address on the letter. That list is checked before anything is printed, it
          is stored as a hash, and there is no way to un-suppress an address from the public site.
        </p>

        <h2>Subprocessors</h2>
        <ul>
          <li><strong>Stripe</strong> — payment processing.</li>
          <li><strong>The mailing provider</strong> — printing, address validation and postal handling. <Todo>name the provider once chosen</Todo></li>
          <li><strong>The API host</strong> — where the server and database run. <Todo>name the host</Todo></li>
        </ul>

        <h2>Asking us about your data</h2>
        <p>
          Write to <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. Because we do not
          keep accounts, please include enough detail to find the record — the recipient address
          and the approximate date.
        </p>
      </div>
    </div>
  );
}

export function Terms() {
  return (
    <div className="section">
      <div className="wrap-narrow">
        <p className="eyebrow">Terms</p>
        <h1>The deal, plainly</h1>

        <Callout tone="gold" title="Before launch">
          <p style={{ marginBottom: 0 }}>
            The operator must complete: <Todo>legal entity name</Todo>{' '}
            <Todo>business address</Todo> <Todo>governing law and venue</Todo>{' '}
            <Todo>refund window</Todo>, and should have this reviewed by a lawyer. This page
            describes how the software behaves; it is not legal advice.
          </p>
        </Callout>

        <hr />

        <h2>What the service does</h2>
        <p>
          We compose a letter from a fixed template using the selections you make, show it to you,
          and — if you ask and pay for it — print it and hand it to a postal mailing provider
          addressed to the property you specified.
        </p>

        <h2>What you agree to</h2>
        <ul>
          <li>
            You are using this to share information about outdoor lighting, in good faith, about a
            light you have actually observed.
          </li>
          <li>
            You will not use it to harass, threaten or target anyone. One address, one letter, a
            cooldown before another; attempts to work around that are misuse.
          </li>
          <li>You are an adult, or you have an adult with you who is agreeing to this.</li>
          <li>Anything you type in the optional note is yours, and you take responsibility for it.</li>
        </ul>

        <h2>What we may refuse</h2>
        <p>
          We may decline to print any letter, refund it, and say so — including for addresses on
          the do-not-mail list, addresses that fail postal validation, notes that read as
          threatening, or patterns that look like harassment. We do not have to explain a refusal
          in detail, and we will not send a letter we think is being used to hurt someone.
        </p>

        <h2>What we cannot promise</h2>
        <ul>
          <li>
            <strong>Delivery.</strong> We can promise that a letter was handed to the mailing
            provider. Only the postal service delivers it, and mail is occasionally lost, delayed
            or returned. Our status page says which of these has actually happened.
          </li>
          <li><strong>A response.</strong> Most letters will never get one.</li>
          <li><strong>A lighting change.</strong> See above; it is a letter.</li>
        </ul>

        <h2>Money</h2>
        <p>
          You see the full price before you pay, and you confirm explicitly. If we take payment and
          then fail to hand the letter to the mailing provider, we refund it in full without you
          having to ask. Once a letter has been submitted for printing it cannot be recalled, so
          that is the point of no return, and it is the point the confirmation checkbox is about.
        </p>

        <h2>Nothing here is legal advice</h2>
        <p>
          This service takes no position on whether any light complies with any ordinance, and the
          letter says nothing about the law. If you have a legal question about a light, ask a
          lawyer or your local government — not us.
        </p>
      </div>
    </div>
  );
}

export function NoMoreLetters() {
  const [address, setAddress] = useState<UsAddress>({ ...EMPTY_ADDRESS });
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<ReturnType<typeof validateAddress>>({});
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found = validateAddress(address);
    setErrors(found);
    if (hasErrors(found)) return;

    if (IS_DEMO) {
      setState('done');
      setMessage(
        'This is the demo, so nothing was recorded — but on the live site this is all it takes.',
      );
      return;
    }

    setState('sending');
    try {
      await requestSuppression(address, reason);
      setState('done');
      setMessage('Done. This address is now on the do-not-mail list.');
    } catch (err) {
      setState('error');
      setMessage(
        err instanceof ApiError
          ? err.message
          : 'Something went wrong. Please email us and we will do it by hand.',
      );
    }
  }

  return (
    <div className="section">
      <div className="wrap-narrow">
        <SectionHead level={1} eyebrow="For recipients" title="No more letters to this address">
          <p>
            If a letter arrived and you would rather not get another, put the address in below. We
            will add it to a do-not-mail list that is checked before anything is printed. You do
            not need to explain yourself, and you do not need to give us your name.
          </p>
        </SectionHead>

        {state === 'done' ? (
          <Callout tone="ok" title="Understood.">
            <p style={{ marginBottom: 0 }}>{message}</p>
          </Callout>
        ) : (
          <form className="panel" onSubmit={submit} noValidate>
            <TextField
              label="Street address"
              required
              value={address.line1}
              onChange={(v) => setAddress((a) => ({ ...a, line1: v }))}
              error={errors.line1}
              maxLength={80}
            />
            <TextField
              label="Apartment, suite, or unit"
              value={address.line2}
              onChange={(v) => setAddress((a) => ({ ...a, line2: v }))}
              error={errors.line2}
              maxLength={60}
            />
            <div className="field-row field-row--zip">
              <TextField
                label="City"
                required
                value={address.city}
                onChange={(v) => setAddress((a) => ({ ...a, city: v }))}
                error={errors.city}
                maxLength={50}
              />
              <SelectField
                label="State"
                required
                value={address.state}
                onChange={(v) => setAddress((a) => ({ ...a, state: v }))}
                placeholder="Choose…"
                options={US_STATES.map((s) => ({ value: s.code, label: `${s.code} — ${s.name}` }))}
                error={errors.state}
              />
              <TextField
                label="ZIP"
                required
                value={address.zip}
                onChange={(v) => setAddress((a) => ({ ...a, zip: v }))}
                inputMode="numeric"
                error={errors.zip}
                maxLength={10}
              />
            </div>
            <TextField
              label="Anything you want us to know"
              value={reason}
              onChange={setReason}
              maxLength={200}
              hint="Entirely optional. It goes to a person, not a database field."
            />
            {state === 'error' && (
              <Callout tone="warm">
                <p style={{ marginBottom: 0 }}>{message}</p>
              </Callout>
            )}
            <button type="submit" className="btn btn--primary" disabled={state === 'sending'}>
              {state === 'sending' ? 'Adding…' : 'Add this address to the do-not-mail list'}
            </button>
          </form>
        )}

        <p className="muted" style={{ marginTop: 'var(--space-6)' }}>
          You can also write to <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>, or use the
          return address printed on the letter.
        </p>
      </div>
    </div>
  );
}
