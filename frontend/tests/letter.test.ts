import { describe, expect, it } from 'vitest';
import expected from '../../scripts/parity-expected.json';
import inputs from '../../scripts/parity-inputs.json';
import sharedContent from '../../shared/letter_content.json';
import localContent from '../src/content/letter_content.json';
import {
  composeLetter,
  formatLetterDate,
  letterFingerprint,
  sanitizeNote,
  todayIso,
} from '../src/lib/letter';
import { CONTENT, NOTE_MAX_CHARS } from '../src/lib/letterContent';
import type { ObservationKey, SuggestionKey } from '../src/lib/letterContent';

const ADDRESS = {
  line1: '414 W San Antonio St',
  line2: '',
  city: 'Marfa',
  state: 'TX',
  zip: '79843',
};

function compose(overrides: {
  observations?: ObservationKey[];
  note?: string;
  suggestions?: SuggestionKey[];
} = {}) {
  return composeLetter({
    address: ADDRESS,
    observations: overrides.observations ?? [],
    note: overrides.note ?? '',
    suggestions: overrides.suggestions ?? [],
    dateIso: '2026-09-07',
  });
}

describe('the shared letter content', () => {
  it('is byte-identical to the copy the backend reads', () => {
    // If this fails, run: node scripts/sync-content.mjs
    expect(JSON.stringify(localContent)).toBe(JSON.stringify(sharedContent));
  });
});

describe('composeLetter', () => {
  it('orders selections by the template, not by click order', () => {
    const a = compose({ suggestions: ['warmer_color', 'shield', 'turn_off'] });
    const b = compose({ suggestions: ['turn_off', 'shield', 'warmer_color'] });
    expect(a.plainText).toBe(b.plainText);
  });

  it('uses the neutral sentence when nothing was observed', () => {
    const doc = compose();
    expect(doc.plainText).toContain(CONTENT.observations_none);
    expect(doc.plainText).not.toContain(CONTENT.observations_lead);
  });

  it('omits the suggestions block entirely when none are chosen', () => {
    const doc = compose({ observations: ['all_night'] });
    expect(doc.plainText).not.toContain(CONTENT.suggestions_lead);
    expect(doc.plainText).not.toContain(CONTENT.suggestions_lead_single);
  });

  it('switches to the singular lead for exactly one suggestion', () => {
    expect(compose({ suggestions: ['shield'] }).plainText).toContain(
      CONTENT.suggestions_lead_single,
    );
    expect(compose({ suggestions: ['shield', 'timer'] }).plainText).toContain(
      CONTENT.suggestions_lead,
    );
  });

  it('never invents a recipient name', () => {
    const doc = compose();
    expect(doc.recipientLines[0]).toBe(CONTENT.recipient_line);
    expect(doc.plainText).not.toContain('Dear ');
  });

  it('never carries contact details for the sender', () => {
    const text = compose({ observations: ['all_night'], suggestions: ['shield'] }).plainText;
    expect(text).not.toContain('@');
    expect(text).not.toMatch(/\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/);
  });

  it('avoids enforcement language even with everything selected', () => {
    const text = compose({
      observations: ['all_night', 'upward', 'spill', 'unused_area'],
      suggestions: ['turn_off', 'timer', 'motion_sensor', 'shield', 'lower_brightness', 'warmer_color'],
    }).plainText.toLowerCase();
    for (const word of ['illegal', 'violation', 'ordinance', 'police', 'penalty', 'citation']) {
      expect(text).not.toContain(word);
    }
  });

  it('is deterministic', () => {
    const a = compose({ observations: ['spill'], suggestions: ['timer'] });
    const b = compose({ observations: ['spill'], suggestions: ['timer'] });
    expect(a.plainText).toBe(b.plainText);
    expect(letterFingerprint(a.plainText)).toBe(letterFingerprint(b.plainText));
  });

  it('changes its fingerprint when any input changes', () => {
    const base = letterFingerprint(compose({ observations: ['all_night'] }).plainText);
    expect(letterFingerprint(compose({ observations: ['upward'] }).plainText)).not.toBe(base);
    expect(
      letterFingerprint(compose({ observations: ['all_night'], suggestions: ['shield'] }).plainText),
    ).not.toBe(base);
  });
});

describe('sanitizeNote', () => {
  it('removes markup rather than escaping it', () => {
    expect(sanitizeNote('It <b>shines</b> in')).toBe('It b shines /b in');
  });

  it('collapses whitespace and control characters', () => {
    expect(sanitizeNote('a\t\tb\n\nc')).toBe('a b c');
    expect(sanitizeNote('  \n\t ')).toBe('');
  });

  it('truncates at the published limit', () => {
    expect(sanitizeNote('x'.repeat(NOTE_MAX_CHARS + 50))).toHaveLength(NOTE_MAX_CHARS);
  });
});

describe('formatLetterDate', () => {
  it('is locale-independent', () => {
    expect(formatLetterDate('2026-09-07')).toBe('September 7, 2026');
    expect(formatLetterDate('2026-01-01')).toBe('January 1, 2026');
    expect(formatLetterDate('nope')).toBe('nope');
  });

  it('todayIso produces a parseable date', () => {
    expect(todayIso(new Date(2026, 8, 7))).toBe('2026-09-07');
  });
});

describe('parity with the Python composer', () => {
  it('matches every shared fixture', () => {
    for (const fixture of expected) {
      const input = inputs.find((i) => i.name === fixture.name);
      expect(input, `missing input for ${fixture.name}`).toBeTruthy();
      const doc = composeLetter({
        address: input!.address,
        observations: input!.observations as ObservationKey[],
        note: input!.note,
        suggestions: input!.suggestions as SuggestionKey[],
        dateIso: input!.dateIso,
      });
      expect(doc.plainText, fixture.name).toBe(fixture.plainText);
      expect(letterFingerprint(doc.plainText), fixture.name).toBe(fixture.fingerprint);
    }
  });
});
