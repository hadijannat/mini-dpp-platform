export type AudienceType = 'aas-builders' | 'dpp-implementers' | 'dataspace-architects' | 'platform-teams';

export type LandingIconKey =
  | 'factory'
  | 'scale'
  | 'wrench'
  | 'scan'
  | 'workflow'
  | 'shield'
  | 'globe'
  | 'api';

export type ClaimLevel = 'implements' | 'aligned' | 'roadmap';

export interface NavigationLink {
  label: string;
  href: string;
  external?: boolean;
}

export interface EvidenceLink {
  label: string;
  href: string;
}

export interface HeroContent {
  eyebrow: string;
  title: string;
  subtitle: string;
  primaryCta: string;
  primaryCtaHref: string;
  secondaryCta: string;
  secondaryCtaHref: string;
  proofPills: string[];
  trustBullets: string[];
  technicalEvidence: EvidenceLink;
}

export interface AudienceCardContent {
  id: AudienceType;
  icon: LandingIconKey;
  title: string;
  description: string;
  outcomes: string[];
}

export interface HowItWorksStep {
  title: string;
  description: string;
}

export interface StandardsMapRow {
  title: string;
  claimLevel: ClaimLevel;
  outcome: string;
  qualifier: string;
  evidence: EvidenceLink;
}

export interface DataspaceCard {
  title: string;
  claimLevel: ClaimLevel;
  body: string;
  evidence: EvidenceLink;
}

export interface DeveloperSignal {
  title: string;
  detail: string;
}

export interface DemoNode {
  label: string;
  value: string;
}

export interface FallbackMetric {
  label: string;
  value: string;
  detail: string;
}

export interface DataExposureRule {
  item: string;
  showOnLanding: boolean;
  rule: string;
}

export interface FaqItem {
  question: string;
  answer: string;
}

export interface FinalCtaContent {
  title: string;
  subtitle: string;
  primaryCta: string;
  primaryCtaHref: string;
  secondaryCta: string;
  secondaryCtaHref: string;
}

export interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

