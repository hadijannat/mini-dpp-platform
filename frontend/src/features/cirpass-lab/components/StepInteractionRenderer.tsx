import { useEffect, useMemo, useRef, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { CirpassLabStep, CirpassLabStepInteraction } from '../schema/storySchema';

type FormValues = Record<string, unknown>;

interface StepInteractionRendererProps {
  step: CirpassLabStep;
  objective?: string;
  derivedHint: string;
  onSubmit: (payload: Record<string, unknown>) => void;
  onHint: () => void;
}

function getFieldInputId(stepId: string, fieldName: string): string {
  return `${stepId}-${fieldName}`;
}

function getFieldHintId(stepId: string, fieldName: string): string {
  return `${stepId}-${fieldName}-hint`;
}

function getFieldErrorId(stepId: string, fieldName: string): string {
  return `${stepId}-${fieldName}-error`;
}

function getFieldErrorMessage(error: unknown): string | null {
  if (!error || typeof error !== 'object') {
    return null;
  }
  const message = (error as { message?: unknown }).message;
  return typeof message === 'string' && message.trim().length > 0 ? message : null;
}

function pickKnownFieldValues(
  source: Record<string, unknown> | undefined,
  fieldNames: string[],
): FormValues {
  const values: FormValues = {};
  if (!source) {
    return values;
  }

  for (const fieldName of fieldNames) {
    if (Object.prototype.hasOwnProperty.call(source, fieldName)) {
      values[fieldName] = source[fieldName];
    }
  }

  return values;
}

function buildDefaultValues(interaction: CirpassLabStepInteraction): FormValues {
  const defaults: FormValues = {};
  for (const field of interaction.fields) {
    if (field.type === 'checkbox') {
      defaults[field.name] = false;
      continue;
    }
    if (field.type === 'select') {
      defaults[field.name] = field.options?.[0]?.value ?? '';
      continue;
    }
    defaults[field.name] = '';
  }
  return defaults;
}

function buildInteractionSchema(interaction: CirpassLabStepInteraction): z.ZodType<FormValues> {
  const shape: Record<string, z.ZodTypeAny> = {};

  for (const field of interaction.fields) {
    if (field.type === 'checkbox') {
      let schema: z.ZodTypeAny = z.boolean();
      if (field.required) {
        schema = schema.refine((value) => value, `${field.label} is required.`);
      }
      if (field.validation?.equals !== undefined) {
        const expected = field.validation.equals;
        schema = schema.refine((value) => value === expected, `${field.label} must equal ${expected}.`);
      }
      shape[field.name] = schema;
      continue;
    }

    if (field.type === 'number') {
      const base = z.preprocess(
        (value) => {
          if (value === '' || value === null || value === undefined) {
            return undefined;
          }
          const parsed = Number(value);
          return Number.isFinite(parsed) ? parsed : value;
        },
        z.number({ invalid_type_error: `${field.label} must be a number.` }),
      );

      let schema: z.ZodTypeAny = field.required
        ? base
        : base.optional();

      if (field.validation?.gt !== undefined) {
        schema = schema.refine(
          (value) => value === undefined || value > field.validation!.gt!,
          `${field.label} must be greater than ${field.validation.gt}.`,
        );
      }
      if (field.validation?.gte !== undefined) {
        schema = schema.refine(
          (value) => value === undefined || value >= field.validation!.gte!,
          `${field.label} must be at least ${field.validation.gte}.`,
        );
      }
      if (field.validation?.lt !== undefined) {
        schema = schema.refine(
          (value) => value === undefined || value < field.validation!.lt!,
          `${field.label} must be lower than ${field.validation.lt}.`,
        );
      }
      if (field.validation?.lte !== undefined) {
        schema = schema.refine(
          (value) => value === undefined || value <= field.validation!.lte!,
          `${field.label} must be at most ${field.validation.lte}.`,
        );
      }
      if (field.validation?.equals !== undefined) {
        schema = schema.refine(
          (value) => value === undefined || value === field.validation!.equals,
          `${field.label} must equal ${field.validation.equals}.`,
        );
      }
      shape[field.name] = schema;
      continue;
    }

    let schema: z.ZodTypeAny = z.string();
    if (field.required) {
      schema = (schema as z.ZodString).trim().min(1, `${field.label} is required.`);
    } else {
      schema = schema.optional().transform((value) => (value ?? '').toString());
    }

    if (field.validation?.min_length !== undefined) {
      schema = schema.refine(
        (value: string) =>
          value.trim().length === 0 ? !field.required : value.trim().length >= field.validation!.min_length!,
        `${field.label} must be at least ${field.validation.min_length} characters.`,
      );
    }
    if (field.validation?.max_length !== undefined) {
      schema = schema.refine(
        (value: string) => value.trim().length <= field.validation!.max_length!,
        `${field.label} must be at most ${field.validation.max_length} characters.`,
      );
    }
    if (field.validation?.pattern) {
      const pattern = new RegExp(field.validation.pattern);
      schema = schema.refine(
        (value: string) => value.trim().length === 0 ? !field.required : pattern.test(value),
        `${field.label} format is invalid.`,
      );
    }
    if (field.validation?.equals !== undefined) {
      schema = schema.refine(
        (value: string) => value === String(field.validation!.equals),
        `${field.label} must equal ${field.validation.equals}.`,
      );
    }
    shape[field.name] = schema;
  }

  return z.object(shape);
}

function renderFieldInput(
  step: CirpassLabStep,
  field: CirpassLabStepInteraction['fields'][number],
  register: UseFormRegister<FormValues>,
  errors: FieldErrors<FormValues>,
) {
  const testId = field.test_id ?? `cirpass-${step.level}-${field.name}`;
  const error = errors[field.name];
  const errorMessage = getFieldErrorMessage(error);
  const inputId = getFieldInputId(step.id, field.name);
  const hintId = getFieldHintId(step.id, field.name);
  const errorId = getFieldErrorId(step.id, field.name);
  const describedBy = [field.hint ? hintId : null, errorMessage ? errorId : null]
    .filter(Boolean)
    .join(' ') || undefined;

  if (field.type === 'checkbox') {
    return (
      <div key={field.name}>
        <div className="flex items-center gap-2 text-sm text-landing-ink">
          <input
            id={inputId}
            type="checkbox"
            aria-describedby={describedBy}
            aria-invalid={errorMessage ? true : undefined}
            {...register(field.name)}
            data-testid={testId}
          />
          <Label htmlFor={inputId}>{field.label}</Label>
        </div>
        {field.hint && <p id={hintId} className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
        {errorMessage && <p id={errorId} className="mt-1 text-xs text-rose-600">{errorMessage}</p>}
      </div>
    );
  }

  if (field.type === 'textarea') {
    return (
      <div key={field.name}>
        <Label htmlFor={inputId}>{field.label}</Label>
        <Textarea
          id={inputId}
          placeholder={field.placeholder ?? ''}
          aria-describedby={describedBy}
          aria-invalid={errorMessage ? true : undefined}
          {...register(field.name)}
          data-testid={testId}
        />
        {field.hint && <p id={hintId} className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
        {errorMessage && <p id={errorId} className="mt-1 text-xs text-rose-600">{errorMessage}</p>}
      </div>
    );
  }

  if (field.type === 'select') {
    return (
      <div key={field.name}>
        <Label htmlFor={inputId}>{field.label}</Label>
        <select
          id={inputId}
          className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          aria-describedby={describedBy}
          aria-invalid={errorMessage ? true : undefined}
          {...register(field.name)}
          data-testid={testId}
        >
          {(field.options ?? []).map((option) => (
            <option key={`${field.name}-${option.value}`} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {field.hint && <p id={hintId} className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
        {errorMessage && <p id={errorId} className="mt-1 text-xs text-rose-600">{errorMessage}</p>}
      </div>
    );
  }

  return (
    <div key={field.name}>
      <Label htmlFor={inputId}>{field.label}</Label>
      <Input
        id={inputId}
        type={field.type === 'number' ? 'number' : 'text'}
        step={field.type === 'number' ? 'any' : undefined}
        placeholder={field.placeholder ?? ''}
        aria-describedby={describedBy}
        aria-invalid={errorMessage ? true : undefined}
        {...register(field.name)}
        data-testid={testId}
      />
      {field.hint && <p id={hintId} className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
      {errorMessage && <p id={errorId} className="mt-1 text-xs text-rose-600">{errorMessage}</p>}
    </div>
  );
}

export default function StepInteractionRenderer({
  step,
  objective,
  derivedHint,
  onSubmit,
  onHint,
}: StepInteractionRendererProps) {
  const interaction = useMemo(
    () =>
      step.interaction ?? {
        kind: step.ui_action?.kind ?? 'form',
        submit_label: step.ui_action?.label ?? 'Validate & Continue',
        fields: [],
        options: [],
      },
    [step.interaction, step.ui_action?.kind, step.ui_action?.label],
  );
  const interactionOptions = useMemo(() => interaction.options ?? [], [interaction.options]);
  const schema = useMemo(() => buildInteractionSchema(interaction), [interaction]);
  const defaultValues = useMemo(() => buildDefaultValues(interaction), [interaction]);
  const fieldNames = useMemo(
    () => interaction.fields.map((field) => field.name),
    [interaction.fields],
  );
  const requestExampleValues = useMemo(
    () => pickKnownFieldValues(step.api?.request_example, fieldNames),
    [fieldNames, step.api?.request_example],
  );
  const hasRequestExample = Object.keys(requestExampleValues).length > 0;
  const [selectedOption, setSelectedOption] = useState(interactionOptions[0]?.value ?? '');
  const [scanValue, setScanValue] = useState('');
  const [payloadCopied, setPayloadCopied] = useState(false);
  const [shouldFocusErrorSummary, setShouldFocusErrorSummary] = useState(false);
  const errorSummaryRef = useRef<HTMLDivElement | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues,
    mode: 'onSubmit',
    shouldFocusError: false,
  });

  useEffect(() => {
    form.reset(defaultValues);
    setSelectedOption(interactionOptions[0]?.value ?? '');
    setScanValue('');
    setPayloadCopied(false);
    setShouldFocusErrorSummary(false);
  }, [defaultValues, form, interactionOptions, step.id]);

  const orderedFieldErrors = useMemo(
    () =>
      interaction.fields
        .map((field) => {
          const message = getFieldErrorMessage(form.formState.errors[field.name]);
          if (!message) {
            return null;
          }
          return {
            name: field.name,
            label: field.label,
            message,
            inputId: getFieldInputId(step.id, field.name),
          };
        })
        .filter((entry): entry is { name: string; label: string; message: string; inputId: string } => !!entry),
    [form.formState.errors, interaction.fields, step.id],
  );

  const hasErrorSummary = form.formState.submitCount > 0 && orderedFieldErrors.length > 0;

  useEffect(() => {
    if (!shouldFocusErrorSummary || !hasErrorSummary) {
      return;
    }
    errorSummaryRef.current?.focus();
    setShouldFocusErrorSummary(false);
  }, [hasErrorSummary, shouldFocusErrorSummary]);

  const handleUseExampleData = () => {
    form.reset({
      ...defaultValues,
      ...requestExampleValues,
    });
  };

  const handleCopyPayloadJson = async () => {
    const payload = pickKnownFieldValues(form.getValues(), fieldNames);
    if (!navigator.clipboard?.writeText) {
      return;
    }
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setPayloadCopied(true);
    window.setTimeout(() => setPayloadCopied(false), 1200);
  };

  const handleSimpleSubmit = () => {
    if (interaction.kind === 'click') {
      onSubmit({ action: 'click', step_id: step.id });
      return;
    }
    if (interaction.kind === 'select') {
      onSubmit({ selectedOption });
      return;
    }
    if (interaction.kind === 'scan') {
      onSubmit({ scannedValue: scanValue.trim() });
    }
  };

  return (
    <section className="rounded-3xl border border-landing-ink/15 bg-white/85 p-5 shadow-[0_24px_40px_-34px_rgba(17,37,49,0.65)]">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">Mission Control</p>
      <h3 className="mt-2 font-display text-2xl font-semibold text-landing-ink" data-testid="cirpass-current-level">
        {step.level.toUpperCase()}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-landing-muted">
        {objective ?? step.intent}
      </p>
      <p className="mt-1 text-xs text-landing-muted">
        Actor: <span className="font-semibold text-landing-ink">{step.actor}</span>
      </p>

      <div className="mt-4 rounded-2xl border border-landing-ink/12 bg-landing-surface-0/70 p-4">
        {interaction.kind === 'form' && (
          <form
            className="space-y-3"
            onSubmit={form.handleSubmit(
              (values) => onSubmit(values),
              () => setShouldFocusErrorSummary(true),
            )}
          >
            {hasErrorSummary && (
              <div
                ref={errorSummaryRef}
                tabIndex={-1}
                role="alert"
                aria-live="assertive"
                className="rounded-xl border border-rose-300 bg-rose-50 p-3"
                data-testid="cirpass-error-summary"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-rose-800">
                  Fix the following fields
                </p>
                <ul className="mt-2 space-y-1 text-sm text-rose-900">
                  {orderedFieldErrors.map((entry) => (
                    <li key={entry.name}>
                      <button
                        type="button"
                        className="text-left underline hover:no-underline"
                        onClick={() => document.getElementById(entry.inputId)?.focus()}
                        data-testid={`cirpass-error-link-${entry.name}`}
                      >
                        {entry.label}: {entry.message}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {interaction.fields.length > 0 ? (
              interaction.fields.map((field) =>
                renderFieldInput(step, field, form.register, form.formState.errors),
              )
            ) : (
              <p className="text-sm text-landing-muted">
                This step has no form fields. Validate to continue.
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="submit" className="rounded-full px-5" data-testid="cirpass-level-submit">
                {interaction.submit_label}
              </Button>
              {hasRequestExample && (
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full px-5"
                  onClick={handleUseExampleData}
                  data-testid="cirpass-level-use-example"
                >
                  Use example data
                </Button>
              )}
              <Button
                type="button"
                variant="outline"
                className="rounded-full px-5"
                onClick={() => {
                  void handleCopyPayloadJson();
                }}
                data-testid="cirpass-level-copy-json"
              >
                {payloadCopied ? 'Copied' : 'Copy payload JSON'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="rounded-full px-5"
                onClick={onHint}
                data-testid="cirpass-level-hint"
              >
                Use Hint
              </Button>
            </div>
          </form>
        )}

        {interaction.kind !== 'form' && (
          <div className="space-y-3">
            {interaction.kind === 'select' && (
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedOption}
                onChange={(event) => setSelectedOption(event.target.value)}
                data-testid={`cirpass-${step.level}-select`}
              >
                {interactionOptions.map((option) => (
                  <option key={`option-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
            {interaction.kind === 'scan' && (
              <Input
                value={scanValue}
                onChange={(event) => setScanValue(event.target.value)}
                placeholder="Scan token / resolver URL"
                data-testid={`cirpass-${step.level}-scan`}
              />
            )}
            <div className="flex flex-wrap gap-2">
              <Button type="button" className="rounded-full px-5" onClick={handleSimpleSubmit} data-testid="cirpass-level-submit">
                {interaction.submit_label}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="rounded-full px-5"
                onClick={onHint}
                data-testid="cirpass-level-hint"
              >
                Use Hint
              </Button>
            </div>
          </div>
        )}
      </div>

      <p className="mt-3 text-xs font-medium text-landing-muted">Hint: {interaction.hint_text ?? derivedHint}</p>
    </section>
  );
}
