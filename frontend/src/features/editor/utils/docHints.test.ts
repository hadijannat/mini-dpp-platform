import { describe, expect, it } from 'vitest';
import {
  buildDocHintDescription,
  fieldPathToIdShortPath,
  resolveDocHint,
} from './docHints';
import type { DefinitionNode } from '../types/definition';
import type { DocHintsPayload } from '../contexts/DocHintsContext';

describe('docHints', () => {
  it('prioritizes semanticId hint over idShort path hint', () => {
    const docHints: DocHintsPayload = {
      by_semantic_id: {
        'urn:test:semantic': {
          formTitle: 'Semantic title',
          source: 'sidecar',
        },
      },
      by_id_short_path: {
        'ContactInformation[]/Phone': {
          formTitle: 'Path title',
          source: 'qualifier',
        },
      },
      entries: [],
    };

    const node: DefinitionNode = {
      modelType: 'Property',
      semanticId: 'URN:TEST:SEMANTIC/',
      idShort: 'Phone',
    };

    const hint = resolveDocHint({
      node,
      fieldPath: 'ContactInformation.0.Phone',
      docHints,
    });

    expect(hint?.formTitle).toBe('Semantic title');
  });

  it('normalizes list indexes in field paths to idShort [] notation', () => {
    expect(fieldPathToIdShortPath('ContactInformation.0.Phone')).toBe('ContactInformation[]/Phone');
    expect(fieldPathToIdShortPath('A.0.B.1.C')).toBe('A[]/B[]/C');
  });

  it('uses sidecar hint fields and description builder for fallback path matches', () => {
    const docHints: DocHintsPayload = {
      by_semantic_id: {},
      by_id_short_path: {
        'ContactInformation[]/Phone': {
          helpText: 'Enter international format',
          formUrl: 'https://example.com/specs/phone',
          pdfRef: 'phone-spec.pdf',
          page: 14,
          source: 'sidecar',
        },
      },
      entries: [],
    };

    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'Phone',
    };

    const hint = resolveDocHint({
      node,
      fieldPath: 'ContactInformation.0.Phone',
      docHints,
    });

    expect(hint?.helpText).toBe('Enter international format');
    expect(hint?.formUrl).toBe('https://example.com/specs/phone');

    const description = buildDocHintDescription(hint ?? {});
    expect(description).toContain('Enter international format');
    expect(description).toContain('phone-spec.pdf');
    expect(description).toContain('p. 14');
  });

  it('prefers sidecar helpText over qualifier formInfo when both are present', () => {
    const description = buildDocHintDescription({
      formInfo: 'Qualifier description',
      helpText: 'Sidecar description',
      formUrl: 'https://example.com/help',
    });

    expect(description).toContain('Sidecar description');
    expect(description).not.toContain('Qualifier description');
  });
});
