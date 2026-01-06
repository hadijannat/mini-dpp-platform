export function extractElementValue(element: any): unknown {
  const type = element?.modelType?.name;
  if (type === 'SubmodelElementCollection') {
    return extractElements(element.value || []);
  }
  if (type === 'SubmodelElementList') {
    const items = Array.isArray(element.value) ? element.value : [];
    return items.map((item) => {
      if (item && typeof item === 'object' && item.modelType) {
        return extractElementValue(item);
      }
      return item;
    });
  }
  if (type === 'MultiLanguageProperty') {
    const value = element.value;
    if (Array.isArray(value)) {
      return value.reduce<Record<string, string>>((acc, entry) => {
        if (entry?.language) acc[String(entry.language)] = String(entry.text ?? '');
        return acc;
      }, {});
    }
  }
  if (type === 'Range') {
    return { min: element.min ?? null, max: element.max ?? null };
  }
  if (type === 'File') {
    return { contentType: element.contentType ?? '', value: element.value ?? '' };
  }
  if (type === 'Blob') {
    return { contentType: element.contentType ?? '', value: element.value ?? '' };
  }
  if (type === 'ReferenceElement') {
    const reference = element.value ?? {};
    return {
      type: reference.type ?? 'ModelReference',
      keys: Array.isArray(reference.keys) ? reference.keys : [],
    };
  }
  if (type === 'Entity') {
    return {
      entityType: element.entityType ?? 'SelfManagedEntity',
      globalAssetId: element.globalAssetId ?? '',
      statements: extractElements(element.statements || []),
    };
  }
  if (type === 'RelationshipElement') {
    return {
      first: element.first ?? null,
      second: element.second ?? null,
    };
  }
  if (type === 'AnnotatedRelationshipElement') {
    return {
      first: element.first ?? null,
      second: element.second ?? null,
      annotations: extractElements(element.annotations || []),
    };
  }
  return element?.value ?? '';
}

export function extractElements(elements: any[]): Record<string, unknown> {
  return elements.reduce<Record<string, unknown>>((acc, element) => {
    const idShort = element?.idShort;
    if (!idShort) return acc;
    acc[String(idShort)] = extractElementValue(element);
    return acc;
  }, {});
}

export function buildSubmodelData(submodel: any): Record<string, unknown> {
  return extractElements(submodel?.submodelElements || []);
}
