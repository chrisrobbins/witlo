/**
 * Typed view over the shared letter content.
 *
 * `content/letter_content.json` is a synced copy of `/shared/letter_content.json`
 * (run `npm run sync:content` from `frontend/`, or `node scripts/sync-content.mjs`
 * from the repo root). The backend reads the same file. A parity test on each
 * side asserts the copies are identical, so the words on the printed page and
 * the words in the mailed letter can never drift apart.
 */
import raw from '../content/letter_content.json';

export type ObservationKey = 'all_night' | 'upward' | 'spill' | 'unused_area' | 'other';
export type SuggestionKey =
  | 'turn_off'
  | 'timer'
  | 'motion_sensor'
  | 'shield'
  | 'lower_brightness'
  | 'warmer_color';

export interface LabelledBullet {
  label: string;
  bullet: string;
}

export interface LetterContent {
  version: string;
  service: { name: string; url: string; opt_out_path: string };
  recipient_line: string;
  salutation: string;
  paragraphs: {
    opening: string;
    acknowledgment: string;
    explanation: string;
    closing: string;
  };
  observations_lead: string;
  observations_none: string;
  observations: Record<ObservationKey, LabelledBullet>;
  note_prefix: string;
  suggestions_lead: string;
  suggestions_lead_single: string;
  suggestions: Record<SuggestionKey, LabelledBullet>;
  signoff_line: string;
  signoff_name: string;
  mascot_caption: string;
  footer: string;
  limits: { note_max_chars: number; max_suggestions: number };
  order: { observations: ObservationKey[]; suggestions: SuggestionKey[] };
}

export const CONTENT = raw as unknown as LetterContent;

export const OBSERVATION_ORDER: ObservationKey[] = CONTENT.order.observations;
export const SUGGESTION_ORDER: SuggestionKey[] = CONTENT.order.suggestions;
export const NOTE_MAX_CHARS = CONTENT.limits.note_max_chars;
