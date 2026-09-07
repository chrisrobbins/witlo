/**
 * US address handling.
 *
 * `normalizeAddressKey` must stay byte-identical to
 * `backend/app/letters/address.py::normalize_address_key`. It is the input to
 * the address hash used for the repeat-letter cooldown and the do-not-mail
 * suppression list, so a mismatch between the two implementations would let a
 * suppressed address through. `tests/address.test.ts` and the backend's
 * `test_address.py` run the same fixture table.
 */

export interface UsAddress {
  line1: string;
  line2: string;
  city: string;
  state: string;
  zip: string;
}

export const EMPTY_ADDRESS: UsAddress = { line1: '', line2: '', city: '', state: '', zip: '' };

export const US_STATES: ReadonlyArray<{ code: string; name: string }> = [
  { code: 'AL', name: 'Alabama' }, { code: 'AK', name: 'Alaska' }, { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' }, { code: 'CA', name: 'California' }, { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' }, { code: 'DE', name: 'Delaware' }, { code: 'DC', name: 'District of Columbia' },
  { code: 'FL', name: 'Florida' }, { code: 'GA', name: 'Georgia' }, { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' }, { code: 'IL', name: 'Illinois' }, { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' }, { code: 'KS', name: 'Kansas' }, { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' }, { code: 'ME', name: 'Maine' }, { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' }, { code: 'MI', name: 'Michigan' }, { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' }, { code: 'MO', name: 'Missouri' }, { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' }, { code: 'NV', name: 'Nevada' }, { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' }, { code: 'NM', name: 'New Mexico' }, { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' }, { code: 'ND', name: 'North Dakota' }, { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' }, { code: 'OR', name: 'Oregon' }, { code: 'PA', name: 'Pennsylvania' },
  { code: 'PR', name: 'Puerto Rico' }, { code: 'RI', name: 'Rhode Island' }, { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' }, { code: 'TN', name: 'Tennessee' }, { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' }, { code: 'VT', name: 'Vermont' }, { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' }, { code: 'WV', name: 'West Virginia' }, { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' },
];

const STATE_CODES = new Set(US_STATES.map((s) => s.code));

/** Uppercase, strip everything that is not A–Z/0–9/space, collapse whitespace. */
function squash(value: string): string {
  return value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

/**
 * A stable key for "this is the same mailbox". Deliberately conservative: it
 * does not attempt USPS standardisation (the server does that through the mail
 * provider), it only removes formatting noise.
 */
export function normalizeAddressKey(address: UsAddress): string {
  const zip5 = squash(address.zip).replace(/\s/g, '').slice(0, 5);
  return [
    squash(address.line1),
    squash(address.line2),
    squash(address.city),
    squash(address.state).slice(0, 2),
    zip5,
  ].join('|');
}

export function isValidStateCode(value: string): boolean {
  return STATE_CODES.has(value.trim().toUpperCase());
}

/** Accepts 12345 or 12345-6789. */
export function isValidZip(value: string): boolean {
  return /^\d{5}(-\d{4})?$/.test(value.trim());
}

/** The address block as printed on the letter, top to bottom. */
export function formatAddressLines(address: UsAddress): string[] {
  const lines: string[] = [address.line1.trim()];
  if (address.line2.trim()) lines.push(address.line2.trim());
  const state = address.state.trim().toUpperCase();
  lines.push(`${address.city.trim()}, ${state} ${address.zip.trim()}`);
  return lines.filter((l) => l.length > 0);
}

/** Single-line form, for compact summaries in the UI. */
export function formatAddressOneLine(address: UsAddress): string {
  return formatAddressLines(address).join(', ');
}
