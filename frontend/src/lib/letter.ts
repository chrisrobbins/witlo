/**
 * Deterministic letter composition. No network, no LLM, no randomness.
 *
 * The Python implementation in `backend/app/letters/composer.py` mirrors this
 * file exactly. `scripts/parity-fixtures.json` holds the shared fixture table
 * that both test suites assert against, so the preview a sender approves in the
 * browser is provably the letter the server prints.
 */
import {
  CONTENT,
  NOTE_MAX_CHARS,
  OBSERVATION_ORDER,
  SUGGESTION_ORDER,
  type ObservationKey,
  type SuggestionKey,
} from './letterContent';
import { formatAddressLines, type UsAddress } from './address';

export interface LetterInput {
  address: UsAddress;
  observations: ObservationKey[];
  /** Free text for the "something else" observation. Already validated. */
  note: string;
  suggestions: SuggestionKey[];
  /** ISO date (YYYY-MM-DD) the letter is dated. */
  dateIso: string;
}

export type LetterBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; lead: string; items: string[] };

export interface LetterDocument {
  contentVersion: string;
  date: string;
  recipientLines: string[];
  salutation: string;
  blocks: LetterBlock[];
  signoffLine: string;
  signoffName: string;
  mascotCaption: string;
  footer: string;
  plainText: string;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** "2026-09-07" -> "September 7, 2026". Locale-independent on purpose. */
export function formatLetterDate(dateIso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateIso.trim());
  if (!m) return dateIso;
  const year = Number(m[1]);
  const monthIndex = Number(m[2]) - 1;
  const day = Number(m[3]);
  const month = MONTHS[monthIndex] ?? m[2];
  return `${month} ${day}, ${year}`;
}

export function todayIso(now: Date = new Date()): string {
  const y = now.getFullYear();
  const mo = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${mo}-${d}`;
}

/**
 * Sanitize the optional note. Control characters and anything that reads as
 * markup are removed rather than escaped, because this string is printed onto
 * paper as well as rendered in HTML. Returns '' if nothing usable is left.
 */
export function sanitizeNote(raw: string): string {
  const collapsed = raw
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001F\u007F-\u009F]/g, ' ')
    .replace(/[<>{}\\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (collapsed.length === 0) return '';
  return collapsed.slice(0, NOTE_MAX_CHARS);
}

function orderedObservations(selected: ObservationKey[]): ObservationKey[] {
  const set = new Set(selected);
  return OBSERVATION_ORDER.filter((k) => set.has(k));
}

function orderedSuggestions(selected: SuggestionKey[]): SuggestionKey[] {
  const set = new Set(selected);
  return SUGGESTION_ORDER.filter((k) => set.has(k));
}

export function composeLetter(input: LetterInput): LetterDocument {
  const observations = orderedObservations(input.observations);
  const suggestions = orderedSuggestions(input.suggestions);
  const note = sanitizeNote(input.note);

  const observationItems: string[] = observations.map((key) => CONTENT.observations[key].bullet);
  if (note) observationItems.push(`${CONTENT.note_prefix}${note}`);

  const blocks: LetterBlock[] = [];
  blocks.push({ kind: 'paragraph', text: CONTENT.paragraphs.opening });

  if (observationItems.length > 0) {
    blocks.push({ kind: 'list', lead: CONTENT.observations_lead, items: observationItems });
  } else {
    blocks.push({ kind: 'paragraph', text: CONTENT.observations_none });
  }

  blocks.push({ kind: 'paragraph', text: CONTENT.paragraphs.acknowledgment });
  blocks.push({ kind: 'paragraph', text: CONTENT.paragraphs.explanation });

  if (suggestions.length > 0) {
    blocks.push({
      kind: 'list',
      lead: suggestions.length === 1 ? CONTENT.suggestions_lead_single : CONTENT.suggestions_lead,
      items: suggestions.map((key) => CONTENT.suggestions[key].bullet),
    });
  }

  blocks.push({ kind: 'paragraph', text: CONTENT.paragraphs.closing });

  const doc: Omit<LetterDocument, 'plainText'> = {
    contentVersion: CONTENT.version,
    date: formatLetterDate(input.dateIso),
    recipientLines: [CONTENT.recipient_line, ...formatAddressLines(input.address)],
    salutation: CONTENT.salutation,
    blocks,
    signoffLine: CONTENT.signoff_line,
    signoffName: CONTENT.signoff_name,
    mascotCaption: CONTENT.mascot_caption,
    footer: CONTENT.footer,
  };

  return { ...doc, plainText: renderPlainText(doc) };
}

/** The canonical text form. Hashed for preview/send integrity checks. */
export function renderPlainText(doc: Omit<LetterDocument, 'plainText'>): string {
  const parts: string[] = [];
  parts.push(doc.date);
  parts.push('');
  parts.push(doc.recipientLines.join('\n'));
  parts.push('');
  parts.push(doc.salutation);
  parts.push('');
  for (const block of doc.blocks) {
    if (block.kind === 'paragraph') {
      parts.push(block.text);
    } else {
      parts.push(block.lead);
      for (const item of block.items) parts.push(`  - ${item}`);
    }
    parts.push('');
  }
  parts.push(doc.signoffLine);
  parts.push(doc.signoffName);
  parts.push('');
  parts.push(doc.mascotCaption);
  parts.push('');
  parts.push('---');
  parts.push(doc.footer);
  return parts.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

/**
 * FNV-1a 32-bit, rendered as 8 hex chars. Not a security primitive — it is a
 * cheap change-detector so the UI can prove the preview and the submission
 * describe the same letter. The server independently recomposes and compares.
 */
export function letterFingerprint(plainText: string): string {
  const bytes = new TextEncoder().encode(plainText);
  let hash = 0x811c9dc5;
  for (let i = 0; i < bytes.length; i += 1) {
    hash ^= bytes[i] as number;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}
