import { describe, expect, it } from 'vitest';

import { classifyElement, classifySubmodelElements } from '../esprCategories';

describe('classifyElement', () => {
  it('classifies by semantic ID (nameplate → identity)', () => {
    const result = classifyElement(
      'SomeGenericName',
      'https://admin-shell.io/zvei/nameplate/2/0/Nameplate',
    );
    expect(result).not.toBeNull();
    expect(result!.id).toBe('identity');
  });

  it('classifies by semantic ID (carbon footprint → environmental)', () => {
    const result = classifyElement(
      'SomeGenericName',
      'https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/0/9',
    );
    expect(result).not.toBeNull();
    expect(result!.id).toBe('environmental');
  });

  it('classifies by semantic ID (technical data → compliance)', () => {
    const result = classifyElement(
      'SomeGenericName',
      'https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2',
    );
    expect(result).not.toBeNull();
    expect(result!.id).toBe('compliance');
  });

  it('falls back to pattern matching when semantic ID is unknown', () => {
    const result = classifyElement('ManufacturerName', 'urn:unknown:semantic:id');
    expect(result).not.toBeNull();
    expect(result!.id).toBe('identity');
  });

  it('falls back to pattern matching when no semantic ID', () => {
    const result = classifyElement('CarbonFootprint');
    expect(result).not.toBeNull();
    expect(result!.id).toBe('environmental');
  });

  it('semantic ID takes precedence over misleading idShort', () => {
    // idShort says "carbon" but semantic ID says it's identity (nameplate)
    const result = classifyElement(
      'CarbonRelatedField',
      'https://admin-shell.io/zvei/nameplate/2/0/Nameplate',
    );
    expect(result).not.toBeNull();
    expect(result!.id).toBe('identity');
  });

  it('returns null for unrecognized element', () => {
    const result = classifyElement('XyzRandomField');
    expect(result).toBeNull();
  });
});

describe('classifySubmodelElements', () => {
  it('classifies submodel elements using semantic IDs', () => {
    const submodels = [
      {
        idShort: 'Nameplate',
        semanticId: {
          type: 'ExternalReference',
          keys: [{ type: 'GlobalReference', value: 'https://admin-shell.io/zvei/nameplate/2/0/Nameplate' }],
        },
        submodelElements: [
          { idShort: 'ManufacturerName', value: 'ACME' },
          { idShort: 'SerialNumber', value: 'SN-001' },
        ],
      },
    ];

    const result = classifySubmodelElements(submodels);
    expect(result['identity'].length).toBe(2);
  });

  it('puts unrecognized elements in uncategorized', () => {
    const submodels = [
      {
        idShort: 'UnknownSubmodel',
        submodelElements: [
          { idShort: 'WeirdField', value: 'test' },
        ],
      },
    ];

    const result = classifySubmodelElements(submodels);
    expect(result['uncategorized'].length).toBe(1);
  });
});
