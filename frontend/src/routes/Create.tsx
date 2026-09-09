/**
 * The address-to-preview journey.
 *
 * Four steps, all of them reversible, with the letter recomposed from scratch
 * on every keystroke so the preview can never lag behind the inputs. Sending is
 * the only step that touches the network, and in demo mode that step is absent
 * rather than disabled-but-wired.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Choice, ChoiceGroup, SelectField, TextAreaField, TextField } from '../components/Form';
import { Callout, SectionHead, Stepper, type StepDef } from '../components/Ui';
import { LetterSheet, EnvelopePreview } from '../components/LetterSheet';
import { ArrowLeftIcon, ArrowRightIcon, DownloadIcon, PrintIcon } from '../components/Icons';
import { Link, useNavigate } from '../lib/router';
import {
  EMPTY_ADDRESS,
  US_STATES,
  formatAddressLines,
  type UsAddress,
} from '../lib/address';
import {
  CONTENT,
  NOTE_MAX_CHARS,
  OBSERVATION_ORDER,
  SUGGESTION_ORDER,
  type ObservationKey,
  type SuggestionKey,
} from '../lib/letterContent';
import { composeLetter, letterFingerprint, todayIso } from '../lib/letter';
import { hasErrors, validateAddress, validateNote, type FieldErrors } from '../lib/validation';
import { downloadLetter, suggestedFilename } from '../lib/download';
import { IS_DEMO } from '../lib/config';
import { LiveSendPanel } from './LiveSend';

const STEPS: StepDef[] = [
  { id: 'address', label: 'The address' },
  { id: 'observed', label: 'What you noticed' },
  { id: 'suggestions', label: 'Helpful ideas' },
  { id: 'preview', label: 'Read and send' },
];

const STORAGE_KEY = 'wittl.draft.v1';

interface DraftState {
  address: UsAddress;
  observations: ObservationKey[];
  note: string;
  suggestions: SuggestionKey[];
}

const INITIAL: DraftState = {
  address: { ...EMPTY_ADDRESS },
  observations: [],
  note: '',
  suggestions: ['shield', 'timer'],
};

function loadDraft(): DraftState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return INITIAL;
    const parsed = JSON.parse(raw) as Partial<DraftState>;
    return {
      address: { ...EMPTY_ADDRESS, ...(parsed.address ?? {}) },
      observations: Array.isArray(parsed.observations) ? parsed.observations : [],
      note: typeof parsed.note === 'string' ? parsed.note : '',
      suggestions: Array.isArray(parsed.suggestions) ? parsed.suggestions : INITIAL.suggestions,
    };
  } catch {
    return INITIAL;
  }
}

function saveDraft(draft: DraftState): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* Private browsing, storage disabled, quota — none of it should break the flow. */
  }
}

export function clearDraft(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* no-op */
  }
}

