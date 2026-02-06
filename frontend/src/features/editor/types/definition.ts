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
  allowed_range?: { min?: number; max?: number } | null;
  form_choices?: string[] | null;
};

export type DefinitionNode = {
  path?: string;
  idShort?: string;
  modelType: string;
  semanticId?: string | null;
  valueType?: string;
  displayName?: LangStringSet;
  description?: LangStringSet;
  smt?: SmtQualifiers;
  children?: DefinitionNode[];
  items?: DefinitionNode | null;
  entityType?: string;
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
  semantic_id: string;
};

export type SubmodelDefinitionResponse = {
  dpp_id: string;
  template_key: string;
  revision_id: string;
  revision_no: number;
  state: string;
  definition: TemplateDefinition;
};

export type FormData = Record<string, unknown>;
