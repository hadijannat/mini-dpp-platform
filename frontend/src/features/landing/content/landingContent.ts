export type AudienceType = 'manufacturer' | 'regulator' | 'recycler' | 'consumer';

export type LandingIconKey =
  | 'factory'
  | 'scale'
  | 'wrench'
  | 'scan'
  | 'workflow'
  | 'shield'
  | 'globe'
  | 'api';

export interface NavigationLink {
  label: string;
  href: string;
}

export interface HeroContent {
  eyebrow: string;
  title: string;
  emphasis: string;
  subtitle: string;
  primaryCta: string;
  secondaryCta: string;
  highlights: string[];
}

export interface AudienceCardContent {
  id: AudienceType;
  icon: LandingIconKey;
  title: string;
  description: string;
  outcomes: string[];
}

export interface CapabilityStep {
  title: string;
  description: string;
}

export interface CapabilityCard {
  icon: LandingIconKey;
  title: string;
  body: string;
}

export interface EvidenceLink {
  label: string;
  href: string;
}

export interface StandardsClaim {
  title: string;
  qualifier: string;
  evidence: EvidenceLink[];
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

export interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

export const landingContent = {
  navigation: [
    { label: 'Audiences', href: '#audiences' },
    { label: 'Workflow', href: '#workflow' },
    { label: 'Standards', href: '#standards' },
    { label: 'Data Policy', href: '#data-policy' },
  ] satisfies NavigationLink[],

  hero: {
    eyebrow: 'ESPR-aligned workflows for supported categories',
    title: 'Digital Product Passport publishing for cross-functional teams',
    emphasis: 'without exposing sensitive product records.',
    subtitle:
      'Launch public-facing transparency with aggregate trust signals, keep record-level data protected, and route stakeholders to the right compliance context.',
    primaryCta: 'Start Secure Sign-In',
    secondaryCta: 'Explore Audience Journeys',
    highlights: [
      'Aggregate-only trust metrics on the first page',
      'AAS and IDTA-aligned modeling workflows',
      'Role-based publishing, viewing, and governance paths',
    ],
  } satisfies HeroContent,

  audienceCards: [
    {
      id: 'manufacturer',
      icon: 'factory',
      title: 'Manufacturers',
      description:
        'Coordinate authoring, quality checks, and publication pipelines with clear ownership boundaries.',
      outcomes: [
        'Publish consistent passport snapshots for approved products',
        'Track readiness across templates and product families',
      ],
    },
    {
      id: 'regulator',
      icon: 'scale',
      title: 'Regulators & Auditors',
      description:
        'Review structured disclosures and evidence-linked claims without requesting internal operational payloads.',
      outcomes: [
        'Validate public summaries against policy language',
        'Inspect standards-aligned references and scope qualifiers',
      ],
    },
    {
      id: 'recycler',
      icon: 'wrench',
      title: 'Recyclers & Repair Networks',
      description:
        'Use public-facing lifecycle context while keeping sensitive identifiers restricted to authorized channels.',
      outcomes: [
        'Access broad availability and traceability coverage signals',
        'Escalate to protected views only when operationally required',
      ],
    },
    {
      id: 'consumer',
      icon: 'scan',
      title: 'Consumers',
      description:
        'See transparent, high-level platform activity and standards context before interacting with product views.',
      outcomes: [
        'Understand what data is public and why',
        'Follow trusted links to standards and policy references',
      ],
    },
  ] satisfies AudienceCardContent[],

  capabilitySteps: [
    {
      title: 'Model and validate passport data',
      description:
        'Teams prepare template-driven records with governance checks before any public publication step.',
    },
    {
      title: 'Publish approved DPPs',
      description:
        'Only published records contribute to first-page trust metrics and public summary timelines.',
    },
    {
      title: 'Expose aggregate trust signals',
      description:
        'Landing-page summaries show counts and recency only, with no per-record identifiers.',
    },
    {
      title: 'Route authorized users deeper',
      description:
        'Detailed record views and event payloads remain in authenticated or scoped endpoints.',
    },
  ] satisfies CapabilityStep[],

  capabilityCards: [
    {
      icon: 'workflow',
      title: 'Workflow orchestration',
      body: 'Connect authoring, review, and publishing milestones in one operational path.',
    },
    {
      icon: 'shield',
      title: 'Privacy-first defaults',
      body: 'Protect identifiers and raw event payloads while still presenting transparent public summaries.',
    },
    {
      icon: 'globe',
      title: 'Cross-audience communication',
      body: 'Give each audience role-specific context without forcing a technical deep dive up front.',
    },
    {
      icon: 'api',
      title: 'Public API contract clarity',
      body: 'Use a dedicated landing summary endpoint with strict aggregate-only response fields.',
    },
  ] satisfies CapabilityCard[],

  standardsClaims: [
    {
      title: 'Supports ESPR-aligned workflows for supported categories',
      qualifier:
        'Scope depends on configured templates, enabled modules, and delegated-act timelines by product group.',
      evidence: [
        {
          label: 'EU ESPR regulation overview',
          href: 'https://commission.europa.eu/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/sustainable-products/ecodesign-sustainable-products-regulation_en',
        },
        {
          label: 'EU 2024/1781 text',
          href: 'https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng',
        },
      ],
    },
    {
      title: 'Uses AAS and IDTA-oriented data modeling patterns',
      qualifier:
        'Interoperability quality depends on the downstream systems and profile constraints selected per deployment.',
      evidence: [
        {
          label: 'IDTA submodel resources',
          href: 'https://industrialdigitaltwin.org/en/content-hub/submodels',
        },
        {
          label: 'AAS specifications',
          href: 'https://industrialdigitaltwin.org/en/content-hub/aasspecifications',
        },
      ],
    },
    {
      title: 'Enables traceability storytelling with protected operational details',
      qualifier:
        'Public pages communicate aggregate readiness while detailed event payloads stay in purpose-specific routes.',
      evidence: [
        {
          label: 'Platform API docs',
          href: '/api/v1/docs',
        },
      ],
    },
  ] satisfies StandardsClaim[],

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

  footer: {
    developerLinks: [
      { label: 'API docs', href: '/api/v1/docs' },
      { label: 'OpenAPI schema', href: '/api/v1/openapi.json' },
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
        label: 'ESPR source references',
        href: '#standards',
      },
    ] satisfies FooterLink[],
  },
} as const;
