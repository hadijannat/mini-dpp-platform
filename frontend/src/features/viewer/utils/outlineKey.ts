import type { ClassifiedNode } from './esprCategories';

export function buildViewerOutlineKey(
  element: Pick<ClassifiedNode, 'submodelIdShort' | 'path' | 'label' | 'semanticId' | 'modelType'>,
): string {
  return [
    element.submodelIdShort,
    element.path,
    element.label,
    element.semanticId ?? '',
    element.modelType ?? '',
  ].join('|');
}
