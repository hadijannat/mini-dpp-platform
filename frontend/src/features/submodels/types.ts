export type SubmodelBindingSource =
  | 'semantic_exact'
  | 'semantic_alias'
  | 'provenance'
  | 'id_short'
  | 'unresolved';

export type SubmodelBinding = {
  submodel_id?: string | null;
  id_short?: string | null;
  semantic_id?: string | null;
  normalized_semantic_id?: string | null;
  template_key?: string | null;
  binding_source: SubmodelBindingSource | string;
  idta_version?: string | null;
  resolved_version?: string | null;
  support_status?: 'supported' | 'experimental' | 'unavailable' | string | null;
  refresh_enabled?: boolean | null;
};

export type SubmodelFieldMeta = {
  semanticId?: string;
  qualifiers: Record<string, string>;
  cardinality?: string;
  required: boolean;
  readOnly: boolean;
  validations: string[];
};

export type SubmodelNode = {
  id: string;
  label: string;
  path: string;
  modelType: string;
  value?: unknown;
  children: SubmodelNode[];
  meta: SubmodelFieldMeta;
};

export type SubmodelHealth = {
  totalRequired: number;
  completedRequired: number;
  validationSignals: number;
  leafCount: number;
};

export type DppAccessSummary = {
  can_read: boolean;
  can_update: boolean;
  can_publish: boolean;
  can_archive: boolean;
  source: 'owner' | 'share' | 'tenant_admin' | string;
};

export type DppActionState = {
  canRead: boolean;
  canUpdate: boolean;
  canExport: boolean;
  canPublish: boolean;
  canRefreshRebuild: boolean;
  canGenerateQr: boolean;
  canCaptureEvent: boolean;
  canViewEvents: boolean;
};

