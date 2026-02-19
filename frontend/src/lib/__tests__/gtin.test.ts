import { describe, expect, it } from 'vitest';
import { computeGTINCheckDigit, validateGTIN } from '../gtin';

describe('computeGTINCheckDigit', () => {
  it('computes check digit for GTIN-13 payload', () => {
    expect(computeGTINCheckDigit('400638133393')).toBe('1');
  });

  it('computes check digit for GTIN-8 payload', () => {
    // GTIN-8 96385074: payload 9638507 → check digit 4
    expect(computeGTINCheckDigit('9638507')).toBe('4');
  });

  it('computes check digit for GTIN-14 payload', () => {
    expect(computeGTINCheckDigit('1234567890123')).toBe('1');
  });
});

describe('validateGTIN', () => {
  it('validates a correct GTIN-13', () => {
    expect(validateGTIN('4006381333931')).toBe(true);
  });

  it('validates a correct GTIN-8', () => {
    expect(validateGTIN('96385074')).toBe(true);
  });

  it('rejects GTIN with wrong check digit', () => {
    expect(validateGTIN('4006381333932')).toBe(false);
  });

  it('rejects GTIN with invalid length', () => {
    expect(validateGTIN('12345')).toBe(false);
  });

  it('strips non-digit characters before validating', () => {
    expect(validateGTIN('4006-3813-3393-1')).toBe(true);
  });

  it('rejects empty string', () => {
    expect(validateGTIN('')).toBe(false);
  });
});
