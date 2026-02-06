import { describe, expect, it } from 'vitest';
import {
  isCollection,
  isList,
  isProperty,
  isMultiLanguage,
  isRange,
  isFile,
  isBlob,
  isReference,
  isEntity,
  isRelationship,
  isAnnotatedRelationship,
  isReadOnlyType,
} from './typeGuards';
import type { DefinitionNode } from '../types/definition';

function node(modelType: string): DefinitionNode {
  return { modelType } as DefinitionNode;
}

describe('type guards', () => {
  it('isCollection', () => {
    expect(isCollection(node('SubmodelElementCollection'))).toBe(true);
    expect(isCollection(node('Property'))).toBe(false);
  });

  it('isList', () => {
    expect(isList(node('SubmodelElementList'))).toBe(true);
    expect(isList(node('Property'))).toBe(false);
  });

  it('isProperty', () => {
    expect(isProperty(node('Property'))).toBe(true);
    expect(isProperty(node('Range'))).toBe(false);
  });

  it('isMultiLanguage', () => {
    expect(isMultiLanguage(node('MultiLanguageProperty'))).toBe(true);
    expect(isMultiLanguage(node('Property'))).toBe(false);
  });

  it('isRange', () => {
    expect(isRange(node('Range'))).toBe(true);
    expect(isRange(node('Property'))).toBe(false);
  });

  it('isFile', () => {
    expect(isFile(node('File'))).toBe(true);
    expect(isFile(node('Blob'))).toBe(false);
  });

  it('isBlob', () => {
    expect(isBlob(node('Blob'))).toBe(true);
    expect(isBlob(node('File'))).toBe(false);
  });

  it('isReference', () => {
    expect(isReference(node('ReferenceElement'))).toBe(true);
    expect(isReference(node('Property'))).toBe(false);
  });

  it('isEntity', () => {
    expect(isEntity(node('Entity'))).toBe(true);
    expect(isEntity(node('Property'))).toBe(false);
  });

  it('isRelationship', () => {
    expect(isRelationship(node('RelationshipElement'))).toBe(true);
    expect(isRelationship(node('Property'))).toBe(false);
  });

  it('isAnnotatedRelationship', () => {
    expect(isAnnotatedRelationship(node('AnnotatedRelationshipElement'))).toBe(true);
    expect(isAnnotatedRelationship(node('Property'))).toBe(false);
  });

  it('isReadOnlyType recognizes all read-only types', () => {
    expect(isReadOnlyType(node('Blob'))).toBe(true);
    expect(isReadOnlyType(node('Operation'))).toBe(true);
    expect(isReadOnlyType(node('Capability'))).toBe(true);
    expect(isReadOnlyType(node('BasicEventElement'))).toBe(true);
    expect(isReadOnlyType(node('Property'))).toBe(false);
    expect(isReadOnlyType(node('File'))).toBe(false);
  });
});
