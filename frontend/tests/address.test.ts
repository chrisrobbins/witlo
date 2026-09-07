import { describe, expect, it } from 'vitest';
import {
  formatAddressLines,
  formatAddressOneLine,
  isValidStateCode,
  isValidZip,
  normalizeAddressKey,
  US_STATES,
  type UsAddress,
} from '../src/lib/address';

/**
 * The same fixture table as `backend/tests/test_address.py`. Both
 * implementations must produce these exact keys — the address hash derived
 * from them is what enforces the do-not-mail list, so a divergence means a
 * suppressed address could receive a letter.
 */
const NORMALIZATION_CASES: Array<[UsAddress, string]> = [
  [
    { line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' },
    '414 W SAN ANTONIO ST||MARFA|TX|79843',
  ],
  [
    { line1: '  414   w. san antonio st. ', line2: '', city: ' marfa ', state: 'tx', zip: '79843-1234' },
    '414 W SAN ANTONIO ST||MARFA|TX|79843',
  ],
  [
    { line1: '9 Highland Ave', line2: 'Apt 4B', city: 'Somerville', state: 'MA', zip: '02143' },
    '9 HIGHLAND AVE|APT 4B|SOMERVILLE|MA|02143',
  ],
  [
    { line1: '9 Highland Ave', line2: 'apt. 4-b', city: 'Somerville', state: 'ma', zip: '02143' },
    '9 HIGHLAND AVE|APT 4 B|SOMERVILLE|MA|02143',
  ],
  [
    { line1: '1600 Amphitheatre Pkwy', line2: '', city: 'Mountain View', state: 'CA', zip: '94043-1351' },
    '1600 AMPHITHEATRE PKWY||MOUNTAIN VIEW|CA|94043',
  ],
];

describe('normalizeAddressKey', () => {
  it('matches the shared fixture table', () => {
    for (const [address, expected] of NORMALIZATION_CASES) {
      expect(normalizeAddressKey(address)).toBe(expected);
    }
  });

  it('ignores formatting differences', () => {
    const a: UsAddress = { line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' };
    const b: UsAddress = { line1: '414  w.  SAN antonio st.', line2: '', city: '  Marfa', state: 'tx', zip: '79843-0001' };
    expect(normalizeAddressKey(a)).toBe(normalizeAddressKey(b));
  });

  it('distinguishes different mailboxes', () => {
    const base: UsAddress = { line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' };
    const keys = new Set([
      normalizeAddressKey(base),
      normalizeAddressKey({ ...base, line1: '415 W San Antonio St' }),
      normalizeAddressKey({ ...base, line2: 'Apt 2' }),
    ]);
    expect(keys.size).toBe(3);
  });
});

describe('formatting', () => {
  it('omits an empty unit line and uppercases the state', () => {
    expect(
      formatAddressLines({ line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'tx', zip: '79843' }),
    ).toEqual(['414 W San Antonio St', 'Marfa, TX 79843']);
  });

  it('keeps a unit line when present', () => {
    expect(
      formatAddressLines({ line1: '9 Highland Ave', line2: 'Apt 4B', city: 'Somerville', state: 'MA', zip: '02143' }),
    ).toEqual(['9 Highland Ave', 'Apt 4B', 'Somerville, MA 02143']);
  });

  it('joins to one line for summaries', () => {
    expect(
      formatAddressOneLine({ line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' }),
    ).toBe('414 W San Antonio St, Marfa, TX 79843');
  });
});

describe('field checks', () => {
  it('accepts both ZIP forms and rejects the rest', () => {
    expect(isValidZip('79843')).toBe(true);
    expect(isValidZip('79843-1234')).toBe(true);
    expect(isValidZip('7984')).toBe(false);
    expect(isValidZip('79843-12')).toBe(false);
    expect(isValidZip('abcde')).toBe(false);
  });

  it('accepts every state and territory in the list', () => {
    for (const state of US_STATES) {
      expect(isValidStateCode(state.code)).toBe(true);
      expect(isValidStateCode(state.code.toLowerCase())).toBe(true);
    }
    expect(isValidStateCode('XX')).toBe(false);
    expect(isValidStateCode('TEXAS')).toBe(false);
  });
});
