import { describe, expect, it } from 'vitest';
import { validateSchema, validateReadOnly, validateEitherOr } from './validation';
import type { UISchema } from '../types/uiSchema';
import type { TemplateDefinition } from '../types/definition';

describe('validateSchema', () => {
  it('returns no errors for valid data', () => {
    const schema: UISchema = {
      type: 'object',
      properties: {
        name: { type: 'string' },
      },
    };
    expect(validateSchema(schema, { name: 'Alice' })).toEqual({});
  });

  it('reports required field errors', () => {
    const schema: UISchema = {
      type: 'object',
      required: ['name'],
      properties: {
        name: { type: 'string' },
      },
    };
    const errors = validateSchema(schema, { name: '' });
    expect(errors['name']).toBe('Required');
  });

  it('validates enum values', () => {
    const schema: UISchema = {
      type: 'string',
      enum: ['red', 'blue'],
    };
    expect(validateSchema(schema, 'green')).toEqual({ '': 'Invalid value' });
    expect(validateSchema(schema, 'red')).toEqual({});
  });

  it('validates pattern', () => {
    const schema: UISchema = {
      type: 'string',
      pattern: '^[A-Z]{3}$',
    };
    expect(validateSchema(schema, 'abc')).toEqual({ '': 'Invalid format' });
    expect(validateSchema(schema, 'ABC')).toEqual({});
  });

  it('validates number range', () => {
    const schema: UISchema = {
      type: 'number',
      minimum: 0,
      maximum: 100,
    };
    expect(validateSchema(schema, -1)).toEqual({ '': expect.stringContaining('0') });
    expect(validateSchema(schema, 101)).toEqual({ '': expect.stringContaining('100') });
    expect(validateSchema(schema, 50)).toEqual({});
  });

  it('validates x-range cross-field min <= max', () => {
    const schema: UISchema = {
      'x-range': true,
    } as UISchema;
    expect(validateSchema(schema, { min: 100, max: 10 })).toEqual({
      '': 'Min cannot exceed max',
    });
    expect(validateSchema(schema, { min: 10, max: 100 })).toEqual({});
  });

  it('validates x-multi-language required languages', () => {
    const schema: UISchema = {
      'x-multi-language': true,
      'x-required-languages': ['en'],
    } as UISchema;
    expect(validateSchema(schema, { de: 'Hallo' })).toEqual({
      '': 'Missing required languages: en',
    });
    expect(validateSchema(schema, { en: 'Hello' })).toEqual({});
  });

  it('validates nested objects recursively', () => {
    const schema: UISchema = {
      type: 'object',
      properties: {
        address: {
          type: 'object',
          required: ['city'],
          properties: {
            city: { type: 'string' },
          },
        },
      },
    };
    const errors = validateSchema(schema, { address: { city: '' } });
    expect(errors['address.city']).toBe('Required');
  });

  it('validates array minItems', () => {
    const schema: UISchema = {
      type: 'array',
      minItems: 1,
      items: { type: 'string' },
    };
    expect(validateSchema(schema, [])).toEqual({
      '': 'At least 1 item(s) required',
    });
    expect(validateSchema(schema, ['item'])).toEqual({});
  });

  it('returns empty for undefined schema', () => {
    expect(validateSchema(undefined, 'anything')).toEqual({});
  });

  it('enforces x-edit-id-short=false for dynamic keys', () => {
    const schema: UISchema = {
      type: 'object',
      properties: { fixed: { type: 'string' } },
      'x-edit-id-short': false,
    };
    const errors = validateSchema(schema, { fixed: 'ok', dynamicKey: 'x' });
    expect(errors['dynamicKey']).toContain('not editable');
  });

  it('enforces x-allowed-id-short patterns for dynamic keys', () => {
    const schema: UISchema = {
      type: 'object',
      properties: {},
      'x-edit-id-short': true,
      'x-allowed-id-short': ['PCF{00}', 'PCF{01}'],
    };
    const errors = validateSchema(schema, { PCF00: 1, WrongKey: 2 });
    expect(errors['WrongKey']).toContain('not allowed');
    expect(errors['PCF00']).toBeUndefined();
  });

  it('enforces x-naming=idShort for dynamic keys', () => {
    const schema: UISchema = {
      type: 'object',
      properties: {},
      'x-edit-id-short': true,
      'x-naming': 'idShort',
    };
    const errors = validateSchema(schema, { valid_Id: 1, 'not-valid': 2 });
    expect(errors['not-valid']).toContain('violates naming rule');
    expect(errors['valid_Id']).toBeUndefined();
  });
});

describe('validateReadOnly', () => {
  it('reports error when read-only field is modified', () => {
    const schema: UISchema = { type: 'string', readOnly: true };
    const errors = validateReadOnly(schema, 'changed', 'original');
    expect(errors['']).toBe('Read-only field cannot be modified');
  });

  it('no error when read-only field is unchanged', () => {
    const schema: UISchema = { type: 'string', readOnly: true };
    expect(validateReadOnly(schema, 'same', 'same')).toEqual({});
  });

  it('recurses into object properties', () => {
    const schema: UISchema = {
      type: 'object',
      properties: {
        locked: { type: 'string', readOnly: true },
        editable: { type: 'string' },
      },
    };
    const errors = validateReadOnly(
      schema,
      { locked: 'modified', editable: 'changed' },
      { locked: 'original', editable: 'old' },
    );
    expect(errors['locked']).toBe('Read-only field cannot be modified');
    expect(errors['editable']).toBeUndefined();
  });

  it('returns empty for undefined schema', () => {
    expect(validateReadOnly(undefined, 'a', 'b')).toEqual({});
  });
});

describe('validateEitherOr', () => {
  it('returns no errors when no groups', () => {
    expect(validateEitherOr(undefined, {})).toEqual([]);
  });

  it('reports error when no member of group has a value', () => {
    const def: TemplateDefinition = {
      submodel: {
        idShort: 'Root',
        elements: [
          {
            modelType: 'Property',
            idShort: 'fieldA',
            path: 'Root/fieldA',
            smt: { either_or: 'group1' },
          },
          {
            modelType: 'Property',
            idShort: 'fieldB',
            path: 'Root/fieldB',
            smt: { either_or: 'group1' },
          },
        ],
      },
    };
    const errors = validateEitherOr(def, { fieldA: '', fieldB: '' });
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('group1');
  });

  it('passes when at least one member has a value', () => {
    const def: TemplateDefinition = {
      submodel: {
        idShort: 'Root',
        elements: [
          {
            modelType: 'Property',
            idShort: 'fieldA',
            path: 'Root/fieldA',
            smt: { either_or: 'group1' },
          },
          {
            modelType: 'Property',
            idShort: 'fieldB',
            path: 'Root/fieldB',
            smt: { either_or: 'group1' },
          },
        ],
      },
    };
    const errors = validateEitherOr(def, { fieldA: 'has value', fieldB: '' });
    expect(errors).toHaveLength(0);
  });
});
