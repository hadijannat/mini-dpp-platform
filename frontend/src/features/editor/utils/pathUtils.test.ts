import { describe, expect, it } from 'vitest';
import {
  pathToKey,
  getValueAtPath,
  setValueAtPath,
  isEmptyValue,
  deepEqual,
  pickLangValue,
  getNodeLabel,
  getNodeDescription,
  isNodeRequired,
  extractSemanticId,
  getSchemaAtPath,
  definitionPathToSegments,
  getValuesAtPattern,
} from './pathUtils';
import type { DefinitionNode } from '../types/definition';
import type { UISchema } from '../types/uiSchema';

describe('pathToKey', () => {
  it('joins segments with dots', () => {
    expect(pathToKey(['a', 'b', 'c'])).toBe('a.b.c');
  });

  it('converts numbers to strings', () => {
    expect(pathToKey(['items', 0, 'name'])).toBe('items.0.name');
  });

  it('returns empty string for empty array', () => {
    expect(pathToKey([])).toBe('');
  });
});

describe('getValueAtPath', () => {
  const data = { a: { b: { c: 42 } }, items: [10, 20, 30] };

  it('traverses nested objects', () => {
    expect(getValueAtPath(data, ['a', 'b', 'c'])).toBe(42);
  });

  it('traverses arrays by index', () => {
    expect(getValueAtPath(data, ['items', 1])).toBe(20);
  });

  it('returns undefined for missing paths', () => {
    expect(getValueAtPath(data, ['a', 'x', 'y'])).toBeUndefined();
  });

  it('returns the root for empty path', () => {
    expect(getValueAtPath(data, [])).toBe(data);
  });

  it('returns undefined when data is null', () => {
    expect(getValueAtPath(null, ['a'])).toBeUndefined();
  });
});

describe('setValueAtPath', () => {
  it('sets a nested value immutably', () => {
    const data = { a: { b: 1 } };
    const result = setValueAtPath(data, ['a', 'b'], 2);
    expect(result).toEqual({ a: { b: 2 } });
    expect(data.a.b).toBe(1); // original unchanged
  });

  it('creates intermediate objects', () => {
    const result = setValueAtPath({}, ['a', 'b'], 'hello');
    expect(result).toEqual({ a: { b: 'hello' } });
  });

  it('creates intermediate arrays for numeric keys', () => {
    const result = setValueAtPath({}, ['items', 0], 'first');
    expect(result).toEqual({ items: ['first'] });
  });

  it('returns data unchanged for empty path', () => {
    const data = { x: 1 };
    expect(setValueAtPath(data, [], 'ignored')).toBe(data);
  });
});

describe('isEmptyValue', () => {
  it.each([
    [null, true],
    [undefined, true],
    ['', true],
    ['  ', true],
    [[], true],
    [{}, true],
    ['hello', false],
    [0, false],
    [false, false],
    [[1], false],
    [{ a: 1 }, false],
  ])('isEmptyValue(%j) === %s', (value, expected) => {
    expect(isEmptyValue(value)).toBe(expected);
  });
});

describe('deepEqual', () => {
  it('compares primitives', () => {
    expect(deepEqual(1, 1)).toBe(true);
    expect(deepEqual('a', 'b')).toBe(false);
  });

  it('compares nested objects', () => {
    expect(deepEqual({ a: { b: 1 } }, { a: { b: 1 } })).toBe(true);
    expect(deepEqual({ a: 1 }, { a: 2 })).toBe(false);
  });

  it('compares arrays', () => {
    expect(deepEqual([1, 2, 3], [1, 2, 3])).toBe(true);
    expect(deepEqual([1, 2], [1, 2, 3])).toBe(false);
  });

  it('handles null', () => {
    expect(deepEqual(null, null)).toBe(true);
    expect(deepEqual(null, {})).toBe(false);
  });

  it('detects type mismatches', () => {
    expect(deepEqual('1', 1)).toBe(false);
  });
});

describe('pickLangValue', () => {
  it('prefers English', () => {
    expect(pickLangValue({ en: 'hello', de: 'hallo' })).toBe('hello');
  });

  it('falls back to first value', () => {
    expect(pickLangValue({ de: 'hallo', fr: 'bonjour' })).toBe('hallo');
  });

  it('returns undefined for undefined input', () => {
    expect(pickLangValue(undefined)).toBeUndefined();
  });

  it('returns undefined for empty object', () => {
    expect(pickLangValue({})).toBeUndefined();
  });
});