export function Create() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<DraftState>(loadDraft);
  const [addressErrors, setAddressErrors] = useState<FieldErrors>({});
  const [noteError, setNoteError] = useState<string | undefined>();
  const headingRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    saveDraft(draft);
  }, [draft]);

  // Move focus to the step heading on every step change so keyboard and screen
  // reader users land in the new content instead of at the top of the document.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [step]);

  // Fixed once per draft so the preview, its fingerprint and the date sent to
  // the server are all composed from the same day, even if the sender lingers
  // on the page across midnight.
  const dateIso = useMemo(() => todayIso(), [draft]);

  const doc = useMemo(
    () =>
      composeLetter({
        address: draft.address,
        observations: draft.observations,
        note: draft.observations.includes('other') ? draft.note : '',
        suggestions: draft.suggestions,
        dateIso,
      }),
    [draft, dateIso],
  );

  const fingerprint = useMemo(() => letterFingerprint(doc.plainText), [doc.plainText]);

  const setAddress = useCallback((patch: Partial<UsAddress>) => {
    setDraft((d) => ({ ...d, address: { ...d.address, ...patch } }));
  }, []);

  const toggleObservation = useCallback((key: ObservationKey, on: boolean) => {
    setDraft((d) => ({
      ...d,
      observations: on ? [...d.observations, key] : d.observations.filter((k) => k !== key),
      note: key === 'other' && !on ? '' : d.note,
    }));
  }, []);

  const toggleSuggestion = useCallback((key: SuggestionKey, on: boolean) => {
    setDraft((d) => ({
      ...d,
      suggestions: on ? [...d.suggestions, key] : d.suggestions.filter((k) => k !== key),
    }));
  }, []);

  const goNext = useCallback(() => {
    if (step === 0) {
      const errors = validateAddress(draft.address);
      setAddressErrors(errors);
      if (hasErrors(errors)) return;
    }
    if (step === 1 && draft.observations.includes('other')) {
      const err = validateNote(draft.note);
      setNoteError(err);
      if (err) return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }, [step, draft]);

  const goBack = useCallback(() => setStep((s) => Math.max(0, s - 1)), []);

  return (
    <div className="wizard">
      <div className="wrap">
        <div className="no-print">
          <Stepper steps={STEPS} currentIndex={step} />
        </div>

        <div className={`wizard__grid${step === STEPS.length - 1 ? ' wizard__grid--wide' : ''}`}>
          <div>
            <div ref={headingRef} tabIndex={-1} style={{ outlineOffset: 6 }}>
              {step === 0 && (
                <AddressStep
                  address={draft.address}
                  errors={addressErrors}
                  onChange={setAddress}
                />
              )}
              {step === 1 && (
                <ObservationsStep
                  selected={draft.observations}
                  note={draft.note}
                  noteError={noteError}
                  onToggle={toggleObservation}
                  onNote={(v) => {
                    setDraft((d) => ({ ...d, note: v }));
                    setNoteError(undefined);
                  }}
                />
              )}
              {step === 2 && (
                <SuggestionsStep selected={draft.suggestions} onToggle={toggleSuggestion} />
              )}
              {step === 3 && (
                <PreviewStep
                  doc={doc}
                  fingerprint={fingerprint}
                  dateIso={dateIso}
                  address={draft.address}
                  observations={draft.observations}
                  note={draft.observations.includes('other') ? draft.note : ''}
                  suggestions={draft.suggestions}
                  onEdit={() => setStep(0)}
                  onStartOver={() => {
                    clearDraft();
                    setDraft(INITIAL);
                    setStep(0);
                    navigate('/create');
                  }}
                />
              )}
            </div>

            <div className="wizard__actions no-print">
              {step > 0 ? (
                <button type="button" className="btn btn--ghost" onClick={goBack}>
                  <ArrowLeftIcon /> Back
                </button>
              ) : (
                <Link to="/" className="btn btn--ghost">
                  <ArrowLeftIcon /> Leave
                </Link>
              )}
              {step < STEPS.length - 1 && (
                <button type="button" className="btn btn--primary" onClick={goNext}>
                  {step === 2 ? 'Read the letter' : 'Continue'} <ArrowRightIcon />
                </button>
              )}
            </div>
          </div>

          {step < STEPS.length - 1 && (
            <aside className="wizard__aside no-print">
              <SidePanel address={draft.address} doc={doc} />
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ step 1 */

function AddressStep({
  address,
  errors,
  onChange,
}: {
  address: UsAddress;
  errors: FieldErrors;
  onChange: (patch: Partial<UsAddress>) => void;
}) {
  return (
    <section className="panel">
      <SectionHead level={1} eyebrow="Step 1 of 4" title="Where is the light?">
        <p>
          The street address of the property, as you would write it on an envelope. This is the
          only address that appears on the letter.
        </p>
      </SectionHead>

      <TextField
        label="Street address"
        required
        value={address.line1}
        onChange={(v) => onChange({ line1: v })}
        placeholder="414 W San Antonio St"
        autoComplete="off"
        error={errors.line1}
        maxLength={80}
      />
      <TextField
        label="Apartment, suite, or unit"
        value={address.line2}
        onChange={(v) => onChange({ line2: v })}
        placeholder="Apt 2"
        autoComplete="off"
        error={errors.line2}
        maxLength={60}
      />
      <div className="field-row field-row--zip">
        <TextField
          label="City"
          required
          value={address.city}
          onChange={(v) => onChange({ city: v })}
          placeholder="Marfa"
          autoComplete="off"
          error={errors.city}
          maxLength={50}
        />
        <SelectField
          label="State"
          required
          value={address.state}
          onChange={(v) => onChange({ state: v })}
          placeholder="Choose…"
          options={US_STATES.map((s) => ({ value: s.code, label: `${s.code} — ${s.name}` }))}
          error={errors.state}
        />
        <TextField
          label="ZIP"
          required
          value={address.zip}
          onChange={(v) => onChange({ zip: v })}
          placeholder="79843"
          inputMode="numeric"
          autoComplete="off"
          error={errors.zip}
          maxLength={10}
        />
      </div>

      <Callout tone="gold" title="United States addresses only, for now.">
        <p style={{ margin: 0 }}>
          Our mailing service prints and posts within the US. If you are somewhere else, you can
          still write and print a letter here and post it yourself.
        </p>
      </Callout>
    </section>
  );
}

/* ------------------------------------------------------------------ step 2 */

function ObservationsStep({
  selected,
  note,
  noteError,
  onToggle,
  onNote,
}: {
  selected: ObservationKey[];
  note: string;
  noteError?: string;
  onToggle: (key: ObservationKey, on: boolean) => void;
  onNote: (value: string) => void;
}) {
  const showNote = selected.includes('other');
  return (
    <section className="panel">
      <SectionHead level={1} eyebrow="Step 2 of 4" title="What did you notice?">
        <p>
          All optional. Pick only what you actually saw — the letter says these were noticed from
          the street, on one occasion, which is exactly what happened.
        </p>
      </SectionHead>

      <ChoiceGroup legend="Observations" intro={<p className="muted" style={{ marginBottom: 0 }}>Choose any that apply, or none at all.</p>}>
        {OBSERVATION_ORDER.map((key) => (
          <Choice
            key={key}
            checked={selected.includes(key)}
            onChange={(on) => onToggle(key, on)}
            title={CONTENT.observations[key].label}
          />
        ))}
        <Choice
          checked={showNote}
          onChange={(on) => onToggle('other', on)}
          title={CONTENT.observations.other.label}
          description="A short, factual note in your own words."
        />
      </ChoiceGroup>

      {showNote && (
        <TextAreaField
          label="In a sentence or so"
          hint="Describe what you saw, not who you think is responsible. This appears in the letter word for word, and you will see it in the preview."
          value={note}
          onChange={onNote}
          maxLength={NOTE_MAX_CHARS}
          error={noteError}
          placeholder="The floodlight above the side door shines across the road into the arroyo."
        />
      )}

      <Callout tone="warm" title="Some lights are needed.">
        <p>
          A light you cannot explain from the sidewalk may be lighting a wheelchair ramp, a
          delivery entrance, or a path someone walks at 5 a.m. The letter is written as a
          courteous request precisely because you cannot know — it never claims the light is
          unnecessary, only that it may be contributing to nighttime brightness.
        </p>
      </Callout>
    </section>
  );
}

/* ------------------------------------------------------------------ step 3 */

function SuggestionsStep({
  selected,
  onToggle,
}: {
  selected: SuggestionKey[];
  onToggle: (key: SuggestionKey, on: boolean) => void;
}) {
  return (
    <section className="panel">
      <SectionHead level={1} eyebrow="Step 3 of 4" title="Which ideas should the letter offer?">
        <p>
          These are drawn from DarkSky International’s principles for responsible outdoor
          lighting. Choose the ones that seem practical for this property — two or three land
          better than all six.
        </p>
      </SectionHead>

      <ChoiceGroup legend="Suggestions to include">
        {SUGGESTION_ORDER.map((key) => (
          <Choice
            key={key}
            checked={selected.includes(key)}
            onChange={(on) => onToggle(key, on)}
            title={CONTENT.suggestions[key].label}
            description={CONTENT.suggestions[key].bullet}
          />
        ))}
      </ChoiceGroup>

      {selected.length === 0 && (
        <Callout tone="gold">
          <p style={{ margin: 0 }}>
            With nothing selected the letter still works — it explains light pollution and leaves
            the next step entirely to the reader.
          </p>
        </Callout>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ step 4 */

function PreviewStep({
  doc,
  fingerprint,
  dateIso,
  address,
  observations,
  note,
  suggestions,
  onEdit,
  onStartOver,
}: {
  doc: ReturnType<typeof composeLetter>;
  fingerprint: string;
  dateIso: string;
  address: UsAddress;
  observations: ObservationKey[];
  note: string;
  suggestions: SuggestionKey[];
  onEdit: () => void;
  onStartOver: () => void;
}) {
  return (
    <section>
      <div className="no-print">
        <SectionHead level={1} eyebrow="Step 4 of 4" title="Read it before it goes anywhere">
          <p>
            This is the letter exactly as it will be printed, and the address exactly as it will
            be written. Nothing has been sent and nothing has been charged.
          </p>
        </SectionHead>

        <div className="sheet-toolbar">
          <div className="btn-row">
            <button type="button" className="btn btn--secondary btn--sm" onClick={() => window.print()}>
              <PrintIcon size={16} /> Print or save as PDF
            </button>
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={() => downloadLetter(doc, suggestedFilename(address.city, address.zip))}
            >
              <DownloadIcon size={16} /> Download the letter
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={onEdit}>
              Change something
            </button>
          </div>
          <div className="sheet-toolbar__meta">
            <span>
              Template v{doc.contentVersion} · <span className="sheet-fingerprint">{fingerprint}</span>
            </span>
          </div>
        </div>
      </div>

      <div className="sheet-scroll">
        <LetterSheet doc={doc} />
      </div>

      <div className="no-print" style={{ marginTop: 'var(--space-6)' }}>
        <div style={{ maxWidth: '26rem', marginBottom: 'var(--space-6)' }}>
          <EnvelopePreview lines={['To the resident or property manager', ...formatAddressLines(address)]} />
        </div>

        {IS_DEMO ? (
          <DemoSendPanel onStartOver={onStartOver} />
        ) : (
          <LiveSendPanel
            address={address}
            observations={observations}
            note={note}
            suggestions={suggestions}
            fingerprint={fingerprint}
            dateIso={dateIso}
          />
        )}
      </div>
    </section>
  );
}

function DemoSendPanel({ onStartOver }: { onStartOver: () => void }) {
  return (
    <div className="panel">
      <h3>Mailing it</h3>
      <Callout tone="warm" title="This is the demo. No letter will be mailed.">
        <p>
          This build has no mailing service connected, so there is no button here that could send
          anything or charge anything — the option is absent rather than switched off.
        </p>
        <p style={{ marginBottom: 0 }}>
          You can still finish the job: use <strong>Print or save as PDF</strong> above, or{' '}
          <strong>Download the letter</strong> for a self-contained file you can open and print
          anywhere. Fold it into a standard envelope, address it as shown, and it is on its way.
        </p>
      </Callout>
      <div className="btn-row" style={{ marginTop: 'var(--space-5)' }}>
        <button type="button" className="btn btn--secondary" onClick={onStartOver}>
          Start a new letter
        </button>
        <Link to="/why-lighting-matters" className="btn btn--ghost">
          Read about light pollution
        </Link>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- side panel */

function SidePanel({
  address,
  doc,
}: {
  address: UsAddress;
  doc: ReturnType<typeof composeLetter>;
}) {
  const lines = address.line1 ? formatAddressLines(address) : [];

  return (
    <div className="panel panel--flat">
      <h3 style={{ fontSize: 'var(--step-1)' }}>The letter so far</h3>
      {lines.length > 0 ? (
        <p className="muted" style={{ fontSize: 'var(--step--1)' }}>
          Going to <strong style={{ color: 'var(--cream-100)' }}>{lines.join(', ')}</strong>
        </p>
      ) : (
        <p className="muted" style={{ fontSize: 'var(--step--1)' }}>
          Add an address and this fills in.
        </p>
      )}
      <div
        aria-hidden="true"
        style={{
          maxHeight: '18rem',
          overflow: 'hidden',
          borderRadius: 'var(--radius-sm)',
          maskImage: 'linear-gradient(180deg, #000 55%, transparent)',
          WebkitMaskImage: 'linear-gradient(180deg, #000 55%, transparent)',
        }}
      >
        <div style={{ transform: 'scale(0.52)', transformOrigin: 'top left', width: '192%' }}>
          <LetterSheet doc={doc} id="side-preview" />
        </div>
      </div>
      <p className="muted" style={{ fontSize: 'var(--step--1)', marginTop: 'var(--space-3)', marginBottom: 0 }}>
        Updates as you go. You will read the full letter before anything is sent.
      </p>
    </div>
  );
}
