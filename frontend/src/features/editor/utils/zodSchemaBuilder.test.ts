import { describe, expect, it } from 'vitest';
import { buildZodSchema } from './zodSchemaBuilder';
import type { TemplateDefinition, DefinitionNode } from '../types/definition';
import type { UISchema } from '../types/uiSchema';

describe('buildZodSchema', () => {
  it('returns passthrough record when no definition or schema', () => {
    const schema = buildZodSchema(undefined, undefined);
    const result = schema.safeParse({ any: 'value' });
    expect(result.success).toBe(true);
  });

  describe('Property nodes', () => {
    function defWithProperty(valueType?: string, smt?: DefinitionNode['smt']): TemplateDefinition {
      return {
        submodel: {
          elements: [
            { modelType: 'Property', idShort: 'field', valueType, smt },
          ],
        },
      };
    }

    it('validates xs:string as string', () => {
      const schema = buildZodSchema(defWithProperty('xs:string'));
      expect(schema.safeParse({ field: 'hello' }).success).toBe(true);
    });

    it('validates xs:integer as integer', () => {
      const schema = buildZodSchema(defWithProperty('xs:integer'));
      expect(schema.safeParse({ field: 42 }).success).toBe(true);
      expect(schema.safeParse({ field: null }).success).toBe(true); // nullable
      expect(schema.safeParse({ field: 3.14 }).success).toBe(false); // not integer
    });

    it('validates xs:decimal as number', () => {
      const schema = buildZodSchema(defWithProperty('xs:decimal'));
      expect(schema.safeParse({ field: 3.14 }).success).toBe(true);
      expect(schema.safeParse({ field: null }).success).toBe(true); // nullable
    });

    it('validates xs:boolean as boolean', () => {
      const schema = buildZodSchema(defWithProperty('xs:boolean'));
      expect(schema.safeParse({ field: true }).success).toBe(true);
      expect(schema.safeParse({ field: false }).success).toBe(true);
      expect(schema.safeParse({ field: 'yes' }).success).toBe(false);
    });

    it('applies allowed_range constraints', () => {
      const def = defWithProperty('xs:integer', {
        allowed_range: { min: 0, max: 100 },
      });
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ field: 50 }).success).toBe(true);
      expect(schema.safeParse({ field: -1 }).success).toBe(false);
      expect(schema.safeParse({ field: 101 }).success).toBe(false);
    });

    it('validates enum from form_choices', () => {
      const def = defWithProperty('xs:string', {
        form_choices: ['option1', 'option2'],
      });
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ field: 'option1' }).success).toBe(true);
      expect(schema.safeParse({ field: 'invalid' }).success).toBe(false);
    });

    it('validates allowed_value_regex', () => {
      const def = defWithProperty('xs:string', {
        allowed_value_regex: '^[A-Z]{3}$',
      });
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ field: 'ABC' }).success).toBe(true);
      expect(schema.safeParse({ field: 'abc' }).success).toBe(false);
      expect(schema.safeParse({ field: 'ABCD' }).success).toBe(false);
    });
  });

  it('treats unknown model types as unknown schema instead of property-like validation', () => {
    const definition: TemplateDefinition = {
      submodel: {
        elements: [
          {
            modelType: 'SubmodelElement',
            idShort: 'GenericNode',
          },
        ],
      },
    };

    const schema = buildZodSchema(definition);
    expect(schema.safeParse({ GenericNode: { arbitrary: true } }).success).toBe(true);
    expect(schema.safeParse({ GenericNode: 'text-value' }).success).toBe(true);
  });

  describe('MultiLanguageProperty nodes', () => {
    it('validates as record of strings', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [
            { modelType: 'MultiLanguageProperty', idShort: 'title' },
          ],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ title: { en: 'Hello', de: 'Hallo' } }).success).toBe(true);
    });

    it('validates required languages', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [
            {
              modelType: 'MultiLanguageProperty',
              idShort: 'title',
              smt: { required_lang: ['en'] },
            },
          ],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ title: { en: 'Hello' } }).success).toBe(true);
      expect(schema.safeParse({ title: { de: 'Hallo' } }).success).toBe(false); // missing en
    });
  });

  describe('Range nodes', () => {
    it('accepts valid min/max', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [{ modelType: 'Range', idShort: 'temp' }],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ temp: { min: 10, max: 50 } }).success).toBe(true);
      expect(schema.safeParse({ temp: { min: null, max: null } }).success).toBe(true);
    });

    it('rejects min > max', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [{ modelType: 'Range', idShort: 'temp' }],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ temp: { min: 100, max: 10 } }).success).toBe(false);
    });
  });

  describe('SubmodelElementCollection nodes', () => {
    it('validates nested structure recursively', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [
            {
              modelType: 'SubmodelElementCollection',
              idShort: 'address',
              children: [
                { modelType: 'Property', idShort: 'city', valueType: 'xs:string' },
                { modelType: 'Property', idShort: 'zip', valueType: 'xs:string' },
              ],
            },
          ],
        },
      };
      const schema = buildZodSchema(def);
      expect(
        schema.safeParse({ address: { city: 'Berlin', zip: '10115' } }).success,
      ).toBe(true);
    });
  });

  describe('SubmodelElementList nodes', () => {
    it('validates as array', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [
            {
              modelType: 'SubmodelElementList',
              idShort: 'tags',
              items: { modelType: 'Property', idShort: 'tag', valueType: 'xs:string' },
            },
          ],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ tags: ['a', 'b'] }).success).toBe(true);
      expect(schema.safeParse({ tags: [] }).success).toBe(true);
    });

    it('enforces OneToMany cardinality (min 1)', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [
            {
              modelType: 'SubmodelElementList',
              idShort: 'items',
              items: { modelType: 'Property', idShort: 'item', valueType: 'xs:string' },
              smt: { cardinality: 'OneToMany' },
            },
          ],
        },
      };
      const schema = buildZodSchema(def);
      expect(schema.safeParse({ items: ['a'] }).success).toBe(true);
      expect(schema.safeParse({ items: [] }).success).toBe(false);
    });
  });

  describe('File nodes', () => {
    it('validates file structure', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [{ modelType: 'File', idShort: 'doc' }],
        },
      };
      const schema = buildZodSchema(def);
      expect(
        schema.safeParse({ doc: { contentType: 'application/pdf', value: '/file.pdf' } }).success,
      ).toBe(true);
    });

    it('rejects invalid MIME type in file structure', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [{ modelType: 'File', idShort: 'doc' }],
        },
      };
      const schema = buildZodSchema(def);
      expect(
        schema.safeParse({ doc: { contentType: 'not a mime', value: '/file.pdf' } }).success,
      ).toBe(false);
      expect(
        schema.safeParse({ doc: { contentType: 'image/png', value: '/image.png' } }).success,
      ).toBe(true);
    });
  });

  describe('ReferenceElement nodes', () => {
    it('validates reference structure', () => {
      const def: TemplateDefinition = {
        submodel: {
          elements: [{ modelType: 'ReferenceElement', idShort: 'ref' }],
        },
      };
      const schema = buildZodSchema(def);
      expect(
        schema.safeParse({
          ref: { type: 'ModelReference', keys: [{ type: 'Submodel', value: 'id' }] },
        }).success,
      ).toBe(true);
    });
  });

  describe('RelationshipElement', () => {
    const definition: TemplateDefinition = {
      submodel: {
        idShort: 'Test',
        elements: [
          {
            idShort: 'TestRelationship',
            modelType: 'RelationshipElement',
            first: undefined,
            second: undefined,
          },
        ],
      },
    };

    it('validates proper AAS Reference structure', () => {
      const schema = buildZodSchema(definition);
      const validData = {
        TestRelationship: {
          first: {
            type: 'ModelReference',
            keys: [{ type: 'Submodel', value: 'urn:example:sm:1' }],
          },
          second: {
            type: 'ExternalReference',
            keys: [{ type: 'GlobalReference', value: 'https://example.com' }],
          },
        },
      };
      expect(() => schema.parse(validData)).not.toThrow();
    });

    it('accepts null references', () => {
      const schema = buildZodSchema(definition);
      const data = {
        TestRelationship: {
          first: null,
          second: null,
        },
      };
      expect(() => schema.parse(data)).not.toThrow();
    });

    it('accepts references without keys', () => {
      const schema = buildZodSchema(definition);
      const data = {
        TestRelationship: {
          first: { type: 'ModelReference' },
          second: null,
        },
      };
      expect(() => schema.parse(data)).not.toThrow();
    });
  });

  describe('AnnotatedRelationshipElement', () => {
    const definition: TemplateDefinition = {
      submodel: {
        idShort: 'Test',
        elements: [
          {
            idShort: 'TestAnnotatedRel',
            modelType: 'AnnotatedRelationshipElement',
            annotations: [
              { idShort: 'Note', modelType: 'Property', valueType: 'xs:string' },
            ],
          },
        ],
      },
    };

    it('validates structured references with annotations', () => {
      const schema = buildZodSchema(definition);
      const data = {
        TestAnnotatedRel: {
          first: {
            type: 'ModelReference',
            keys: [{ type: 'Submodel', value: 'urn:example:1' }],
          },
          second: null,
          annotations: {
            Note: 'test annotation',
          },
        },
      };
      expect(() => schema.parse(data)).not.toThrow();
    });
  });

  describe('UISchema fallback', () => {
    it('builds schema from UISchema when no definition', () => {
      const uiSchema: UISchema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'integer' },
        },
      };
      const schema = buildZodSchema(undefined, uiSchema);
      expect(schema.safeParse({ name: 'Alice', age: 30 }).success).toBe(true);
    });

    it('handles x-multi-language in UISchema', () => {
      const uiSchema: UISchema = {
        type: 'object',
        properties: {
          title: { 'x-multi-language': true } as UISchema,
        },
      };
      const schema = buildZodSchema(undefined, uiSchema);
      expect(schema.safeParse({ title: { en: 'hi' } }).success).toBe(true);
    });
  });
});
