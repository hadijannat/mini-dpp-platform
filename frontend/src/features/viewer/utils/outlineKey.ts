import type { ClassifiedNode } from './esprCategories';

export function buildViewerOutlineKey(
  element: Pick<ClassifiedNode, 'submodelIdShort' | 'path' | 'label'>,
  index: number,
): string {
  return `${element.submodelIdShort}|${element.path}|${element.label}|${index}`;
}