describe('getNodeLabel', () => {
  it('prefers smt.form_title', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'test',
      smt: { form_title: 'Custom Title' },
    };
    expect(getNodeLabel(node, 'fallback')).toBe('Custom Title');
  });

  it('falls back to displayName.en', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'test',
      displayName: { en: 'Display Name' },
    };
    expect(getNodeLabel(node, 'fallback')).toBe('Display Name');
  });

  it('falls back to idShort', () => {
    const node: DefinitionNode = { modelType: 'Property', idShort: 'MyField' };
    expect(getNodeLabel(node, 'fallback')).toBe('MyField');
  });

  it('falls back to provided fallback', () => {
    const node: DefinitionNode = { modelType: 'Property' };
    expect(getNodeLabel(node, 'lastResort')).toBe('lastResort');
  });
});

describe('getNodeDescription', () => {
  it('prefers smt.form_info', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      smt: { form_info: 'Info text' },
    };
    expect(getNodeDescription(node)).toBe('Info text');
  });

  it('falls back to description', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      description: { en: 'Description' },
    };
    expect(getNodeDescription(node)).toBe('Description');
  });

  it('returns undefined when neither is available', () => {
    const node: DefinitionNode = { modelType: 'Property' };
    expect(getNodeDescription(node)).toBeUndefined();
  });
});

describe('isNodeRequired', () => {
  it('returns true for cardinality One', () => {
    const node: DefinitionNode = { modelType: 'Property', smt: { cardinality: 'One' } };
    expect(isNodeRequired(node)).toBe(true);
  });

  it('returns true for cardinality OneToMany', () => {
    const node: DefinitionNode = { modelType: 'Property', smt: { cardinality: 'OneToMany' } };
    expect(isNodeRequired(node)).toBe(true);
  });

  it('returns false for ZeroToMany', () => {
    const node: DefinitionNode = { modelType: 'Property', smt: { cardinality: 'ZeroToMany' } };
    expect(isNodeRequired(node)).toBe(false);
  });

  it('returns false when no smt', () => {
    const node: DefinitionNode = { modelType: 'Property' };
    expect(isNodeRequired(node)).toBe(false);
  });
});

describe('extractSemanticId', () => {
  it('extracts value from AAS semanticId structure', () => {
    const submodel = {
      semanticId: { keys: [{ type: 'GlobalReference', value: 'urn:example:1.0' }] },
    };
    expect(extractSemanticId(submodel)).toBe('urn:example:1.0');
  });

  it('returns null for missing keys', () => {
    expect(extractSemanticId({})).toBeNull();
    expect(extractSemanticId({ semanticId: {} })).toBeNull();
    expect(extractSemanticId({ semanticId: { keys: [] } })).toBeNull();
  });
});

describe('getSchemaAtPath', () => {
  const schema: UISchema = {
    type: 'object',
    properties: {
      name: { type: 'string' },
      address: {
        type: 'object',
        properties: {
          city: { type: 'string' },
        },
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
      },
    },
  };

  it('resolves nested object properties', () => {
    expect(getSchemaAtPath(schema, ['address', 'city'])).toEqual({ type: 'string' });
  });

  it('resolves array items by numeric index', () => {
    expect(getSchemaAtPath(schema, ['tags', 0])).toEqual({ type: 'string' });
  });

  it('returns undefined for missing path', () => {
    expect(getSchemaAtPath(schema, ['nonexistent'])).toBeUndefined();
  });

  it('returns root for empty path', () => {
    expect(getSchemaAtPath(schema, [])).toBe(schema);
  });

  it('returns undefined when schema is undefined', () => {
    expect(getSchemaAtPath(undefined, ['a'])).toBeUndefined();
  });
});

describe('definitionPathToSegments', () => {
  it('splits path into segments', () => {
    expect(definitionPathToSegments('Root/Field1/Field2')).toEqual([
      'Root',
      'Field1',
      'Field2',
    ]);
  });

  it('strips root idShort prefix', () => {
    expect(definitionPathToSegments('Nameplate/Field1', 'Nameplate')).toEqual([
      'Field1',
    ]);
  });

  it('handles array markers', () => {
    expect(definitionPathToSegments('Root/Items[]/Name')).toEqual([
      'Root',
      'Items',
      '[]',
      'Name',
    ]);
  });
});

describe('getValuesAtPattern', () => {
  const data = {
    contacts: [
      { name: 'Alice', role: 'admin' },
      { name: 'Bob', role: 'user' },
    ],
  };

  it('navigates into arrays with [] segment', () => {
    const result = getValuesAtPattern(data, ['contacts', '[]', 'name']);
    expect(result).toEqual(['Alice', 'Bob']);
  });

  it('navigates simple object paths', () => {
    const result = getValuesAtPattern({ a: { b: 42 } }, ['a', 'b']);
    expect(result).toEqual([42]);
  });

  it('returns empty for missing path', () => {
    const result = getValuesAtPattern(data, ['nonexistent', '[]']);
    expect(result).toEqual([]);
  });
});
