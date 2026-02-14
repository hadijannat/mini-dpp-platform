import { useMemo, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
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
  register: ReturnType<typeof useForm<FormValues>>['register'],
  errors: ReturnType<typeof useForm<FormValues>>['formState']['errors'],
) {
  const testId = field.test_id ?? `cirpass-${step.level}-${field.name}`;
  const error = errors[field.name];

  if (field.type === 'checkbox') {
    return (
      <label key={field.name} className="flex items-center gap-2 text-sm text-landing-ink">
        <input type="checkbox" {...register(field.name)} data-testid={testId} />
        <span>{field.label}</span>
      </label>
    );
  }

  if (field.type === 'textarea') {
    return (
      <div key={field.name}>
        <Label htmlFor={`${step.id}-${field.name}`}>{field.label}</Label>
        <Textarea
          id={`${step.id}-${field.name}`}
          placeholder={field.placeholder ?? ''}
          {...register(field.name)}
          data-testid={testId}
        />
        {field.hint && <p className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
        {error && <p className="mt-1 text-xs text-rose-600">{String(error.message)}</p>}
      </div>
    );
  }

  if (field.type === 'select') {
    return (
      <div key={field.name}>
        <Label htmlFor={`${step.id}-${field.name}`}>{field.label}</Label>
        <select
          id={`${step.id}-${field.name}`}
          className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          {...register(field.name)}
          data-testid={testId}
        >
          {(field.options ?? []).map((option) => (
            <option key={`${field.name}-${option.value}`} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {field.hint && <p className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
        {error && <p className="mt-1 text-xs text-rose-600">{String(error.message)}</p>}
      </div>
    );
  }

  return (
    <div key={field.name}>
      <Label htmlFor={`${step.id}-${field.name}`}>{field.label}</Label>
      <Input
        id={`${step.id}-${field.name}`}
        type={field.type === 'number' ? 'number' : 'text'}
        step={field.type === 'number' ? 'any' : undefined}
        placeholder={field.placeholder ?? ''}
        {...register(field.name)}
        data-testid={testId}
      />
      {field.hint && <p className="mt-1 text-xs text-landing-muted">{field.hint}</p>}
      {error && <p className="mt-1 text-xs text-rose-600">{String(error.message)}</p>}
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
  const interactionOptions = interaction.options ?? [];
  const schema = useMemo(() => buildInteractionSchema(interaction), [interaction]);
  const defaultValues = useMemo(() => buildDefaultValues(interaction), [interaction]);
  const [selectedOption, setSelectedOption] = useState(interactionOptions[0]?.value ?? '');
  const [scanValue, setScanValue] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues,
    mode: 'onSubmit',
  });

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
          <form className="space-y-3" onSubmit={form.handleSubmit((values) => onSubmit(values))}>
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
