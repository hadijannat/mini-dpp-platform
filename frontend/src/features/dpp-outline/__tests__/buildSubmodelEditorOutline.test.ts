import { describe, expect, it } from 'vitest';
import type { TemplateDefinition } from '@/features/editor/types/definition';
import { buildSubmodelEditorOutline } from '../builders/buildSubmodelEditorOutline';

const templateDefinition: TemplateDefinition = {
  submodel: {
    idShort: 'Nameplate',
    elements: [
      {
        modelType: 'SubmodelElementCollection',
        idShort: 'ManufacturerData',
        children: [
          {
            modelType: 'Property',
            idShort: 'ManufacturerName',
            smt: { cardinality: 'One' },
          },
          {
            modelType: 'Property',
            idShort: 'ManufacturerCode',
          },
        ],
      },
    ],
  },
};

describe('buildSubmodelEditorOutline', () => {
  it('creates section and field nodes with completion and error counters', () => {
    const nodes = buildSubmodelEditorOutline({
      templateDefinition,
      formData: {
        ManufacturerData: {
          ManufacturerName: '',
          ManufacturerCode: '',
        },
      },
      fieldErrors: [{ path: 'ManufacturerData.ManufacturerName', message: 'Required' }],
    });

    expect(nodes).toHaveLength(1);
    const section = nodes[0];
    expect(section.kind).toBe('section');
    expect(section.path).toBe('ManufacturerData');
    expect(section.status?.errors).toBe(1);

    const requiredField = section.children.find((child) => child.path.endsWith('ManufacturerName'));
    expect(requiredField?.kind).toBe('field');
    expect(requiredField?.status?.required).toBe(true);
    expect(requiredField?.status?.completion).toBe('empty');
    expect(requiredField?.status?.errors).toBe(1);
  });

  it('updates field completion based on live form values', () => {
    const nodes = buildSubmodelEditorOutline({
      templateDefinition,
      formData: {
        ManufacturerData: {
          ManufacturerName: 'ACME',
          ManufacturerCode: '001',
        },
      },
      fieldErrors: [],
    });

    const section = nodes[0];
    const requiredField = section.children.find((child) => child.path.endsWith('ManufacturerName'));
    expect(requiredField?.status?.completion).toBe('complete');
    expect(section.status?.completion).toBe('complete');
  });
});
