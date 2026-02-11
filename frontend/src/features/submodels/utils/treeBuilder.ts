import type { SubmodelHealth, SubmodelNode } from '../types';

function getModelType(node: Record<string, unknown>): string {
  const modelType = node.modelType;
  if (typeof modelType === 'string' && modelType) return modelType;
  if (modelType && typeof modelType === 'object') {
    const named = (modelType as { name?: unknown }).name;
    if (typeof named === 'string' && named) return named;
  }
  return 'Property';
}

function extractSemanticId(node: Record<string, unknown>): string | undefined {
  const semanticId = node.semanticId;
  if (!semanticId || typeof semanticId !== 'object') return undefined;
  const keys = (semanticId as { keys?: Array<{ value?: unknown }> }).keys;
  const value = keys?.[0]?.value;
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function isEmptyValue(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

function buildMeta(node: Record<string, unknown>) {
  const qualifiers = Array.isArray(node.qualifiers)
    ? (node.qualifiers as Array<Record<string, unknown>>)
    : [];

  const qualifierMap: Record<string, string> = {};
  for (const qualifier of qualifiers) {
    const type = typeof qualifier.type === 'string' ? qualifier.type : '';
    if (!type) continue;
    qualifierMap[type] = String(qualifier.value ?? '');
  }

  const cardinality = qualifierMap['SMT/Cardinality'] || qualifierMap.Cardinality;
  const accessMode = (qualifierMap['SMT/AccessMode'] || qualifierMap.AccessMode || '').toLowerCase();
  const readOnly = accessMode === 'readonly' || accessMode === 'read-only';
  const required = cardinality === 'One' || cardinality === 'OneToMany';

  const validations: string[] = [];
  if (qualifierMap['SMT/AllowedRange'] || qualifierMap.AllowedRange) validations.push('range');
  if (qualifierMap['SMT/AllowedValue'] || qualifierMap.AllowedValue) validations.push('regex');
  if (qualifierMap['SMT/RequiredLang'] || qualifierMap.RequiredLang) validations.push('required-lang');
  if (qualifierMap['SMT/EitherOr'] || qualifierMap.EitherOr) validations.push('either-or');
  if (readOnly) validations.push('read-only');

  return {
    semanticId: extractSemanticId(node),
    qualifiers: qualifierMap,
    cardinality,
    required,
    readOnly,
    validations,
  };
}

function elementChildren(
  node: Record<string, unknown>,
  modelType: string,
): Array<Record<string, unknown>> {
  if (modelType === 'SubmodelElementCollection') {
    const value = node.value;
    return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
  }
  if (modelType === 'SubmodelElementList') {
    const value = node.value;
    return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
  }
  if (modelType === 'Entity') {
    const statements = node.statements;
    return Array.isArray(statements) ? (statements as Array<Record<string, unknown>>) : [];
  }
  if (modelType === 'AnnotatedRelationshipElement') {
    const annotations = node.annotations;
    if (Array.isArray(annotations)) return annotations as Array<Record<string, unknown>>;
    return [];
  }
  return [];
}

function elementValue(node: Record<string, unknown>, modelType: string): unknown {
  if (modelType === 'Property') return node.value;
  if (modelType === 'MultiLanguageProperty') return node.value;
  if (modelType === 'Range') return { min: node.min, max: node.max };
  if (modelType === 'File') return { contentType: node.contentType, value: node.value };
  if (modelType === 'Blob') return { contentType: node.contentType, value: node.value };
  if (modelType === 'ReferenceElement') return node.value;
  if (modelType === 'RelationshipElement') return { first: node.first, second: node.second };
  if (modelType === 'AnnotatedRelationshipElement') return { first: node.first, second: node.second };
  if (modelType === 'Entity') return { entityType: node.entityType, globalAssetId: node.globalAssetId };
  return node.value;
}

function buildElementNode(
  node: Record<string, unknown>,
  options: {
    path: string;
    fallbackLabel: string;
  },
): SubmodelNode {
  const { path, fallbackLabel } = options;
  const modelType = getModelType(node);
  const label = typeof node.idShort === 'string' && node.idShort ? node.idShort : fallbackLabel;
  const children = elementChildren(node, modelType).map((child, index) =>
    buildElementNode(child, {
      path: `${path}.${label}[${index}]`,
      fallbackLabel: `${label}-${index + 1}`,
    }),
  );

  return {
    id: String(node.id ?? path),
    label,
    path: `${path}.${label}`,
    modelType,
    value: children.length > 0 ? undefined : elementValue(node, modelType),
    children,
    meta: buildMeta(node),
  };
}

export function buildSubmodelNodeTree(submodel: Record<string, unknown>): SubmodelNode {
  const idShort =
    typeof submodel.idShort === 'string' && submodel.idShort
      ? submodel.idShort
      : String(submodel.id ?? 'Submodel');
  const path = idShort;
  const modelType = getModelType(submodel);
  const elements = Array.isArray(submodel.submodelElements)
    ? (submodel.submodelElements as Array<Record<string, unknown>>)
    : [];

  return {
    id: String(submodel.id ?? idShort),
    label: idShort,
    path,
    modelType,
    children: elements.map((element, index) =>
      buildElementNode(element, {
        path,
        fallbackLabel: `Field-${index + 1}`,
      }),
    ),
    meta: buildMeta(submodel),
  };
}

export function flattenSubmodelNodes(root: SubmodelNode): SubmodelNode[] {
  const flattened: SubmodelNode[] = [];
  const stack: SubmodelNode[] = [...root.children].reverse();
  while (stack.length > 0) {
    const current = stack.pop()!;
    flattened.push(current);
    for (const child of [...current.children].reverse()) {
      stack.push(child);
    }
  }
  return flattened;
}

export function computeSubmodelHealth(root: SubmodelNode): SubmodelHealth {
  const nodes = flattenSubmodelNodes(root);
  const requiredNodes = nodes.filter((node) => node.meta.required);
  const completedRequired = requiredNodes.filter((node) => !isEmptyValue(node.value)).length;
  const validationSignals = nodes.reduce((sum, node) => sum + node.meta.validations.length, 0);
  const leafCount = nodes.filter((node) => node.children.length === 0).length;

  return {
    totalRequired: requiredNodes.length,
    completedRequired,
    validationSignals,
    leafCount,
  };
}