export const landingContent = {
  navigation: [
    { label: 'Demo', href: '#sample-passport' },
    { label: 'How it works', href: '#workflow' },
    { label: 'Standards', href: '#standards' },
    { label: 'FAQ', href: '#faq' },
    {
      label: 'Docs',
      href: 'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public',
      external: true,
    },
  ] satisfies NavigationLink[],

  hero: {
    eyebrow: 'Open-source ESPR-ready DPP platform',
    title: 'Digital Product Passport Platform for ESPR-ready product data',
    subtitle:
      'Create, manage, and publish standards-aligned passports using AAS + IDTA DPP4.0 with controlled public sharing.',
    primaryCta: 'Open demo passport',
    primaryCtaHref: '#sample-passport',
    secondaryCta: 'Deploy locally in 5 minutes',
    secondaryCtaHref:
      'https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose',
    proofPills: [
      'Regulation (EU) 2024/1781 aligned posture',
      'DPP4.0 Template Ingestion',
      'AAS + Dataspace-ready APIs',
    ],
    trustBullets: [
      'Regulation (EU) 2024/1781 entered into force on 18 July 2024; delegated acts define category-specific obligations.',
      'Public landing metrics are aggregate-only by policy, with sensitive keys blocked.',
      'Production stack: FastAPI, React, Keycloak, OPA, PostgreSQL, Redis, and MinIO.',
    ],
    technicalEvidence: {
      label: 'View technical evidence',
      href: 'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public',
    },
  } satisfies HeroContent,

  samplePassport: {
    title: 'Sample Passport Flow',
    description:
      'A compact view of how AAS identifiers resolve into public DPP content, with protected operational details kept out of the landing contract.',
    nodes: [
      { label: 'AAS ID', value: 'urn:uuid:dpp-shell-2f4e5a9a' },
      { label: 'Asset ID', value: 'manufacturerPartId=MP-2400' },
      { label: 'Resolver', value: '/api/v1/resolve/01/{gtin}/21/{serial}' },
      { label: 'Viewer', value: '/t/default/p/{slug}' },
    ] satisfies DemoNode[],
    aasSnippet: [
      '{',
      '  "modelType": "AssetAdministrationShell",',
      '  "idShort": "dpp-shell",',
      '  "submodels": ["digital-nameplate", "carbon-footprint", "traceability"]',
      '}',
    ].join('\n'),
  },

  audienceCards: [
    {
      id: 'aas-builders',
      icon: 'factory',
      title: 'IDTA / AAS Builders',
      description:
        'Validate shell and submodel interoperability using AAS repository style APIs and AASX exchange outputs.',
      outcomes: [
        'Map against IDTA Part 1/2 patterns with explicit endpoint evidence.',
        'Inspect AASX export behavior in practical flows.',
      ],
    },
    {
      id: 'dpp-implementers',
      icon: 'scale',
      title: 'DPP Implementers (EU ESPR Context)',
      description:
        'Build DPP lifecycles with conservative regulatory language and delegated-act-aware claim discipline.',
      outcomes: [
        'Trace implementation evidence to API and docs links.',
        'Keep compliance messaging scoped to supported capabilities.',
      ],
    },
    {
      id: 'dataspace-architects',
      icon: 'globe',
      title: 'Dataspace Architects',
      description:
        'Connect DPP publication to EDC dataspace operations with policy and contract definition support.',
      outcomes: [
        'Publish assets with usage/access policy setup paths.',
        'Track registry, resolver, and credential-oriented integration surfaces.',
      ],
    },
    {
      id: 'platform-teams',
      icon: 'api',
      title: 'Platform Teams',
      description:
        'Operate the platform as a composable stack with IAM, policy controls, and API-first contracts.',
      outcomes: [
        'Run locally via Docker Compose with known service endpoints.',
        'Integrate with CI checks and OpenAPI-driven client workflows.',
      ],
    },
  ] satisfies AudienceCardContent[],

  howItWorksSteps: [
    {
      title: 'Model',
      description: 'Author DPP records with AAS structures and DPP4.0 template contracts.',
    },
    {
      title: 'Publish',
      description: 'Release approved passports as JSON/AASX with resolver-ready identifiers.',
    },
    {
      title: 'Share',
      description:
        'Expose public viewer paths and aggregate trust metrics while routing protected exchanges through connector policies.',
    },
  ] satisfies HowItWorksStep[],

  standardsMap: [
    {
      title: 'IDTA AAS Part 2 service-description + shell APIs',
      claimLevel: 'implements',
      outcome: 'Provides tenant-scoped service-description and shell retrieval routes for published shells.',
      qualifier: 'Implementation evidence comes from current backend public routes.',
      evidence: {
        label: 'AAS public router evidence',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/backend/app/modules/dpps/public_router.py',
      },
    },
    {
      title: 'AASX export pipeline',
      claimLevel: 'implements',
      outcome: 'Exports AASX packages with explicit writer and validation flow in the export service.',
      qualifier: 'Framed as implemented export capability, not external certification.',
      evidence: {
        label: 'Export service evidence',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/backend/app/modules/export/service.py',
      },
    },
    {
      title: 'DPP4.0 template ingestion and refresh',
      claimLevel: 'implements',
      outcome: 'Supports listing and refreshing fetched template contracts and schemas.',
      qualifier: 'Availability depends on upstream template publication status.',
      evidence: {
        label: 'Template router evidence',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/backend/app/modules/templates/router.py',
      },
    },
    {
      title: 'GS1 Digital Link and IEC 61406 link generation',
      claimLevel: 'implements',
      outcome: 'Generates identifier links for published passports and carrier workflows.',
      qualifier: 'Positioned as implemented endpoint behavior in this platform.',
      evidence: {
        label: 'QR/router evidence',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/backend/app/modules/qr/router.py',
      },
    },
    {
      title: 'EDC dataspace publish and health surfaces',
      claimLevel: 'implements',
      outcome: 'Creates EDC assets, policies, and contract definitions with status/health checks.',
      qualifier: 'Interoperability outcomes depend on external connector configuration and partner environment.',
      evidence: {
        label: 'Connector router evidence',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/backend/app/modules/connectors/router.py',
      },
    },
    {
      title: 'EU ESPR framing',
      claimLevel: 'aligned',
      outcome: 'Uses conservative language aligned with ESPR and delegated-act rollout realities.',
      qualifier: 'No universal product-category compliance claim is made on landing pages.',
      evidence: {
        label: 'ESPR legal text',
        href: 'https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng',
      },
    },
    {
      title: 'Conformance test harness publication',
      claimLevel: 'roadmap',
      outcome: 'Planned publication of machine-verifiable conformance evidence artifacts.',
      qualifier: 'Not yet shipped as a public, versioned evidence bundle.',
      evidence: {
        label: 'Architecture docs',
        href: 'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public/architecture',
      },
    },
  ] satisfies StandardsMapRow[],

  dataspaceCards: [
    {
      title: 'Sovereign Sharing Path',
      claimLevel: 'implements',
      body: 'Connector flows expose EDC publication and policy primitives for controlled partner sharing.',
      evidence: {
        label: 'EDC connector endpoints',
        href: '/api/v1/docs',
      },
    },
    {
      title: 'Registry + Resolver Surfaces',
      claimLevel: 'implements',
      body: 'Built-in registry and GS1 resolver routes support discoverability and pointer resolution.',
      evidence: {
        label: 'Resolver + registry docs',
        href: 'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public/architecture',
      },
    },
    {
      title: 'Trust and Policy Controls',
      claimLevel: 'aligned',
      body: 'Keycloak + OPA + connector policy builders align platform flows with controlled access patterns.',
      evidence: {
        label: 'Operations docs',
        href: 'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public/operations',
      },
    },
  ] satisfies DataspaceCard[],

  developerSignals: [
    {
      title: 'API-first contract',
      detail: 'OpenAPI JSON and interactive docs are published at /api/v1/openapi.json and /api/v1/docs.',
    },
    {
      title: 'Identity and policy',
      detail: 'Keycloak (OIDC) and OPA policy checks are first-class platform services.',
    },
    {
      title: 'Composable runtime',
      detail: 'Docker Compose profiles include base stack plus optional EDC and DTR overlays.',
    },
    {
      title: 'Open-source posture',
      detail: 'MIT licensing and public documentation support reference implementation usage.',
    },
  ] satisfies DeveloperSignal[],

  faq: [
    {
      question: 'What is a Digital Product Passport under ESPR?',
      answer:
        'A Digital Product Passport is a product-specific digital record defined by the EU ESPR framework to make sustainability and lifecycle information accessible in a structured format.',
    },
    {
      question: 'How does this platform handle confidential supplier data?',
      answer:
        'Public landing and public summary surfaces are aggregate-only. Sensitive product identifiers, raw event payloads, and actor metadata are blocked by policy.',
    },
    {
      question: 'Is this implementation aligned with AAS and IDTA DPP4.0?',
      answer:
        'Yes. The platform is built on Asset Administration Shell structures and IDTA DPP4.0 template flows, with API and implementation evidence linked in the standards map.',
    },
    {
      question: 'Can I self-host the platform?',
      answer:
        'Yes. The repository ships with Docker Compose for local deployment and includes backend, frontend, Keycloak, OPA, PostgreSQL, Redis, and MinIO services.',
    },
    {
      question: 'How do I evaluate interoperability with dataspaces or Catena-X style flows?',
      answer:
        'Connector, registry, and resolver capabilities are exposed through documented APIs. Interoperability outcomes depend on external connector and partner environment configuration.',
    },
    {
      question: 'Where can I verify current public claims?',
      answer:
        'Landing claims are evidence-linked to API docs, public architecture/operations docs, and source routes so technical reviewers can verify scope quickly.',
    },
  ] satisfies FaqItem[],

  fallbackMetrics: [
    {
      label: 'Published DPPs',
      value: 'Live metrics temporarily unavailable',
      detail: 'Public summaries are offline; protected data remains unaffected.',
    },
    {
      label: 'Traceability coverage',
      value: 'Aggregate sync pending',
      detail: 'No per-record payload is shown while summary sync recovers.',
    },
    {
      label: 'Public data boundary',
      value: 'Strictly enforced',
      detail: 'Landing pages only present aggregate counters and timestamps.',
    },
  ] satisfies FallbackMetric[],

  dataExposureRules: [
    {
      item: 'Platform capabilities and standards links',
      showOnLanding: true,
      rule: 'Static, curated, evidence-linked copy only.',
    },
    {
      item: 'Aggregate published DPP count',
      showOnLanding: true,
      rule: 'Integer only from the public landing summary endpoint.',
    },
    {
      item: 'Aggregate product family count',
      showOnLanding: true,
      rule: 'Distinct count only.',
    },
    {
      item: 'Aggregate traceability coverage count',
      showOnLanding: true,
      rule: 'Count only, no event payload detail.',
    },
    {
      item: 'Latest publish timestamp',
      showOnLanding: true,
      rule: 'Single timestamp only.',
    },
    {
      item: 'Product-level identifiers (serialNumber, batchId, globalAssetId, dpp_id)',
      showOnLanding: false,
      rule: 'Explicitly prohibited on landing.',
    },
    {
      item: 'Raw AAS submodel content',
      showOnLanding: false,
      rule: 'Restricted to viewer and protected routes.',
    },
    {
      item: 'Raw EPCIS event payloads or location fields',
      showOnLanding: false,
      rule: 'Explicitly prohibited on landing.',
    },
    {
      item: 'Actor/user metadata',
      showOnLanding: false,
      rule: 'Explicitly prohibited.',
    },
  ] satisfies DataExposureRule[],

  finalCta: {
    title: 'Ready to publish your first passport?',
    subtitle:
      'Start with the live demo, then deploy locally to create, validate, and publish your own DPP workflows.',
    primaryCta: 'Open demo passport',
    primaryCtaHref: '#sample-passport',
    secondaryCta: 'Start local deployment',
    secondaryCtaHref:
      'https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose',
  } satisfies FinalCtaContent,

  footer: {
    developerLinks: [
      { label: 'API docs', href: '/api/v1/docs' },
      { label: 'OpenAPI schema', href: '/api/v1/openapi.json' },
      {
        label: 'Quickstart (README)',
        href: 'https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose',
        external: true,
      },
      {
        label: 'GitHub repository',
        href: 'https://github.com/hadijannat/mini-dpp-platform',
        external: true,
      },
    ] satisfies FooterLink[],
    policyLinks: [
      { label: 'Public data boundary', href: '#data-policy' },
      {
        label: 'Public data exposure policy',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/docs/public/operations/public-data-exposure-policy.md',
        external: true,
      },
      {
        label: 'ESPR overview',
        href: 'https://commission.europa.eu/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/ecodesign-sustainable-products-regulation_en',
        external: true,
      },
      {
        label: 'MIT License',
        href: 'https://github.com/hadijannat/mini-dpp-platform/blob/main/LICENSE',
        external: true,
      },
    ] satisfies FooterLink[],
  },
} as const;
