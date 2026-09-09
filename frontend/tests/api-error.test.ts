/**
 * The API returns two error shapes: `{code, detail}` for validation failures
 * and `{detail: {code, detail}}` for everything else (FastAPI's HTTPException
 * envelope). `apiErrorFrom` has to unwrap both, or a sender sees `[object
 * Object]` instead of the sentence the server wrote.
 */
import { describe, expect, it } from 'vitest';
import { ApiError, apiErrorFrom } from '../src/lib/api';

describe('apiErrorFrom', () => {
  it('reads a flat validation error body', () => {
    const err = apiErrorFrom(422, { code: 'invalid_request', detail: 'Check the note field.' });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe('invalid_request');
    expect(err.message).toBe('Check the note field.');
  });

  it('unwraps a nested HTTPException body instead of stringifying the object', () => {
    const err = apiErrorFrom(409, {
      detail: {
        code: 'stale_date',
        detail: 'The date on this letter is too far from today.',
      },
    });
    expect(err.code).toBe('stale_date');
    expect(err.message).toBe('The date on this letter is too far from today.');
    expect(err.message).not.toContain('[object Object]');
  });

  it('falls back to a status message when the body has no usable detail', () => {
    expect(apiErrorFrom(500, null).message).toBe('The server responded with 500.');
    expect(apiErrorFrom(502, { detail: {} }).message).toBe('The server responded with 502.');
    expect(apiErrorFrom(400, 'plain string').message).toBe('The server responded with 400.');
  });
});
