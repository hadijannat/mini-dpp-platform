import semanticRegistry from '@shared/idta_semantic_registry.json';

export type AccessTier = 'public' | 'partner' | 'restricted';
export type AudienceMode = 'general' | 'implementer';
export type ModelLane = 'core' | 'extension';

export interface DppModelActions {
  demoHref: string;
  evidenceHref: string;
  apiHref: string;
}

export interface DppModelNode {
  id: string;
  label: string;
  tabLabel: string;
  templateKey?: string;
  idtaTemplateName?: string;
  semanticId?: string;
  lane: ModelLane;
  accessTier: AccessTier;
  descriptionPublic: string;
  whyItMattersPublic: string;
  whoUsesItPublic: string;
  descriptionImpl: string;
  apiHintPath: string;
  typicalFields: string[];
  actions: DppModelActions;
}

interface RegistryTemplateEntry {
  semantic_id?: string;
}

interface SemanticRegistryDocument {
  templates?: Record<string, RegistryTemplateEntry>;
}

const SEMANTIC_REGISTRY = semanticRegistry as SemanticRegistryDocument;

const ACTIONS: DppModelActions = {
  demoHref: '#sample-passport',
  evidenceHref: 'https://industrialdigitaltwin.org/dpp4-0',
  apiHref: '/api/v1/docs',
};

function templateSemanticId(templateKey: string): string | undefined {
  return SEMANTIC_REGISTRY.templates?.[templateKey]?.semantic_id;
}

