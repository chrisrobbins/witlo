/**
 * Client-side validation. Convenience only — the server revalidates everything
 * it is willing to act on. Messages are written to be read aloud by a screen
 * reader without sounding like an error dialog.
 */
import { isValidStateCode, isValidZip, type UsAddress } from './address';
import { NOTE_MAX_CHARS } from './letterContent';
import { sanitizeNote } from './letter';

export type FieldErrors = Partial<Record<keyof UsAddress | 'note' | 'email' | 'confirm', string>>;

const PO_BOX = /\b(p\.?\s?o\.?\s?box|post\s+office\s+box)\b/i;

export function validateAddress(address: UsAddress): FieldErrors {
  const errors: FieldErrors = {};

  const line1 = address.line1.trim();
  if (line1.length === 0) {
    errors.line1 = 'Please enter the street address of the property.';
  } else if (line1.length < 4) {
    errors.line1 = 'That looks a little short for a street address.';
  } else if (!/\d/.test(line1)) {
    errors.line1 = 'A US street address usually starts with a number.';
  } else if (PO_BOX.test(line1)) {
    errors.line1 = 'A PO box has no outdoor light. Please use the street address of the property.';
  }

  if (address.line2.trim().length > 60) {
    errors.line2 = 'Please keep the unit or suite line under 60 characters.';
  }

  const city = address.city.trim();
  if (city.length === 0) {
    errors.city = 'Please enter the city.';
  } else if (city.length < 2) {
    errors.city = 'Please enter the full city name.';
  }

  const state = address.state.trim();
  if (state.length === 0) {
    errors.state = 'Please choose the state.';
  } else if (!isValidStateCode(state)) {
    errors.state = 'Please choose a US state or territory from the list.';
  }

  const zip = address.zip.trim();
  if (zip.length === 0) {
    errors.zip = 'Please enter the ZIP code.';
  } else if (!isValidZip(zip)) {
    errors.zip = 'Please enter a ZIP code as 12345 or 12345-6789.';
  }

  return errors;
}

export function validateNote(note: string): string | undefined {
  const trimmed = note.trim();
  if (trimmed.length === 0) return undefined;
  if (trimmed.length > NOTE_MAX_CHARS) {
    return `Please keep this under ${NOTE_MAX_CHARS} characters.`;
  }
  if (sanitizeNote(trimmed).length === 0) {
    return 'Please use plain words here.';
  }
  // Keep the letter free of anything that reads as a threat or a demand.
  const discouraged = /\b(illegal|violation|report(ed|ing)?\s+(you|this)|police|lawsuit|sue|fine[sd]?|code\s+enforcement|ordinance)\b/i;
  if (discouraged.test(trimmed)) {
    return 'This letter is a friendly request, so it avoids legal or enforcement language. Please rephrase, or leave this blank.';
  }
  if (/\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/.test(trimmed) || /@/.test(trimmed)) {
    return 'Please leave out phone numbers and email addresses — the letter does not share contact details.';
  }
  return undefined;
}

export function isValidEmail(value: string): boolean {
  const v = value.trim();
  if (v.length === 0) return false;
  if (v.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some((v) => typeof v === 'string' && v.length > 0);
}
