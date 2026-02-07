import { describe, expect, it } from 'vitest';
import { defaultValueForSchema } from './formDefaults';
import type { UISchema } from '../types/uiSchema';

describe('defaultValueForSchema', () => {
  it('returns empty string for undefined schema', () => {
    expect(defaultValueForSchema(undefined)).toBe('');
  });

  it('uses explicit default if provided', () => {
    expect(defaultValueForSchema({ type: 'string', default: 'hello' })).toBe('hello');
  });

  it('returns first enum value for enum schema', () => {
    expect(defaultValueForSchema({ type: 'string', enum: ['a', 'b', 'c'] })).toBe('a');
  });

  it('returns empty object for multi-language', () => {
    expect(defaultValueForSchema({ 'x-multi-language': true } as UISchema)).toEqual({});
  });

  it('returns range default for x-range', () => {
    expect(defaultValueForSchema({ 'x-range': true } as UISchema)).toEqual({
      min: null,
      max: null,
    });
  });

  it('returns file default for x-file-upload', () => {
    expect(defaultValueForSchema({ 'x-file-upload': true } as UISchema)).toEqual({
      contentType: '',
      value: '',
    });
  });

  it('returns reference default for x-reference', () => {
    expect(defaultValueForSchema({ 'x-reference': true } as UISchema)).toEqual({
      type: 'ModelReference',
      keys: [],
    });
  });

  it('returns entity default for x-entity', () => {
    expect(defaultValueForSchema({ 'x-entity': true } as UISchema)).toEqual({
      entityType: 'SelfManagedEntity',
      globalAssetId: '',
      statements: {},
    });
  });

  it('returns relationship default for x-relationship', () => {
    expect(defaultValueForSchema({ 'x-relationship': true } as UISchema)).toEqual({
      first: null,
      second: null,
    });
  });

  it('returns annotated-relationship default', () => {
    expect(
      defaultValueForSchema({ 'x-annotated-relationship': true } as UISchema),
    ).toEqual({
      first: null,
      second: null,
      annotations: {},
    });
  });

  it('returns empty object for object type', () => {
    expect(defaultValueForSchema({ type: 'object' })).toEqual({});
  });

  it('returns empty array for array type', () => {
    expect(defaultValueForSchema({ type: 'array' })).toEqual([]);
  });

  it('returns null for number type', () => {
    expect(defaultValueForSchema({ type: 'number' })).toBeNull();
  });

  it('returns null for integer type', () => {
    expect(defaultValueForSchema({ type: 'integer' })).toBeNull();
  });

  it('returns false for boolean type', () => {
    expect(defaultValueForSchema({ type: 'boolean' })).toBe(false);
  });

  it('returns empty string for string type', () => {
    expect(defaultValueForSchema({ type: 'string' })).toBe('');
  });
});