export const dppModelNodes: DppModelNode[] = [
  {
    id: 'digital-nameplate',
    label: 'Digital Nameplate',
    tabLabel: 'DNP 4.0',
    templateKey: 'digital-nameplate',
    idtaTemplateName: 'Digital Nameplate',
    semanticId: templateSemanticId('digital-nameplate'),
    lane: 'core',
    accessTier: 'public',
    descriptionPublic:
      'Core product identity, manufacturer profile, and essential identifiers for trustworthy passport access.',
    whyItMattersPublic:
      'It gives regulators, operators, and customers a stable product identity foundation before deeper data access.',
    whoUsesItPublic: 'Regulators, operators, marketplaces, and end users.',
    descriptionImpl:
      'Canonical identity submodel resolved by semantic ID and exposed through public-safe shell retrieval flows.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}',
    typicalFields: ['ManufacturerName', 'ProductDesignation', 'ProductImage', 'OrderCode'],
    actions: ACTIONS,
  },
  {
    id: 'contact-information',
    label: 'Contact Information',
    tabLabel: 'Contact',
    templateKey: 'contact-information',
    idtaTemplateName: 'Submodel for Contact Information',
    semanticId: templateSemanticId('contact-information'),
    lane: 'core',
    accessTier: 'public',
    descriptionPublic:
      'Identifies responsible contacts for product support, compliance inquiries, and lifecycle handovers.',
    whyItMattersPublic:
      'It keeps accountability visible and enables fast routing for audits, incidents, and support workflows.',
    whoUsesItPublic: 'Authorities, service partners, and compliance teams.',
    descriptionImpl:
      'Mapped to IDTA contact template semantics and consumed as a standalone submodel reference.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}',
    typicalFields: ['ContactName', 'AddressInformation', 'Phone', 'Email'],
    actions: ACTIONS,
  },
  {
    id: 'technical-data',
    label: 'Technical Data',
    tabLabel: 'Technical',
    templateKey: 'technical-data',
    idtaTemplateName: 'Generic Frame for Technical Data',
    semanticId: templateSemanticId('technical-data'),
    lane: 'core',
    accessTier: 'public',
    descriptionPublic:
      'Captures essential technical characteristics required to interpret product behavior and performance.',
    whyItMattersPublic:
      'It supports comparability, safer operation, and evidence-backed claims in downstream product usage.',
    whoUsesItPublic: 'Engineering teams, buyers, and market surveillance authorities.',
    descriptionImpl:
      'Versioned technical frame template keyed by semantic ID and resolved through AAS repository paths.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}',
    typicalFields: ['RatedVoltage', 'Mass', 'Dimensions', 'OperatingRange'],
    actions: ACTIONS,
  },
  {
    id: 'hierarchical-structures',
    label: 'Bill of Materials',
    tabLabel: 'BOM',
    templateKey: 'hierarchical-structures',
    idtaTemplateName: 'Hierarchical Structures enabling Bills of Material',
    semanticId: templateSemanticId('hierarchical-structures'),
    lane: 'core',
    accessTier: 'restricted',
    descriptionPublic:
      'Represents nested component structure so authorized parties can understand composition and material lineage.',
    whyItMattersPublic:
      'It is critical for repairability, sourcing transparency, and circular lifecycle operations.',
    whoUsesItPublic: 'Manufacturers, recyclers, and authorized service networks.',
    descriptionImpl:
      'Hierarchical composition model with relationship-rich structures typically exposed through protected routes.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}/$value',
    typicalFields: ['ComponentId', 'ParentChildLinks', 'MaterialClass', 'MassFraction'],
    actions: ACTIONS,
  },
  {
    id: 'handover-documentation',
    label: 'Handover Documentation',
    tabLabel: 'Handover',
    templateKey: 'handover-documentation',
    idtaTemplateName: 'Handover Documentation',
    semanticId: templateSemanticId('handover-documentation'),
    lane: 'core',
    accessTier: 'restricted',
    descriptionPublic:
      'Collects manuals, compliance files, and transfer documents needed at ownership or custody handover points.',
    whyItMattersPublic:
      'It preserves continuity across operation, maintenance, and end-of-life transitions.',
    whoUsesItPublic: 'Operators, repair networks, and downstream logistics partners.',
    descriptionImpl:
      'Document-centric template integrated as submodel references with policy-based visibility boundaries.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}',
    typicalFields: ['ManualReference', 'SafetyInstructions', 'DeclarationOfConformity', 'WarrantyDoc'],
    actions: ACTIONS,
  },
  {
    id: 'carbon-footprint',
    label: 'Carbon Footprint',
    tabLabel: 'Carbon',
    templateKey: 'carbon-footprint',
    idtaTemplateName: 'Carbon Footprint',
    semanticId: templateSemanticId('carbon-footprint'),
    lane: 'core',
    accessTier: 'public',
    descriptionPublic:
      'Stores product-level carbon intensity values and methodological context for sustainability disclosures.',
    whyItMattersPublic:
      'It anchors environmental reporting with standardized fields that can be independently verified.',
    whoUsesItPublic: 'Sustainability teams, regulators, and procurement stakeholders.',
    descriptionImpl:
      'IDTA carbon template integrated into shell submodel references and resolvable via public-safe endpoints.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}',
    typicalFields: ['PCFValue', 'DeclaredUnit', 'Methodology', 'ReferencePeriod'],
    actions: ACTIONS,
  },
  {
    id: 'recyclability-extension',
    label: 'Recyclability / Circularity',
    tabLabel: 'Circularity',
    lane: 'extension',
    accessTier: 'partner',
    semanticId: 'urn:dpp:extension:recyclability-circularity:1:0',
    descriptionPublic:
      'Extension lane for category-specific recyclability and circular performance data managed by business policy.',
    whyItMattersPublic:
      'It supports circular economy use cases where additional data beyond core templates is contractually required.',
    whoUsesItPublic: 'Circularity partners, recyclers, and delegated-service providers.',
    descriptionImpl:
      'Non-core extension namespace linked to delegated-act or partner-specific contract definitions.',
    apiHintPath: '/api/v1/public/{tenant}/shells/{aasIdB64}/submodels/{submodelIdB64}',
    typicalFields: ['MaterialRecoveryRate', 'DisassemblyScore', 'RecycledContentShare', 'SortingGuidance'],
    actions: ACTIONS,
  },
];

export const defaultDppModelNodeId = 'digital-nameplate';
