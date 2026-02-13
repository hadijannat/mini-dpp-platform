import { describe, expect, it } from 'vitest';
import type { TemplateDefinition } from '../types/definition';
import { buildPatchOperations } from './patchOps';

const DEFINITION: TemplateDefinition = {
  submodel: {
    idShort: 'Nameplate',
    elements: [
      { idShort: 'ManufacturerName', modelType: 'Property' },
      { idShort: 'ProductDesignation', modelType: 'MultiLanguageProperty' },
      {
        idShort: 'Documents',
        modelType: 'SubmodelElementList',
        items: {
          idShort: 'Document',
          modelType: 'SubmodelElementCollection',
          children: [
            { idShort: 'title', modelType: 'Property' },
            { idShort: 'file', modelType: 'File' },
          ],
        },
      },
    ],
  },
};

describe('buildPatchOperations', () => {
  it('builds deterministic property operations', () => {
    const current = { ManufacturerName: 'A' };
    const next = { ManufacturerName: 'B' };
    const ops = buildPatchOperations(DEFINITION, current, next);
    expect(ops).toEqual([{ op: 'set_value', path: 'ManufacturerName', value: 'B' }]);
  });

  it('builds set_multilang operations', () => {
    const current = { ProductDesignation: { en: 'Pump' } };
    const next = { ProductDesignation: { en: 'Pump', de: 'Pumpe' } };
    const ops = buildPatchOperations(DEFINITION, current, next);
    expect(ops).toEqual([
      {
        op: 'set_multilang',
        path: 'ProductDesignation',
        value: { en: 'Pump', de: 'Pumpe' },
      },
    ]);
  });

  it('builds list add/remove and nested updates in stable order', () => {
    const current = {
      Documents: [
        { title: 'Old 1', file: { contentType: 'application/pdf', value: '/a.pdf' } },
        { title: 'Old 2', file: { contentType: 'application/pdf', value: '/b.pdf' } },
      ],
    };
    const next = {
      Documents: [{ title: 'New 1', file: { contentType: 'application/pdf', value: '/c.pdf' } }],
    };
    const ops = buildPatchOperations(DEFINITION, current, next);
    expect(ops).toEqual([
      { op: 'remove_list_item', path: 'Documents', index: 1 },
      { op: 'set_value', path: 'Documents/0/title', value: 'New 1' },
      {
        op: 'set_file_ref',
        path: 'Documents/0/file',
        value: { contentType: 'application/pdf', url: '/c.pdf' },
      },
    ]);
  });
});

