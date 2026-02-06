import { Fingerprint, FlaskConical, Leaf, ShieldCheck, Wrench, type LucideIcon } from 'lucide-react';

export type ESPRCategory = {
  id: string;
  label: string;
  icon: LucideIcon;
  description: string;
  /** idShort patterns that map to this category (case-insensitive partial match) */
  patterns: string[];
};

export const ESPR_CATEGORIES: ESPRCategory[] = [
  {
    id: 'identity',
    label: 'Product Identity',
    icon: Fingerprint,
    description: 'Product identification, manufacturer, and traceability information',
    patterns: [
      'nameplate', 'manufacturer', 'serial', 'batch', 'product', 'gtin',
      'identification', 'asset', 'part', 'model', 'brand', 'name',
    ],
  },
  {
    id: 'materials',
    label: 'Material Composition',
    icon: FlaskConical,
    description: 'Material composition, recyclate content, and critical raw materials',
    patterns: [
      'material', 'bill', 'recyclate', 'substance', 'chemical', 'composition',
      'raw', 'component', 'ingredient', 'alloy', 'polymer',
    ],
  },
  {
    id: 'environmental',
    label: 'Environmental Impact',
    icon: Leaf,
    description: 'Carbon footprint, energy rating, and environmental performance',
    patterns: [
      'carbon', 'footprint', 'energy', 'emission', 'environment', 'climate',
      'sustainability', 'recyclability', 'waste', 'co2', 'ghg',
    ],
  },
  {
    id: 'compliance',
    label: 'Compliance & Certification',
    icon: ShieldCheck,
    description: 'Technical standards, CE marking, and conformity declarations',
    patterns: [
      'technical', 'compliance', 'conformity', 'certification', 'standard',
      'regulation', 'marking', 'declaration', 'ce', 'reach', 'rohs',
    ],
  },
  {
    id: 'endoflife',
    label: 'Repair & End-of-Life',
    icon: Wrench,
    description: 'Repair instructions, spare parts, and end-of-life handling',
    patterns: [
      'repair', 'maintenance', 'spare', 'handover', 'documentation', 'end',
      'disassembly', 'recycling', 'disposal', 'lifetime', 'warranty', 'instruction',
    ],
  },
];

/**
 * Classify a submodel element into an ESPR category by matching
 * its idShort against category patterns.
 */
export function classifyElement(idShort: string): ESPRCategory | null {
  const lower = idShort.toLowerCase();
  for (const category of ESPR_CATEGORIES) {
    if (category.patterns.some(pattern => lower.includes(pattern))) {
      return category;
    }
  }
  return null;
}

/**
 * Classify all submodel elements into ESPR categories.
 * Returns a map of category ID -> elements, plus an 'uncategorized' bucket.
 */
export function classifySubmodelElements(
  submodels: Array<Record<string, unknown>>,
): Record<string, Array<{ submodelIdShort: string; element: Record<string, unknown> }>> {
  const result: Record<string, Array<{ submodelIdShort: string; element: Record<string, unknown> }>> = {};

  // Initialize all categories
  for (const cat of ESPR_CATEGORIES) {
    result[cat.id] = [];
  }
  result['uncategorized'] = [];

  for (const submodel of submodels) {
    const elements = (submodel.submodelElements || []) as Array<Record<string, unknown>>;
    // First, try to classify the entire submodel
    const submodelCategory = classifyElement((submodel.idShort as string) || '');

    for (const element of elements) {
      const elementCategory = classifyElement((element.idShort as string) || '');
      const category = elementCategory || submodelCategory;

      if (category) {
        result[category.id].push({ submodelIdShort: submodel.idShort as string, element });
      } else {
        result['uncategorized'].push({ submodelIdShort: submodel.idShort as string, element });
      }
    }
  }

  return result;
}
