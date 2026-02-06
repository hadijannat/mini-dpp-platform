import type { DefinitionNode } from '../types/definition';

export function isCollection(node: DefinitionNode): boolean {
  return node.modelType === 'SubmodelElementCollection';
}

export function isList(node: DefinitionNode): boolean {
  return node.modelType === 'SubmodelElementList';
}

export function isProperty(node: DefinitionNode): boolean {
  return node.modelType === 'Property';
}

export function isMultiLanguage(node: DefinitionNode): boolean {
  return node.modelType === 'MultiLanguageProperty';
}

export function isRange(node: DefinitionNode): boolean {
  return node.modelType === 'Range';
}

export function isFile(node: DefinitionNode): boolean {
  return node.modelType === 'File';
}

export function isBlob(node: DefinitionNode): boolean {
  return node.modelType === 'Blob';
}

export function isReference(node: DefinitionNode): boolean {
  return node.modelType === 'ReferenceElement';
}

export function isEntity(node: DefinitionNode): boolean {
  return node.modelType === 'Entity';
}

export function isRelationship(node: DefinitionNode): boolean {
  return node.modelType === 'RelationshipElement';
}

export function isAnnotatedRelationship(node: DefinitionNode): boolean {
  return node.modelType === 'AnnotatedRelationshipElement';
}

export function isReadOnlyType(node: DefinitionNode): boolean {
  return (
    node.modelType === 'Blob' ||
    node.modelType === 'Operation' ||
    node.modelType === 'Capability' ||
    node.modelType === 'BasicEventElement'
  );
}
