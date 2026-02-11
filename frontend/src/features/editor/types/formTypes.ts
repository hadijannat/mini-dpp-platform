import type { Control, UseFormReturn } from 'react-hook-form';
import type { DefinitionNode } from './definition';
import type { UISchema } from './uiSchema';

export type EditorContext = {
  dppId: string;
  tenantSlug: string;
  token?: string;
};

/** Props passed to every field component */
export type FieldProps = {
  /** RHF field name (dot-separated path like "ContactInformation.0.Phone") */
  name: string;
  /** RHF control object */
  control: Control<Record<string, unknown>>;
  /** Definition node from the template AST */
  node: DefinitionNode;
  /** Optional UISchema node for this field */
  schema?: UISchema;
  /** Nesting depth (0 = top-level) */
  depth: number;
  /** Whether the field is read-only (from access_mode) */
  readOnly?: boolean;
  /** Whether user interaction should be disabled (permission/policy gate) */
  disabled?: boolean;
  /** Optional editor request context used by upload-capable fields */
  editorContext?: EditorContext;
};

/** Props for the AASRenderer dispatcher */
export type AASRendererProps = {
  node: DefinitionNode;
  basePath: string;
  depth: number;
  schema?: UISchema;
  control: Control<Record<string, unknown>>;
  disabled?: boolean;
  editorContext?: EditorContext;
};

/** Props for the FieldWrapper label/error shell */
export type FieldWrapperProps = {
  label: string;
  required?: boolean;
  description?: string;
  formUrl?: string;
  error?: string;
  unit?: string;
  /** Optional ID to associate label with input via htmlFor */
  fieldId?: string;
  /** Canonical field path for jump-link and diagnostics targeting */
  fieldPath?: string;
  children: React.ReactNode;
};

/** Form context returned by useSubmodelForm */
export type SubmodelFormContext = {
  form: UseFormReturn<Record<string, unknown>>;
  zodSchema: unknown;
  initialData: Record<string, unknown>;
};
