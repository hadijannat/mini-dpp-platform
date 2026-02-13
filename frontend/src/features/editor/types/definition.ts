export type LangStringSet = Record<string, string>;

export type SmtQualifiers = {
  cardinality?: string | null;
  form_title?: string | null;
  form_info?: string | null;
  form_url?: string | null;
  access_mode?: string | null;
  required_lang?: string[];
  either_or?: string | null;
  allowed_value_regex?: string | null;
  allowed_range?: { min?: number; max?: number; raw?: string | null } | null;
  form_choices?: string[] | null;
  default_value?: string | null;
  initial_value?: string | null;
  example_value?: string | null;
  naming?: string | null;
  allowed_id_short?: string[];
  edit_id_short?: boolean | null;
};

export type DefinitionNode = {
  path?: string;
  idShort?: string;
  modelType: string;
  order?: number;
  orderRelevant?: boolean;
  semanticId?: string | null;
  supplementalSemanticIds?: string[];
  valueType?: string;
  contentType?: string;
  displayName?: LangStringSet;
  description?: LangStringSet;
  smt?: SmtQualifiers;
  x_resolution?: {
    status?: string;
    reason?: string;
    binding_id?: string;
    source_template_key?: string;
    target_semantic_id?: string;
    path?: string;
    [key: string]: unknown;
  };
  children?: DefinitionNode[];
  items?: DefinitionNode | null;
  entityType?: string;
  statements?: DefinitionNode[];
  first?: string;
  second?: string;
  annotations?: DefinitionNode[];
};

export type TemplateDefinition = {
  template_key?: string;
  semantic_id?: string | null;
  submodel?: {
    idShort?: string;
    elements?: DefinitionNode[];
  };
};

export type TemplateResponse = {
  id?: string;
  template_key?: string;
  idta_version?: string;
  resolved_version?: string | null;
  semantic_id: string;
  support_status?: 'supported' | 'experimental' | 'unavailable';
  refresh_enabled?: boolean;
  source_url?: string;
  source_repo_ref?: string | null;
  source_file_path?: string | null;
  source_file_sha?: string | null;
  source_kind?: string | null;
  selection_strategy?: string | null;
  fetched_at?: string;
};

export type SubmodelDefinitionResponse = {
  dpp_id: string;
  template_key: string;
  revision_id: string;
  revision_no: number;
  state: string;
  definition: TemplateDefinition;
};

export type TemplateContractResponse = {
  template_key: string;
  idta_version: string;
  semantic_id: string;
  definition: TemplateDefinition;
  schema: import('./uiSchema').UISchema;
  source_metadata: {
    resolved_version: string;
    source_repo_ref: string;
    source_file_path?: string | null;
    source_file_sha?: string | null;
    source_kind?: string | null;
    selection_strategy?: string | null;
    source_url: string;
  };
  dropin_resolution_report?: Array<Record<string, unknown>>;
  unsupported_nodes?: Array<{
    path?: string | null;
    idShort?: string | null;
    modelType?: string | null;
    semanticId?: string | null;
    reasons?: string[];
  }>;
  doc_hints?: {
    by_semantic_id?: Record<string, Record<string, unknown>>;
    by_id_short_path?: Record<string, Record<string, unknown>>;
    entries?: Array<Record<string, unknown>>;
  };
};

export type FormData = Record<string, unknown>;
