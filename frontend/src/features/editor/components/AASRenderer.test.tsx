// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useForm, FormProvider, type Control } from 'react-hook-form';
import { AASRenderer, AASRendererList } from './AASRenderer';
import type { DefinitionNode } from '../types/definition';

/** Wrapper that provides a RHF context for components using Controller */
function FormWrapper({
  defaultValues,
  children,
}: {
  defaultValues: Record<string, unknown>;
  children: (control: Control<Record<string, unknown>>) => React.ReactNode;
}) {
  const form = useForm<Record<string, unknown>>({ defaultValues });
  return <FormProvider {...form}>{children(form.control)}</FormProvider>;
}

describe('AASRenderer', () => {
  it('renders a Property field', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'name',
      valueType: 'xs:string',
      smt: { form_title: 'Product Name' },
    };

    render(
      <FormWrapper defaultValues={{ name: 'Test Product' }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="name"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Product Name')).toBeTruthy();
    expect(screen.getByDisplayValue('Test Product')).toBeTruthy();
  });

  it('renders a BooleanField for xs:boolean', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'active',
      valueType: 'xs:boolean',
      smt: { form_title: 'Is Active' },
    };

    render(
      <FormWrapper defaultValues={{ active: true }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="active"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Is Active')).toBeTruthy();
    const checkbox = screen.getByRole('checkbox');
    expect((checkbox as HTMLInputElement).checked).toBe(true);
  });

  it('renders an EnumField for form_choices', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'status',
      smt: {
        form_title: 'Status',
        form_choices: ['active', 'inactive', 'archived'],
      },
    };

    render(
      <FormWrapper defaultValues={{ status: 'active' }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="status"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Status')).toBeTruthy();
    const select = screen.getByRole('combobox');
    expect((select as HTMLSelectElement).value).toBe('active');
  });

  it('renders an unsupported node banner for Blob type', () => {
    const node: DefinitionNode = {
      modelType: 'Blob',
      idShort: 'data',
      smt: { form_title: 'Binary Data' },
    };

    render(
      <FormWrapper defaultValues={{ data: null }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="data"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Binary Data')).toBeTruthy();
    expect(screen.getByText(/Unsupported field/i)).toBeTruthy();
  });

  it('renders ReadOnlyField when access_mode is readonly', () => {
    const node: DefinitionNode = {
      modelType: 'Property',
      idShort: 'locked',
      smt: { form_title: 'Locked', access_mode: 'ReadOnly' },
    };

    render(
      <FormWrapper defaultValues={{ locked: 'value' }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="locked"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Locked')).toBeTruthy();
    // ReadOnlyField shows JSON-stringified value when value is present
    expect(screen.getByText('"value"')).toBeTruthy();
  });

  it('renders MultiLanguageProperty', () => {
    const node: DefinitionNode = {
      modelType: 'MultiLanguageProperty',
      idShort: 'title',
      smt: {
        form_title: 'Product Title',
        required_lang: ['en'],
      },
    };

    render(
      <FormWrapper defaultValues={{ title: { en: 'Hello' } }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="title"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Product Title')).toBeTruthy();
    expect(screen.getByDisplayValue('Hello')).toBeTruthy();
  });

  it('renders Range fields', () => {
    const node: DefinitionNode = {
      modelType: 'Range',
      idShort: 'temperature',
      smt: { form_title: 'Temperature' },
    };

    render(
      <FormWrapper defaultValues={{ temperature: { min: 10, max: 50 } }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="temperature"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('Temperature')).toBeTruthy();
  });

  it('renders list reorder controls when orderRelevant is true', () => {
    const node: DefinitionNode = {
      modelType: 'SubmodelElementList',
      idShort: 'ProductCarbonFootprint',
      orderRelevant: true,
      items: {
        modelType: 'Property',
        idShort: 'PcfItem',
        valueType: 'xs:string',
      },
    };

    render(
      <FormWrapper defaultValues={{ ProductCarbonFootprint: ['a', 'b'] }}>
        {(control) => (
          <AASRenderer
            node={node}
            basePath="ProductCarbonFootprint"
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByRole('button', { name: 'Move item 1 up' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Move item 1 down' })).toBeTruthy();
  });
});

describe('AASRendererList', () => {
  it('renders multiple nodes', () => {
    const nodes: DefinitionNode[] = [
      {
        modelType: 'Property',
        idShort: 'firstName',
        smt: { form_title: 'First Name' },
      },
      {
        modelType: 'Property',
        idShort: 'lastName',
        smt: { form_title: 'Last Name' },
      },
    ];

    render(
      <FormWrapper defaultValues={{ firstName: 'John', lastName: 'Doe' }}>
        {(control) => (
          <AASRendererList
            nodes={nodes}
            basePath=""
            depth={0}
            control={control}
          />
        )}
      </FormWrapper>,
    );

    expect(screen.getByText('First Name')).toBeTruthy();
    expect(screen.getByText('Last Name')).toBeTruthy();
    expect(screen.getByDisplayValue('John')).toBeTruthy();
    expect(screen.getByDisplayValue('Doe')).toBeTruthy();
  });
});
