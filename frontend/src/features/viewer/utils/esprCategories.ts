import { Fingerprint, FlaskConical, Leaf, ShieldCheck, Wrench, type LucideIcon } from 'lucide-react';

/**
 * Maps IDTA/Catena-X semantic IDs to ESPR category IDs.
 * This is the primary classification mechanism — pattern matching on idShort
 * is used as a fallback when no semantic ID is available.
 */
const SEMANTIC_ID_TO_CATEGORY: Record<string, string> = {
  // Nameplate → Identity
  'https://admin-shell.io/zvei/nameplate/2/0/Nameplate': 'identity',
  'https://admin-shell.io/zvei/nameplate/3/0/Nameplate': 'identity',
  '0173-1#01-AHF578#001': 'identity',
  // Technical Data → Compliance
  'https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2': 'compliance',
  // Carbon Footprint → Environmental
  'https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/0/9': 'environmental',
  // Hierarchical Structures → Materials (BOM)
  'https://admin-shell.io/idta/HierarchicalStructures/1/0/Submodel': 'materials',
  // Handover Documentation → End-of-Life
  'https://admin-shell.io/ZVEI/HandoverDocumentation/Submodel/1/2': 'endoflife',
  // Battery Passport submodels (Catena-X)
  'urn:samm:io.catenax.battery.battery_pass:6.0.0#BatteryPass': 'identity',
};

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
      'identification', 'assetid', 'partid', 'partnumber', 'modelnumber',
      'brand', 'trademark', 'traceability',
    ],
  },
  {
    id: 'materials',
    label: 'Material Composition',
    icon: FlaskConical,
    description: 'Material composition, recyclate content, and critical raw materials',
    patterns: [
      'material', 'billofmaterial', 'recyclate', 'substance', 'chemical',
      'composition', 'rawmaterial', 'ingredient', 'alloy', 'polymer',
      'criticalraw', 'hazardous',
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
      'technicaldata', 'compliance', 'conformity', 'certification', 'standard',
      'regulation', 'marking', 'declaration', 'cemarking', 'reach', 'rohs',
    ],
  },
  {
    id: 'endoflife',
    label: 'Repair & End-of-Life',
    icon: Wrench,
    description: 'Repair instructions, spare parts, and end-of-life handling',
    patterns: [
      'repair', 'maintenance', 'sparepart', 'handover', 'documentation',
      'endoflife', 'disassembly', 'recycling', 'disposal', 'lifetime',
      'warranty', 'instruction', 'durability',
    ],
  },
];

/**
 * Classify a submodel element into an ESPR category.
 * Primary: semantic ID lookup. Fallback: pattern matching on idShort.
 */
export function classifyElement(
  idShort: string,
  semanticId?: string,
): ESPRCategory | null {
  // Primary: semantic ID lookup
  if (semanticId) {
    const categoryId = SEMANTIC_ID_TO_CATEGORY[semanticId];
    if (categoryId) {
      return ESPR_CATEGORIES.find(c => c.id === categoryId) ?? null;
    }
  }
  // Fallback: pattern matching on idShort
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
    const submodelSemanticId = _extractSemanticId(submodel);

    // First, try to classify the entire submodel
    const submodelCategory = classifyElement(
      (submodel.idShort as string) || '',
      submodelSemanticId,
    );

    for (const element of elements) {
      const elementSemanticId = _extractSemanticId(element);
      const elementCategory = classifyElement(
        (element.idShort as string) || '',
        elementSemanticId,
      );
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

/**
 * Extract the first semantic ID value from an AAS element's semanticId reference.
 */
function _extractSemanticId(element: Record<string, unknown>): string | undefined {
  const semanticId = element.semanticId as Record<string, unknown> | undefined;
  if (!semanticId) return undefined;
  const keys = semanticId.keys as Array<Record<string, unknown>> | undefined;
  if (!keys || keys.length === 0) return undefined;
  return keys[0].value as string | undefined;
}
